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

    def generate_relationship_tables_ddl(self) -> list[str]:
        """Generate DDL for relationship tables from YAML schema using YamlTranslator.

        Uses YamlTranslator to discover relations and centralized table naming.
        Handles directed/undirected semantics for table creation.

        Returns:
            List of DDL strings for relationship tables

        Raises:
            DatabaseError: If YamlTranslator not provided or schema access fails
        """
        if not self.yaml_translator:
            # Return empty list if no YamlTranslator - maintains compatibility
            return []

        ddl_statements = []
        created_tables = set()  # Track unique table names to avoid duplicates

        try:
            # Use YamlTranslator to discover all relations across all entities
            for entity_name in self.yaml_translator.get_entity_types():
                relation_specs = self.yaml_translator.get_relations_for_source(entity_name)

                for spec in relation_specs:
                    # Validate predicate against TypeRegistry
                    predicate = spec["predicate"]
                    if not self.type_registry.validate_relation_predicate(predicate):
                        raise DatabaseError(
                            f"Invalid predicate '{predicate}' not found in TypeRegistry",
                            operation="generate_relationship_tables_ddl",
                            context={"predicate": predicate, "spec": spec},
                        )

                    # Generate table name using centralized helper
                    table_name = self.yaml_translator.relationship_table_name(
                        source=spec["source"],
                        predicate=spec["predicate"],
                        target=spec["target"],
                        directed=spec["directed"],
                    )

                    # Skip if we've already created this table
                    if table_name in created_tables:
                        continue

                    created_tables.add(table_name)

                    # Create DDL - direction affects semantics but not table structure
                    ddl = f"""CREATE REL TABLE IF NOT EXISTS {table_name}(
                        FROM {spec["source"]} TO {spec["target"]}
                    )"""
                    ddl_statements.append(ddl)

        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(
                "Failed to generate relationship tables DDL",
                operation="generate_relationship_tables_ddl",
                original_error=e,
            ) from e

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

        # Entity tables
        ddl_statements.extend(self.generate_all_entity_tables_ddl())

        # Relationship tables
        ddl_statements.extend(self.generate_relationship_tables_ddl())

        # System tables
        ddl_statements.append(self.generate_hrid_mapping_table_ddl())

        return ddl_statements
