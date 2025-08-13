"""Simple Kuzu interface wrapper - pure I/O operations only"""

import os
from typing import Any

import kuzu

from ..exceptions import DatabaseError


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
        """Add a node to the graph"""
        try:
            # Create table if it doesn't exist (DDL on demand)
            if table == "Entity":
                self.conn.execute(
                    """
                    CREATE NODE TABLE IF NOT EXISTS Entity(
                        id STRING,
                        user_id STRING,
                        name STRING,
                        type STRING,
                        description STRING,
                        confidence DOUBLE,
                        created_at STRING,
                        is_valid BOOLEAN,
                        source_memory_id STRING,
                        PRIMARY KEY (id)
                    )
                """
                )
            elif table == "Memory":
                self.conn.execute(
                    """
                    CREATE NODE TABLE IF NOT EXISTS Memory(
                        id STRING,
                        user_id STRING,
                        content STRING,
                        memory_type STRING,
                        summary STRING,
                        title STRING,
                        source STRING,
                        tags STRING,
                        confidence DOUBLE,
                        is_valid BOOLEAN,
                        created_at STRING,
                        expires_at STRING,
                        supersedes STRING,
                        superseded_by STRING,
                        PRIMARY KEY (id)
                    )
                """
                )

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

            # Sanitize relationship type name for SQL compatibility
            rel_type = rel_type.replace(" ", "_").replace("-", "_").upper()
            rel_type = "".join(c for c in rel_type if c.isalnum() or c == "_")

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
                if "type" in str(schema_error).lower():
                    # Schema mismatch - drop and recreate
                    self.conn.execute(f"DROP TABLE {rel_type}")
                    self.conn.execute(create_table_sql)
                else:
                    raise

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
    ) -> list[dict[str, Any]]:
        """Fetch neighbors of a node"""
        try:
            rel_filter = "|".join([r.upper() for r in rel_types]) if rel_types else ""
            neighbor = f":{neighbor_label}" if neighbor_label else ""

            # Format relationship pattern properly - don't include ':' if no filter
            rel_part = f":{rel_filter}" if rel_filter else ""

            if direction == "out":
                pattern = f"(a:{node_label} {{id: $id}})-[r{rel_part}]->(n{neighbor})"
            elif direction == "in":
                pattern = f"(a:{node_label} {{id: $id}})<-[r{rel_part}]-(n{neighbor})"
            else:
                pattern = f"(a:{node_label} {{id: $id}})-[r{rel_part}]-(n{neighbor})"

            if neighbor_label == "Memory":
                cypher = f"""
                MATCH {pattern}
                RETURN DISTINCT n.id as id,
                                n.user_id as user_id,
                                n.content as content,
                                n.title as title,
                                n.memory_type as memory_type,
                                n.created_at as created_at,
                                label(r) as rel_type
                LIMIT $limit
                """
            else:
                cypher = f"""
                MATCH {pattern}
                RETURN DISTINCT n as node, label(r) as rel_type
                LIMIT $limit
                """
            params = {"id": node_id, "limit": limit}
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

    def _get_kuzu_type(self, key: str, value: Any) -> str:
        """Map Python types to Kuzu types"""
        if key in ["confidence"]:
            return "DOUBLE"
        if key in ["is_valid"]:
            return "BOOLEAN"
        if isinstance(value, (int, float)):
            return "DOUBLE"
        if isinstance(value, bool):
            return "BOOLEAN"
        return "STRING"
