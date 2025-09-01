"""Database client management - thin layer for explicit database setup.

User controls database paths. No fallbacks. No automation.
"""

from __future__ import annotations

from contextlib import suppress
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
from .graph_register import GraphRegister


class DatabaseClients:
    """DDL-only database setup - creates schemas and returns raw clients.

    NO INTERFACES - pure schema creation only.
    Consumer must create interfaces separately using returned raw clients.

    Attributes:
        qdrant_client: Pre-initialized QdrantClient.
        kuzu_connection: Pre-initialized Kuzu connection.
        db_name: Database name.
        qdrant_path: Path to Qdrant database.
        kuzu_path: Path to Kuzu database.
        yaml_translator: YAML translator instance.
    """

    def __init__(self, yaml_path: str | None = None):
        """Create DDL-only database client wrapper.

        Args:
            yaml_path: Path to YAML schema file. User must provide - no defaults.
        """
        self.qdrant_client: QdrantClient | None = None
        self.kuzu_connection: kuzu.Connection | None = None
        self.db_name = "memg"
        self.qdrant_path = "qdrant"
        self.kuzu_path = "kuzu"

        self.yaml_translator = YamlTranslator(yaml_path) if yaml_path else None

    def init_dbs(self, db_path: str, db_name: str):
        """Initialize databases with structured paths.

        Args:
            db_path: Base database directory.
            db_name: Database name (used for collection and file names).
        """
        # Structure paths
        qdrant_path = os.path.join(db_path, "qdrant")
        kuzu_path = os.path.join(db_path, "kuzu", db_name)

        # Store paths and names
        self.qdrant_path = qdrant_path
        self.kuzu_path = kuzu_path
        self.db_name = db_name

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
        self._setup_qdrant_collection(qdrant_client, self.db_name)
        self._setup_kuzu_tables_with_graph_register(kuzu_conn)

    def _setup_qdrant_collection(self, client: QdrantClient, collection_name: str) -> None:
        """Create Qdrant collection if it doesn't exist.

        Args:
            client: Qdrant client instance.
            collection_name: Name of the collection to create.

        Raises:
            DatabaseError: If collection creation fails.
        """
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
            ) from e

    def _setup_kuzu_tables_with_graph_register(self, conn: kuzu.Connection) -> None:
        """Create Kuzu tables using GraphRegister for DDL generation.

        Args:
            conn: Kuzu database connection.

        Raises:
            DatabaseError: If YAML translator not initialized or table creation fails.
        """
        if not self.yaml_translator:
            raise DatabaseError(
                "YAML translator not initialized. Provide yaml_path to constructor.",
                operation="_setup_kuzu_tables_with_graph_register",
            )

        try:
            # Create GraphRegister with YamlTranslator for complete DDL generation
            graph_register = GraphRegister(yaml_translator=self.yaml_translator)

            # Generate all DDL statements using GraphRegister
            ddl_statements = graph_register.generate_all_ddl()

            # Execute all DDL statements
            for ddl in ddl_statements:
                conn.execute(ddl)

        except Exception as e:
            raise DatabaseError(
                "Failed to setup Kuzu tables using GraphRegister",
                operation="_setup_kuzu_tables_with_graph_register",
                original_error=e,
            ) from e

    # ===== INTERFACE ACCESS METHODS =====
    # After DDL operations, provide access to CRUD interfaces

    def get_qdrant_interface(self) -> QdrantInterface:
        """Get Qdrant interface using the initialized client.

        Returns:
            QdrantInterface: Configured with the DDL-created client and collection.

        Raises:
            DatabaseError: If client not initialized (call init_dbs first).
        """
        if self.qdrant_client is None:
            raise DatabaseError(
                "Qdrant client not initialized. Call init_dbs() first.",
                operation="get_qdrant_interface",
            )
        return QdrantInterface(self.qdrant_client, self.db_name)

    def get_kuzu_interface(self) -> KuzuInterface:
        """Get Kuzu interface using the initialized connection.

        Returns:
            KuzuInterface: Configured with the DDL-created connection.

        Raises:
            DatabaseError: If connection not initialized (call init_dbs first).
        """
        if self.kuzu_connection is None:
            raise DatabaseError(
                "Kuzu connection not initialized. Call init_dbs() first.",
                operation="get_kuzu_interface",
            )
        return KuzuInterface(self.kuzu_connection, self.yaml_translator)

    def get_embedder(self) -> Embedder:
        """Get embedder instance.

        Returns:
            Embedder: Instance for generating vectors.
        """
        return Embedder()

    def get_yaml_translator(self) -> YamlTranslator:
        """Get the YAML translator used for schema operations.

        Returns:
            YamlTranslator: Instance used during DDL operations.

        Raises:
            DatabaseError: If YAML translator not initialized.
        """
        if self.yaml_translator is None:
            raise DatabaseError(
                "YAML translator not initialized. Provide yaml_path to constructor.",
                operation="get_yaml_translator",
            )
        return self.yaml_translator

    def close(self):
        """Close all database connections and cleanup resources.

        Should be called when database clients are no longer needed.
        """
        if self.qdrant_client is not None:
            with suppress(Exception):
                # Ignore cleanup errors - best effort
                self.qdrant_client.close()
            self.qdrant_client = None

        if self.kuzu_connection is not None:
            with suppress(Exception):
                # Ignore cleanup errors - best effort
                self.kuzu_connection.close()
            self.kuzu_connection = None
