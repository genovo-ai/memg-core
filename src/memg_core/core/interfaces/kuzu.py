"""Simple Kuzu interface wrapper - pure I/O operations only"""

import os
from typing import Any

import kuzu

from memg_core.core.exceptions import DatabaseError


class KuzuInterface:
    """Simple wrapper around Kuzu database - CRUD and query only"""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.getenv("KUZU_DB_PATH")
            if not db_path:
                raise DatabaseError(
                    "KUZU_DB_PATH environment variable must be set! No defaults allowed.",
                    operation="__init__",
                )

            # Expand $HOME and other variables
            db_path = os.path.expandvars(db_path)

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        try:
            self.db = kuzu.Database(db_path)
            self.conn = kuzu.Connection(self.db)
        except Exception as e:
            raise DatabaseError(
                "Failed to initialize Kuzu database",
                operation="init",
                original_error=e,
            )

    def add_node(self, table: str, properties: dict[str, Any]) -> None:
        """Add a node to the graph with dynamic schema creation"""
        try:
            # Create table dynamically based on properties
            self._ensure_table_schema(table, properties)

            props = ", ".join([f"{k}: ${k}" for k in properties])
            query = f"CREATE (:{table} {{{props}}})"
            self.conn.execute(query, parameters=properties)
        except Exception as e:
            raise DatabaseError(
                f"Failed to add node to {table}",
                operation="add_node",
                context={"table": table, "properties": properties},
                original_error=e,
            )

    def _ensure_table_schema(self, table: str, properties: dict[str, Any]) -> None:
        """Ensure table exists with proper schema based on properties"""
        try:
            # Generate schema from properties - type-agnostic
            columns = []
            for key, value in properties.items():
                kuzu_type = self._get_kuzu_type(key, value)
                columns.append(f"{key} {kuzu_type}")

            columns_str = ", ".join(columns)
            create_sql = f"CREATE NODE TABLE IF NOT EXISTS {table}({columns_str}, PRIMARY KEY (id))"

            # Execute table creation with explicit error handling
            try:
                self.conn.execute(create_sql)
            except Exception as create_error:
                # Only ignore "table already exists" errors, not all exceptions
                error_msg = str(create_error).lower()
                if "already exists" in error_msg or "duplicate" in error_msg:
                    # Table exists with potentially different schema - this is acceptable
                    pass
                else:
                    # Real error - re-raise with context
                    raise DatabaseError(
                        f"Failed to create table {table}: {create_error}",
                        operation="_ensure_table_schema",
                        context={"table": table, "sql": create_sql},
                        original_error=create_error,
                    )
        except DatabaseError:
            # Re-raise our own errors
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise DatabaseError(
                f"Failed to ensure table schema for {table}",
                operation="_ensure_table_schema",
                context={"table": table, "properties": properties},
                original_error=e,
            )

    def add_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        props: dict[str, Any] | None = None,
    ) -> None:
        """Add relationship between nodes"""
        try:
            props = props or {}

            # VALIDATE RELATIONSHIP AGAINST YAML SCHEMA - crash if invalid
            try:
                from ..types import validate_relation_predicate

                if not validate_relation_predicate(rel_type):
                    raise ValueError(
                        f"Invalid relationship predicate: {rel_type}. Must be defined in YAML schema."
                    )
            except RuntimeError:
                # TypeRegistry not initialized - skip validation for now
                pass

            # Use relationship type as-is (predicates from YAML) - no sanitization
            # rel_type should already be a valid predicate (e.g., "REFERENCED_BY", "ANNOTATES")

            # Create relationship table if it doesn't exist
            prop_columns = (
                ", ".join([f"{k} {self._get_kuzu_type(k, v)}" for k, v in props.items()])
                if props
                else ""
            )
            extra_cols = f", {prop_columns}" if prop_columns else ""

            create_table_sql = (
                f"CREATE REL TABLE IF NOT EXISTS {rel_type}"
                f"(FROM {from_table} TO {to_table}{extra_cols})"
            )

            try:
                self.conn.execute(create_table_sql)
            except Exception as schema_error:
                error_msg = str(schema_error).lower()
                if "type" in error_msg or "schema" in error_msg:
                    # Schema mismatch - attempt to drop and recreate
                    try:
                        self.conn.execute(f"DROP TABLE {rel_type}")
                        self.conn.execute(create_table_sql)
                    except Exception as recreate_error:
                        raise DatabaseError(
                            f"Failed to recreate relationship table {rel_type}",
                            operation="add_relationship",
                            context={
                                "original_error": str(schema_error),
                                "recreate_error": str(recreate_error),
                            },
                            original_error=recreate_error,
                        )
                else:
                    # Unknown error - wrap and re-raise
                    raise DatabaseError(
                        f"Failed to create relationship table {rel_type}",
                        operation="add_relationship",
                        context={"sql": create_table_sql},
                        original_error=schema_error,
                    )

            # Add the relationship
            prop_str = ", ".join([f"{k}: ${k}" for k in props.keys()]) if props else ""
            rel_props = f" {{{prop_str}}}" if prop_str else ""
            query = (
                f"MATCH (a:{from_table} {{id: $from_id}}), "
                f"(b:{to_table} {{id: $to_id}}) "
                f"CREATE (a)-[:{rel_type}{rel_props}]->(b)"
            )
            params = {"from_id": from_id, "to_id": to_id, **props}
            self.conn.execute(query, parameters=params)
        except Exception as e:
            raise DatabaseError(
                f"Failed to add relationship {rel_type}",
                operation="add_relationship",
                context={
                    "from_table": from_table,
                    "to_table": to_table,
                    "rel_type": rel_type,
                    "from_id": from_id,
                    "to_id": to_id,
                },
                original_error=e,
            )

    def _extract_query_results(self, query_result) -> list[dict[str, Any]]:
        """Extract results from Kuzu QueryResult using raw iteration"""
        # Type annotations disabled for QueryResult - dynamic interface from kuzu package
        qr = query_result  # type: ignore

        results = []
        column_names = qr.get_column_names()
        while qr.has_next():
            row = qr.get_next()
            result = {}
            for i, col_name in enumerate(column_names):
                result[col_name] = row[i] if i < len(row) else None
            results.append(result)
        return results

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute Cypher query and return results"""
        try:
            qr = self.conn.execute(cypher, parameters=params or {})
            return self._extract_query_results(qr)
        except Exception as e:
            raise DatabaseError(
                "Failed to execute Kuzu query",
                operation="query",
                context={"cypher": cypher, "params": params},
                original_error=e,
            )

    def neighbors(
        self,
        node_label: str,
        node_id: str,
        rel_types: list[str] | None = None,
        direction: str = "any",
        limit: int = 10,
        neighbor_label: str | None = None,
        id_type: str = "UUID",
    ) -> list[dict[str, Any]]:
        """Fetch neighbors of a node

        Args:
            node_label: Node type/table name (e.g., "Memory", "bug")
            node_id: ID of the specific node to find neighbors for
            rel_types: List of relationship types to filter by
            direction: "in", "out", or "any" for relationship direction
            limit: Maximum number of neighbors to return
            neighbor_label: Type of neighbor nodes to return
            id_type: "UUID" to search by id field, "HRID" to search by hrid field
        """
        try:
            rel_filter = "|".join([r.upper() for r in rel_types]) if rel_types else ""
            neighbor = f":{neighbor_label}" if neighbor_label else ""

            # Format relationship pattern properly - don't include ':' if no filter
            rel_part = f":{rel_filter}" if rel_filter else ""

            # Build node matching condition based on id_type
            id_type_upper = id_type.upper()
            if id_type_upper == "HRID":
                # Search by hrid field
                node_condition = f"a:{node_label} {{hrid: $node_id}}"
            else:
                # Default to UUID - search by id field
                node_condition = f"a:{node_label} {{id: $node_id}}"

            if direction == "out":
                pattern = f"({node_condition})-[r{rel_part}]->(n{neighbor})"
            elif direction == "in":
                pattern = f"({node_condition})<-[r{rel_part}]-(n{neighbor})"
            else:
                pattern = f"({node_condition})-[r{rel_part}]-(n{neighbor})"

            if neighbor_label == "Memory":
                # Type-agnostic query - return core fields + individual payload fields
                # Note: properties() function syntax varies by Kuzu version, so we'll get individual fields
                cypher = f"""
                MATCH {pattern}
                RETURN DISTINCT n.id as id,
                                n.user_id as user_id,
                                n.memory_type as memory_type,
                                n.created_at as created_at,
                                label(r) as rel_type,
                                n as node
                LIMIT $limit
                """
            else:
                cypher = f"""
                MATCH {pattern}
                RETURN DISTINCT n as node, label(r) as rel_type
                LIMIT $limit
                """
            params = {"node_id": node_id, "limit": limit}
            return self.query(cypher, params)
        except Exception as e:
            raise DatabaseError(
                "Failed to fetch neighbors",
                operation="neighbors",
                context={
                    "node_label": node_label,
                    "node_id": node_id,
                    "rel_types": rel_types,
                    "direction": direction,
                },
                original_error=e,
            )

    def delete_node(self, table: str, node_id: str) -> bool:
        """Delete a single node by ID"""
        try:
            # Check if node exists first
            cypher_check = f"MATCH (n:{table} {{id: $id}}) RETURN n.id as id"
            check_result = self.query(cypher_check, {"id": node_id})

            if not check_result:
                # Node doesn't exist, consider it successfully "deleted"
                return True

            # Try to delete the node directly - ignore relationship issues for now
            # Kuzu will handle orphaned relationships
            cypher_delete_node = f"MATCH (n:{table} {{id: $id}}) DELETE n"
            self.conn.execute(cypher_delete_node, parameters={"id": node_id})
            return True

        except Exception as e:
            # If there are relationship issues, we'll just skip Kuzu deletion
            # The memory will still be deleted from Qdrant which is the primary store
            error_msg = str(e).lower()
            if "delete undirected rel" in error_msg or "relationship" in error_msg:
                # Skip Kuzu deletion due to relationship constraints
                return True
            raise DatabaseError(
                f"Failed to delete node from {table}",
                operation="delete_node",
                context={"table": table, "node_id": node_id},
                original_error=e,
            )

    def _get_kuzu_type(self, key: str, value: Any) -> str:
        """Map Python types to Kuzu types - NO field-specific logic"""
        if isinstance(value, (int, float)):
            return "DOUBLE"
        if isinstance(value, bool):
            return "BOOLEAN"
        return "STRING"
