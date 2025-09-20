"""Graph database DDL generation - database agnostic schema creation.

Generates DDL statements for graph databases using TypeRegistry as single source of truth.
Future-proof design supports Kuzu today, Neo4j/ArangoDB tomorrow.
"""

from __future__ import annotations

from ..core.exceptions import DatabaseError
from ..core.types import TypeRegistry
from ..core.yaml_translator import YamlTranslator


class GraphRegister:
    """Generates DDL statements for graph databases using TypeRegistry.

    Database-agnostic design - generates DDL that can be adapted for:
    - Kuzu (current)
    - Neo4j (future)
    - ArangoDB (future)
    - Any graph database with node/relationship tables
    """

    def __init__(
        self,
        type_registry: TypeRegistry | None = None,
        yaml_translator: YamlTranslator | None = None,
    ):
        """Initialize GraphRegister with TypeRegistry and YamlTranslator.

        Args:
            type_registry: TypeRegistry instance. If None, uses global singleton.
            yaml_translator: YamlTranslator for accessing full YAML schema. Optional.
        """
        self.type_registry = type_registry or TypeRegistry.get_instance()
        self.yaml_translator = yaml_translator

        # Validate TypeRegistry is properly initialized
        try:
            self.type_registry.get_valid_entity_names()
        except RuntimeError as e:
            raise DatabaseError(
                "TypeRegistry not initialized. Call initialize_types_from_yaml() first.",
                operation="graph_register_init",
                original_error=e,
            ) from e

    def generate_entity_table_ddl(self, entity_name: str) -> str:
        """Generate DDL for a single entity table.

        Args:
            entity_name: Name of entity type (e.g., 'task', 'bug')

        Returns:
            DDL string for creating the entity table

        Raises:
            DatabaseError: If entity not found in TypeRegistry
        """
        # Validate entity exists in TypeRegistry
        valid_entities = self.type_registry.get_valid_entity_names()
        if entity_name not in valid_entities:
            raise DatabaseError(
                f"Entity '{entity_name}' not found in TypeRegistry",
                operation="generate_entity_table_ddl",
                context={"entity_name": entity_name, "valid_entities": valid_entities},
            )

        # Get Pydantic model with all fields (inheritance already resolved)
        model = self.type_registry.get_entity_model(entity_name)

        # Build column definitions from Pydantic model fields
        columns = []
        system_field_names = {
            "id",
            "user_id",
            "memory_type",
            "created_at",
            "updated_at",
        }

        for field_name, _field_info in model.model_fields.items():
            # Skip system fields - they'll be added separately
            if field_name in system_field_names:
                continue
            # All user fields are STRING for now (Kuzu limitation)
            # TODO: Add proper type mapping when Kuzu supports more types
            columns.append(f"{field_name} STRING")

        # Add system fields (not in YAML schema)
        system_columns = [
            "id STRING",
            "user_id STRING",
            "memory_type STRING",
            "created_at STRING",
            "updated_at STRING",
        ]

        all_columns = system_columns + columns
        columns_sql = ",\n                ".join(all_columns)

        # Generate Kuzu-style DDL (adaptable for other graph DBs)
        ddl = f"""CREATE NODE TABLE IF NOT EXISTS {entity_name}(
                {columns_sql},
                PRIMARY KEY (id)
        )"""

        return ddl

    def generate_all_entity_tables_ddl(self) -> list[str]:
        """Generate DDL for all entity tables from TypeRegistry.

        Returns:
            List of DDL strings, one per entity table
        """
        ddl_statements = []

        for entity_name in self.type_registry.get_valid_entity_names():
            ddl = self.generate_entity_table_ddl(entity_name)
            ddl_statements.append(ddl)

        return ddl_statements

    def generate_memory_base_table_ddl(self) -> str:
        """Generate DDL for base Memory table used for relationships.

        All entities are also stored in this table to enable unified relationship model.
        Contains only system fields needed for relationships and filtering.

        Returns:
            DDL string for Memory table
        """
        ddl = """CREATE NODE TABLE IF NOT EXISTS Memory(
                id STRING,
                user_id STRING,
                memory_type STRING,
                created_at STRING,
                updated_at STRING,
                PRIMARY KEY (id)
        )"""

        return ddl

    def generate_relationship_tables_ddl(self) -> list[str]:
        """Generate DDL for predicate-based relationship tables.

        Creates one relationship table per predicate type (RELATES_TO, ANNOTATES, etc.).
        Each table connects Memory nodes, eliminating entity combination explosion.

        Returns:
            List of DDL strings, one per predicate type
        """
        # Get all predicates from TypeRegistry
        predicates = self.type_registry.get_valid_predicates()

        ddl_statements = []
        for predicate in predicates:
            # Create relationship table for this predicate
            ddl = f"""CREATE REL TABLE IF NOT EXISTS {predicate}(
                FROM Memory TO Memory,
                user_id STRING
            )"""
            ddl_statements.append(ddl)

        return ddl_statements

    def generate_hrid_mapping_table_ddl(self) -> str:
        """Generate DDL for HRID mapping table (system table).

        Returns:
            DDL string for HRID mapping table
        """
        ddl = """CREATE NODE TABLE IF NOT EXISTS HridMapping(
            hrid_user_key STRING,
            hrid STRING,
            uuid STRING,
            memory_type STRING,
            user_id STRING,
            created_at STRING,
            deleted_at STRING,
            PRIMARY KEY (hrid_user_key)
        )"""

        return ddl

    def generate_all_ddl(self) -> list[str]:
        """Generate all DDL statements for complete schema setup.

        Returns:
            List of all DDL statements needed for schema creation
        """
        ddl_statements = []

        # Base Memory table (for relationships)
        ddl_statements.append(self.generate_memory_base_table_ddl())

        # Entity tables (separate table per node type)
        ddl_statements.extend(self.generate_all_entity_tables_ddl())

        # Relationship tables (one table per predicate type)
        ddl_statements.extend(self.generate_relationship_tables_ddl())

        # System tables
        ddl_statements.append(self.generate_hrid_mapping_table_ddl())

        return ddl_statements
