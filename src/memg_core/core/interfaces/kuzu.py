"""Pure CRUD Kuzu interface wrapper - NO DDL operations."""

import re
from typing import Any

import kuzu

from ..exceptions import DatabaseError
from ..types import validate_relation_predicate


class KuzuInterface:
    """Pure CRUD wrapper around Kuzu database - NO DDL operations.

    Attributes:
        conn: Pre-initialized Kuzu connection.
        yaml_translator: Optional YAML translator for relationship operations.
    """

    def __init__(self, connection: kuzu.Connection, yaml_translator=None):
        """Initialize with pre-created connection.

        Args:
            connection: Pre-initialized Kuzu connection from DatabaseClients.
            yaml_translator: Optional YamlTranslator for relationship operations.
        """
        self.conn = connection
        self.yaml_translator = yaml_translator

    def add_node(self, table: str, properties: dict[str, Any]) -> None:
        """Add a node to the graph - pure CRUD operation.

        Args:
            table: Node table name.
            properties: Node properties.

        Raises:
            DatabaseError: If node creation fails.
        """
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
            ) from e

    def update_node(
        self, table: str, node_uuid: str, properties: dict[str, Any], user_id: str
    ) -> bool:
        """Update a node in the graph - pure CRUD operation.

        Args:
            table: Node table name.
            node_uuid: UUID of the node to update.
            properties: Node properties to update.
            user_id: User ID for ownership verification.

        Returns:
            bool: True if update succeeded, False if node not found.

        Raises:
            DatabaseError: If node update fails due to system error.
        """
        try:
            # CRITICAL: Check if node exists AND belongs to user
            check_query = f"MATCH (n:{table} {{id: $uuid, user_id: $user_id}}) RETURN n.id as id"
            check_result = self.query(check_query, {"uuid": node_uuid, "user_id": user_id})

            if not check_result:
                # Node doesn't exist for this user
                return False

            # Build SET clause for properties
            set_clauses = []
            params = {"uuid": node_uuid, "user_id": user_id}

            for key, value in properties.items():
                # Skip system fields that shouldn't be updated via this method
                if key in ("id", "user_id"):
                    continue

                param_name = f"prop_{key}"
                set_clauses.append(f"n.{key} = ${param_name}")
                params[param_name] = value

            if not set_clauses:
                # No properties to update (all were system fields)
                return True

            # Execute update query
            set_clause = ", ".join(set_clauses)
            update_query = f"MATCH (n:{table} {{id: $uuid, user_id: $user_id}}) SET {set_clause}"
            self.conn.execute(update_query, parameters=params)

            return True

        except Exception as e:
            raise DatabaseError(
                f"Failed to update node in {table}",
                operation="update_node",
                context={
                    "table": table,
                    "node_uuid": node_uuid,
                    "properties": properties,
                    "user_id": user_id,
                },
                original_error=e,
            ) from e

    def add_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        user_id: str,
        props: dict[str, Any] | None = None,
    ) -> None:
        """Add relationship between nodes.

        Args:
            from_table: Source node table name.
            to_table: Target node table name.
            rel_type: Relationship type.
            from_id: Source node ID.
            to_id: Target node ID.
            user_id: User ID for ownership verification.
            props: Optional relationship properties.

        Raises:
            DatabaseError: If relationship creation fails.
        """
        try:
            props = props or {}

            # VALIDATE RELATIONSHIP AGAINST YAML SCHEMA - crash if invalid
            if not validate_relation_predicate(rel_type):
                raise ValueError(
                    f"Invalid relationship predicate: {rel_type}. Must be defined in YAML schema."
                )

            # Use relationship type as-is (predicates from YAML) - no sanitization
            # rel_type should already be a valid predicate (e.g., "REFERENCED_BY", "ANNOTATES")

            # CRITICAL: Verify both nodes belong to the user before creating relationship
            # First check if both nodes exist and belong to the user
            check_query = (
                f"MATCH (a:{from_table} {{id: $from_id, user_id: $user_id}}), "
                f"(b:{to_table} {{id: $to_id, user_id: $user_id}}) "
                f"RETURN a.id, b.id"
            )
            check_params = {"from_id": from_id, "to_id": to_id, "user_id": user_id}
            check_result = self.query(check_query, check_params)

            if not check_result:
                raise ValueError(
                    f"Cannot create relationship: one or both memories not found "
                    f"or don't belong to user {user_id}"
                )

            # Generate relationship table name using YamlTranslator
            if not self.yaml_translator:
                raise DatabaseError(
                    "YamlTranslator required for relationship operations",
                    operation="add_relationship",
                    context={
                        "from_table": from_table,
                        "to_table": to_table,
                        "rel_type": rel_type,
                    },
                )

            relationship_table_name = self.yaml_translator.relationship_table_name(
                source=from_table,
                predicate=rel_type,
                target=to_table,
                directed=True,  # Direction affects semantics but not table naming for now
            )

            # Now create the relationship using the unique table name
            prop_str = ", ".join([f"{k}: ${k}" for k in props.keys()]) if props else ""
            rel_props = f" {{{prop_str}}}" if prop_str else ""
            create_query = (
                f"MATCH (a:{from_table} {{id: $from_id, user_id: $user_id}}), "
                f"(b:{to_table} {{id: $to_id, user_id: $user_id}}) "
                f"CREATE (a)-[:{relationship_table_name}{rel_props}]->(b)"
            )
            create_params = {
                "from_id": from_id,
                "to_id": to_id,
                "user_id": user_id,
                **props,
            }
            self.conn.execute(create_query, parameters=create_params)
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
            ) from e

    def delete_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        user_id: str,
    ) -> bool:
        """Delete relationship between nodes.

        Args:
            from_table: Source node table name.
            to_table: Target node table name.
            rel_type: Relationship type.
            from_id: Source node ID.
            to_id: Target node ID.
            user_id: User ID for ownership verification.

        Returns:
            bool: True if deletion succeeded, False if relationship not found.

        Raises:
            DatabaseError: If relationship deletion fails due to system error.
        """
        try:
            # VALIDATE RELATIONSHIP AGAINST YAML SCHEMA - crash if invalid
            if not validate_relation_predicate(rel_type):
                raise ValueError(
                    f"Invalid relationship predicate: {rel_type}. Must be defined in YAML schema."
                )

            # CRITICAL: Verify both nodes belong to the user before deleting relationship
            # First check if both nodes exist and belong to the user
            check_query = (
                f"MATCH (a:{from_table} {{id: $from_id, user_id: $user_id}}), "
                f"(b:{to_table} {{id: $to_id, user_id: $user_id}}) "
                f"RETURN a.id, b.id"
            )
            check_params = {"from_id": from_id, "to_id": to_id, "user_id": user_id}
            check_result = self.query(check_query, check_params)

            if not check_result:
                # Nodes don't exist or don't belong to user - return False (not found)
                return False

            # Generate relationship table name using YamlTranslator
            if not self.yaml_translator:
                raise DatabaseError(
                    "YamlTranslator required for relationship operations",
                    operation="delete_relationship",
                    context={
                        "from_table": from_table,
                        "to_table": to_table,
                        "rel_type": rel_type,
                    },
                )

            relationship_table_name = self.yaml_translator.relationship_table_name(
                source=from_table,
                predicate=rel_type,
                target=to_table,
                directed=True,  # Direction affects semantics but not table naming for now
            )

            # First check if the relationship exists
            check_rel_query = (
                f"MATCH (a:{from_table} {{id: $from_id, user_id: $user_id}})"
                f"-[r:{relationship_table_name}]->"
                f"(b:{to_table} {{id: $to_id, user_id: $user_id}}) "
                f"RETURN r"
            )
            check_rel_params = {"from_id": from_id, "to_id": to_id, "user_id": user_id}

            # Check if relationship exists
            relationship_exists = self.query(check_rel_query, check_rel_params)
            if not relationship_exists:
                # Relationship doesn't exist - return False
                return False

            # Delete the specific relationship (we know it exists)
            delete_query = (
                f"MATCH (a:{from_table} {{id: $from_id, user_id: $user_id}})"
                f"-[r:{relationship_table_name}]->"
                f"(b:{to_table} {{id: $to_id, user_id: $user_id}}) "
                f"DELETE r"
            )
            delete_params = {"from_id": from_id, "to_id": to_id, "user_id": user_id}

            # Execute deletion
            self.conn.execute(delete_query, parameters=delete_params)

            # If we get here, deletion succeeded
            return True

        except Exception as e:
            if isinstance(e, ValueError):
                # Re-raise validation errors as-is
                raise
            raise DatabaseError(
                f"Failed to delete relationship {rel_type}",
                operation="delete_relationship",
                context={
                    "from_table": from_table,
                    "to_table": to_table,
                    "rel_type": rel_type,
                    "from_id": from_id,
                    "to_id": to_id,
                },
                original_error=e,
            ) from e

    def _extract_query_results(self, query_result) -> list[dict[str, Any]]:
        """Extract results from Kuzu QueryResult using raw iteration.

        Args:
            query_result: Kuzu QueryResult object.

        Returns:
            list[dict[str, Any]]: List of dictionaries containing query results.
        """
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
        """Execute Cypher query and return results.

        Args:
            cypher: Cypher query string.
            params: Query parameters.

        Returns:
            list[dict[str, Any]]: Query results.

        Raises:
            DatabaseError: If query execution fails.
        """
        try:
            qr = self.conn.execute(cypher, parameters=params or {})
            return self._extract_query_results(qr)
        except Exception as e:
            raise DatabaseError(
                "Failed to execute Kuzu query",
                operation="query",
                context={"cypher": cypher, "params": params},
                original_error=e,
            ) from e

    def neighbors(
        self,
        node_label: str,
        node_uuid: str,
        user_id: str,
        rel_types: list[str] | None = None,
        direction: str = "any",
        limit: int = 10,
        neighbor_label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch neighbors of a node by UUID only.

        Args:
            node_label: Node type/table name (e.g., "Memory", "bug") - NOT a UUID.
            node_uuid: UUID of the specific node to find neighbors for.
            user_id: User ID for isolation - only return neighbors belonging to this user.
            rel_types: List of relationship types to filter by.
            direction: "in", "out", or "any" for relationship direction.
            limit: Maximum number of neighbors to return.
            neighbor_label: Type of neighbor nodes to return.

        Returns:
            list[dict[str, Any]]: List of neighbor nodes with relationship info.

        Raises:
            ValueError: If node_label is a UUID or node_uuid is not a UUID.
            DatabaseError: If neighbor query fails.
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
            # Use YamlTranslator to expand predicates to concrete relationship labels
            if not self.yaml_translator:
                raise DatabaseError(
                    "YamlTranslator required for neighbor operations",
                    operation="neighbors",
                    context={"node_label": node_label, "rel_types": rel_types},
                )

            # Get concrete relationship labels for this source and predicates
            if rel_types:
                relationship_labels = self.yaml_translator.get_labels_for_predicates(
                    source_type=node_label,
                    predicates=rel_types,
                    neighbor_label=neighbor_label,
                )
                if not relationship_labels:
                    # No matching relationships found - return empty
                    return []

                # Create relationship pattern with specific labels
                rel_filter = "|".join(relationship_labels)
                rel_part = f":{rel_filter}"
            else:
                # No filtering - match all relationships
                rel_part = ""

            # CRITICAL: User isolation - both source node and neighbors must belong to user
            node_condition = f"a:{node_label} {{id: $node_uuid, user_id: $user_id}}"
            neighbor = f":{neighbor_label}" if neighbor_label else ""
            neighbor_condition = f"n{neighbor} {{user_id: $user_id}}"

            # Build direction-aware pattern
            if direction == "out":
                pattern = f"({node_condition})-[r{rel_part}]->({neighbor_condition})"
            elif direction == "in":
                pattern = f"({node_condition})<-[r{rel_part}]-({neighbor_condition})"
            else:
                pattern = f"({node_condition})-[r{rel_part}]-({neighbor_condition})"

            # Return neighbors only if they belong to the same user
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
            params = {"node_uuid": node_uuid, "user_id": user_id, "limit": limit}
            return self.query(cypher, params)
        except Exception as e:
            raise DatabaseError(
                "Failed to fetch neighbors",
                operation="neighbors",
                context={
                    "node_label": node_label,
                    "node_uuid": node_uuid,
                    "user_id": user_id,
                    "rel_types": rel_types,
                    "direction": direction,
                },
                original_error=e,
            ) from e

    def delete_node(self, table: str, node_uuid: str, user_id: str) -> bool:
        """Delete a single node by UUID"""
        try:
            # CRITICAL: Check if node exists AND belongs to user
            cypher_check = f"MATCH (n:{table} {{id: $uuid, user_id: $user_id}}) RETURN n.id as id"
            check_result = self.query(cypher_check, {"uuid": node_uuid, "user_id": user_id})

            if not check_result:
                # Node doesn't exist for this user, consider it successfully "deleted"
                return True

            # Delete the node - only if it belongs to the user
            cypher_delete_node = f"MATCH (n:{table} {{id: $uuid, user_id: $user_id}}) DELETE n"
            self.conn.execute(
                cypher_delete_node, parameters={"uuid": node_uuid, "user_id": user_id}
            )
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
                ) from e
            # Other database error
            raise DatabaseError(
                f"Failed to delete node from {table}",
                operation="delete_node",
                context={"table": table, "node_uuid": node_uuid, "user_id": user_id},
                original_error=e,
            ) from e

    def get_nodes(
        self,
        user_id: str,
        node_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get multiple nodes with filtering and pagination.

        Args:
            user_id: User ID for ownership verification.
            node_type: Optional node type filter (e.g., "task", "note").
            filters: Optional field filters (e.g., {"status": "open"}).
            limit: Maximum number of nodes to return.
            offset: Number of nodes to skip for pagination.

        Returns:
            list[dict[str, Any]]: List of node data from Kuzu.

        Raises:
            DatabaseError: If node retrieval fails.
        """
        try:
            filters = filters or {}

            # Build MATCH clause
            if node_type:
                match_clause = f"MATCH (n:{node_type} {{user_id: $user_id"
            else:
                match_clause = "MATCH (n {user_id: $user_id"

            # Add field filters
            params = {"user_id": user_id, "limit": limit, "offset": offset}
            for field_name, field_value in filters.items():
                param_name = f"filter_{field_name}"
                match_clause += f", {field_name}: ${param_name}"
                params[param_name] = field_value

            match_clause += "})"

            # Build complete query
            cypher_query = f"""
            {match_clause}
            RETURN n.id as id,
                   n.user_id as user_id,
                   n.memory_type as memory_type,
                   n.created_at as created_at,
                   n.updated_at as updated_at,
                   n as node
            ORDER BY n.created_at DESC
            SKIP $offset
            LIMIT $limit
            """

            return self.query(cypher_query, params)

        except Exception as e:
            raise DatabaseError(
                "Failed to get nodes from Kuzu",
                operation="get_nodes",
                context={
                    "user_id": user_id,
                    "node_type": node_type,
                    "filters": filters,
                    "limit": limit,
                    "offset": offset,
                },
                original_error=e,
            ) from e

    def _get_kuzu_type(self, key: str, value: Any) -> str:
        """Map Python types to Kuzu types with proper validation.

        Args:
            key: Property key name.
            value: Property value to type-check.

        Returns:
            str: Kuzu type name.

        Raises:
            DatabaseError: If the Python type is not supported by Kuzu.
        """
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
            value: String to check.

        Returns:
            bool: True if value matches UUID format (8-4-4-4-12 hex pattern), False otherwise.
        """
        if not isinstance(value, str) or len(value) != 36:
            return False

        # UUID format: 8-4-4-4-12 (e.g., 550e8400-e29b-41d4-a716-446655440000)
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(uuid_pattern, value, re.IGNORECASE))
