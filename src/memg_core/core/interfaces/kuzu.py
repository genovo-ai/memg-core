"""Pure CRUD Kuzu interface wrapper - NO DDL operations"""

from typing import Any

import kuzu

from memg_core.core.exceptions import DatabaseError


class KuzuInterface:
    """Pure CRUD wrapper around Kuzu database - NO DDL operations"""

    def __init__(self, connection: kuzu.Connection):
        """Initialize with pre-created connection.

        Args:
            connection: Pre-initialized Kuzu connection from DatabaseClients
        """
        self.conn = connection

    def add_node(self, table: str, properties: dict[str, Any]) -> None:
        """Add a node to the graph - pure CRUD operation"""
        try:
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
        node_uuid: str,
        rel_types: list[str] | None = None,
        direction: str = "any",
        limit: int = 10,
        neighbor_label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch neighbors of a node by UUID only

        Args:
            node_label: Node type/table name (e.g., "Memory", "bug") - NOT a UUID
            node_uuid: UUID of the specific node to find neighbors for
            rel_types: List of relationship types to filter by
            direction: "in", "out", or "any" for relationship direction
            limit: Maximum number of neighbors to return
            neighbor_label: Type of neighbor nodes to return

        Raises:
            ValueError: If node_label is a UUID or node_uuid is not a UUID
        """
        # Validate parameters to prevent common bugs
        if self._is_uuid(node_label):
            raise ValueError(
                f"node_label must be a node type (e.g., 'Memory', 'bug'), not UUID: {node_label}. "
                f"UUIDs should be passed as node_uuid parameter."
            )

        if not self._is_uuid(node_uuid):
            raise ValueError(f"node_uuid must be a valid UUID format, got: {node_uuid}")

        try:
            rel_filter = "|".join([r.upper() for r in rel_types]) if rel_types else ""
            neighbor = f":{neighbor_label}" if neighbor_label else ""

            # Format relationship pattern properly - don't include ':' if no filter
            rel_part = f":{rel_filter}" if rel_filter else ""

            # Simple UUID-only node matching
            node_condition = f"a:{node_label} {{id: $node_uuid}}"

            if direction == "out":
                pattern = f"({node_condition})-[r{rel_part}]->(n{neighbor})"
            elif direction == "in":
                pattern = f"({node_condition})<-[r{rel_part}]-(n{neighbor})"
            else:
                pattern = f"({node_condition})-[r{rel_part}]-(n{neighbor})"

            # Single Memory table - always return structured fields
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
            params = {"node_uuid": node_uuid, "limit": limit}
            return self.query(cypher, params)
        except Exception as e:
            raise DatabaseError(
                "Failed to fetch neighbors",
                operation="neighbors",
                context={
                    "node_label": node_label,
                    "node_uuid": node_uuid,
                    "rel_types": rel_types,
                    "direction": direction,
                },
                original_error=e,
            )

    def delete_node(self, table: str, node_uuid: str) -> bool:
        """Delete a single node by UUID"""
        try:
            # Check if node exists first
            cypher_check = f"MATCH (n:{table} {{id: $uuid}}) RETURN n.id as id"
            check_result = self.query(cypher_check, {"uuid": node_uuid})

            if not check_result:
                # Node doesn't exist, consider it successfully "deleted"
                return True

            # Try to delete the node directly - ignore relationship issues for now
            # Kuzu will handle orphaned relationships
            cypher_delete_node = f"MATCH (n:{table} {{id: $uuid}}) DELETE n"
            self.conn.execute(cypher_delete_node, parameters={"uuid": node_uuid})
            return True

        except Exception as e:
            error_msg = str(e).lower()
            if "delete undirected rel" in error_msg or "relationship" in error_msg:
                # Relationship constraint prevents deletion - this is a REAL FAILURE
                # Don't lie by returning True - raise explicit error
                raise DatabaseError(
                    f"Cannot delete node {node_uuid} from {table}: has existing relationships. "
                    f"Delete relationships first or use CASCADE delete if supported.",
                    operation="delete_node",
                    context={
                        "table": table,
                        "node_uuid": node_uuid,
                        "constraint_error": str(e),
                    },
                    original_error=e,
                )
            # Other database error
            raise DatabaseError(
                f"Failed to delete node from {table}",
                operation="delete_node",
                context={"table": table, "node_uuid": node_uuid},
                original_error=e,
            )

    def _get_kuzu_type(self, key: str, value: Any) -> str:
        """Map Python types to Kuzu types with proper validation"""
        if isinstance(value, bool):
            # Check bool first (bool is subclass of int in Python!)
            return "BOOLEAN"
        if isinstance(value, int):
            return "INT64"
        if isinstance(value, float):
            return "DOUBLE"
        if isinstance(value, str):
            return "STRING"
        if value is None:
            # None values need special handling - default to STRING for now
            return "STRING"
        # Unsupported type - fail explicitly instead of silent STRING conversion
        raise DatabaseError(
            f"Unsupported property type for key '{key}': {type(value).__name__}. "
            f"Supported types: str, int, float, bool. "
            f"Complex types must be serialized before storage.",
            operation="_get_kuzu_type",
            context={"key": key, "value": value, "type": type(value).__name__},
        )

    def _is_uuid(self, value: str) -> bool:
        """Check if string looks like a UUID (36 chars with hyphens in right positions).

        Args:
            value: String to check

        Returns:
            True if value matches UUID format (8-4-4-4-12 hex pattern)
        """
        if not isinstance(value, str) or len(value) != 36:
            return False

        # UUID format: 8-4-4-4-12 (e.g., 550e8400-e29b-41d4-a716-446655440000)
        import re

        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(uuid_pattern, value, re.IGNORECASE))
