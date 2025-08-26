"""Database client management - thin layer for explicit database setup.

User controls database paths. No fallbacks. No automation.
"""

from __future__ import annotations

import os
from pathlib import Path

import kuzu
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from ..core.config import get_config
from ..core.exceptions import DatabaseError
from ..core.interfaces.embedder import Embedder
from ..core.interfaces.kuzu import KuzuInterface
from ..core.interfaces.qdrant import QdrantInterface
from ..core.yaml_translator import YamlTranslator


class DatabaseClients:
    """DDL-only database setup - creates schemas and returns raw clients.

    NO INTERFACES - pure schema creation only.
    Consumer must create interfaces separately using returned raw clients.
    """

    def __init__(self, yaml_path: str | None = None):
        """Create DDL-only database client wrapper.

        Args:
            yaml_path: Path to YAML schema file. User must provide - no defaults.
        """
        self.qdrant_client = None
        self.kuzu_connection = None
        self.db_name = "memg"
        self.qdrant_path = "qdrant"
        self.kuzu_path = "kuzu"
        self.yaml_translator = YamlTranslator(yaml_path) if yaml_path else None

    def init_dbs(self, db_path: str, db_name: str):
        """Initialize databases with structured paths.

        Args:
            db_path: Base database directory
            db_name: Database name (used for collection and file names)
        """
        # Structure paths
        qdrant_path = os.path.join(db_path, "qdrant")
        kuzu_path = os.path.join(db_path, "kuzu", db_name)
        collection_name = db_name

        # Store paths and names
        self.qdrant_path = qdrant_path
        self.kuzu_path = kuzu_path
        self.db_name = db_name
        self.collection_name = collection_name

        # Ensure directories exist
        os.makedirs(qdrant_path, exist_ok=True)
        os.makedirs(Path(kuzu_path).parent, exist_ok=True)

        # Create raw database clients directly
        qdrant_client = QdrantClient(path=qdrant_path)
        kuzu_db = kuzu.Database(kuzu_path)
        kuzu_conn = kuzu.Connection(kuzu_db)

        # Store raw clients for interface creation
        self.qdrant_client = qdrant_client
        self.kuzu_connection = kuzu_conn

        # DDL operations - create collection and tables
        self._setup_qdrant_collection(qdrant_client, collection_name)
        self._setup_kuzu_tables(kuzu_conn)

    def _setup_qdrant_collection(self, client: QdrantClient, collection_name: str) -> None:
        """Create Qdrant collection if it doesn't exist"""
        try:
            config = get_config()
            vector_dimension = config.memg.vector_dimension

            collections = client.get_collections()
            if not any(col.name == collection_name for col in collections.collections):
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_dimension, distance=Distance.COSINE),
                )
        except Exception as e:
            raise DatabaseError(
                "Failed to setup Qdrant collection",
                operation="_setup_qdrant_collection",
                original_error=e,
            )

    def _setup_kuzu_tables(self, conn: kuzu.Connection) -> None:
        """Create Kuzu tables dynamically from YAML schema"""
        if not self.yaml_translator:
            raise DatabaseError(
                "YAML translator not initialized. Provide yaml_path to constructor.",
                operation="_setup_kuzu_tables",
            )

        try:
            # Get all entity types from YAML schema
            entities_map = self.yaml_translator._entities_map()

            # Create node table for each entity type
            for entity_name, entity_spec in entities_map.items():
                self._create_entity_table(conn, entity_name, entity_spec)

            # Create relationship tables from YAML schema
            self._create_relationship_tables(conn, entities_map)

            # Create HRID mapping table (adhoc - not from YAML)
            self._create_hrid_mapping_table(conn)

        except Exception as e:
            raise DatabaseError(
                "Failed to setup Kuzu tables from YAML schema",
                operation="_setup_kuzu_tables",
                original_error=e,
            )

    def _create_entity_table(
        self, conn: kuzu.Connection, entity_name: str, entity_spec: dict
    ) -> None:
        """Create a node table for a specific entity type from YAML schema"""
        # Collect all fields including inherited ones
        all_fields = self._collect_all_fields(entity_spec)

        # Build column definitions from YAML fields
        columns = []
        for field_name, field_spec in all_fields.items():
            if isinstance(field_spec, dict):
                # Skip system fields that are auto-managed
                if field_spec.get("system", False):
                    continue
                # All user fields are STRING for now (Kuzu limitation)
                columns.append(f"{field_name} STRING")
            else:
                # Simple field definition
                columns.append(f"{field_name} STRING")

        # TODO: add system fields to YAML schema
        system_columns = [
            "id STRING",
            "user_id STRING",
            "memory_type STRING",
            "created_at STRING",
            "updated_at STRING",
        ]

        all_columns = system_columns + columns
        columns_sql = ",\n                ".join(all_columns)

        create_sql = f"""
        CREATE NODE TABLE IF NOT EXISTS {entity_name}(
                {columns_sql},
                PRIMARY KEY (id)
        )
        """
        conn.execute(create_sql)

    def _create_relationship_tables(self, conn: kuzu.Connection, entities_map: dict) -> None:
        """Create relationship tables from YAML schema"""
        for entity_name, entity_spec in entities_map.items():
            relations = entity_spec.get("relations", [])
            if not relations:
                continue

            for relation in relations:
                if not isinstance(relation, dict):
                    continue

                rel_name = relation.get("name")
                source = relation.get("source", entity_name)
                target = relation.get("target")
                predicates = relation.get("predicates", [])

                if not all([rel_name, source, target, predicates]):
                    continue

                # Create relationship table for each predicate
                for predicate in predicates:
                    create_rel_sql = f"""
                    CREATE REL TABLE IF NOT EXISTS {predicate}(
                        FROM {source} TO {target}
                    )
                    """
                    conn.execute(create_rel_sql)

    def _collect_all_fields(self, entity_spec: dict) -> dict:
        """Collect all fields for an entity, including inherited fields from parent"""
        all_fields = {}
        entities_map = self.yaml_translator._entities_map()

        # Traverse inheritance chain
        current_spec = entity_spec
        visited = set()  # Prevent infinite loops

        while current_spec:
            # Add fields from current entity
            fields = current_spec.get("fields", {})
            for field_name, field_spec in fields.items():
                if field_name not in all_fields:  # Don't override child fields
                    all_fields[field_name] = field_spec

            # Move to parent
            parent_name = current_spec.get("parent")
            if not parent_name or parent_name in visited:
                break

            visited.add(parent_name)
            current_spec = entities_map.get(parent_name.lower())

        return all_fields

    def _create_hrid_mapping_table(self, conn: kuzu.Connection) -> None:
        """Create HRID mapping table for UUID↔HRID translation (adhoc system table)"""
        create_sql = """
        CREATE NODE TABLE IF NOT EXISTS HridMapping(
            hrid STRING,
            uuid STRING,
            memory_type STRING,
            created_at STRING,
            deleted_at STRING,
            PRIMARY KEY (hrid)
        )
        """
        conn.execute(create_sql)

    # ===== INTERFACE ACCESS METHODS =====
    # After DDL operations, provide access to CRUD interfaces

    def get_qdrant_interface(self) -> QdrantInterface:
        """Get Qdrant interface using the initialized client.

        Returns:
            QdrantInterface configured with the DDL-created client and collection

        Raises:
            DatabaseError: If client not initialized (call init_dbs first)
        """
        if self.qdrant_client is None:
            raise DatabaseError(
                "Qdrant client not initialized. Call init_dbs() first.",
                operation="get_qdrant_interface",
            )
        return QdrantInterface(self.qdrant_client, self.collection_name)

    def get_kuzu_interface(self) -> KuzuInterface:
        """Get Kuzu interface using the initialized connection.

        Returns:
            KuzuInterface configured with the DDL-created connection

        Raises:
            DatabaseError: If connection not initialized (call init_dbs first)
        """
        if self.kuzu_connection is None:
            raise DatabaseError(
                "Kuzu connection not initialized. Call init_dbs() first.",
                operation="get_kuzu_interface",
            )
        return KuzuInterface(self.kuzu_connection)

    def get_embedder(self) -> Embedder:
        """Get embedder instance.

        Returns:
            Embedder instance for generating vectors
        """
        return Embedder()

    def get_yaml_translator(self) -> YamlTranslator:
        """Get the YAML translator used for schema operations.

        Returns:
            YamlTranslator instance used during DDL operations

        Raises:
            DatabaseError: If YAML translator not initialized
        """
        if self.yaml_translator is None:
            raise DatabaseError(
                "YAML translator not initialized. Provide yaml_path to constructor.",
                operation="get_yaml_translator",
            )
        return self.yaml_translator
