#!/usr/bin/env python3
"""Simple Kuzu interface wrapper"""

import os
from typing import Any

from dotenv import load_dotenv
import kuzu


class KuzuInterface:
    """Simple wrapper around Kuzu database"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            load_dotenv()
            db_path = os.getenv("KUZU_DB_PATH")
            if not db_path:
                raise RuntimeError(
                    "KUZU_DB_PATH environment variable must be set! No defaults allowed."
                )

            # Expand $HOME and other variables
            db_path = os.path.expandvars(db_path)

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        # Database already has schema, no setup needed

    def add_node(self, table: str, properties: dict[str, Any]) -> None:
        """Add a node to the graph"""
        # Create table if it doesn't exist with full schema
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
                    last_updated STRING,
                    is_valid BOOLEAN,
                    source_memory_id STRING,
                    importance STRING,
                    context STRING,
                    category STRING,
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
        # Minimal core: no Project table

        props = ", ".join([f"{k}: ${k}" for k in properties])
        query = f"CREATE (:{table} {{{props}}})"
        self.conn.execute(query, parameters=properties)

    def add_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        props: dict = None,
    ) -> None:
        """Add relationship between nodes"""
        props = props or {}

        # Sanitize relationship type name for SQL compatibility
        rel_type = rel_type.replace(" ", "_").replace("-", "_").upper()
        # Remove any other problematic characters
        rel_type = "".join(c for c in rel_type if c.isalnum() or c == "_")

        # Create relationship table if it doesn't exist with proper types
        def get_kuzu_type(key: str, value) -> str:
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

        prop_columns = (
            ", ".join([f"{k} {get_kuzu_type(k, v)}" for k, v in props.items()]) if props else ""
        )
        extra_cols = f", {prop_columns}" if prop_columns else ""

        # Try to create table, if it fails due to schema mismatch, recreate it
        create_table_sql = (
            f"CREATE REL TABLE IF NOT EXISTS {rel_type}"
            f"(FROM {from_table} TO {to_table}{extra_cols})"
        )
        try:
            self.conn.execute(create_table_sql)
        except Exception as schema_error:
            if "type" in str(schema_error).lower():
                # Schema mismatch - drop and recreate table
                try:
                    self.conn.execute(f"DROP TABLE {rel_type}")
                    self.conn.execute(create_table_sql)
                except Exception as drop_error:
                    raise RuntimeError(
                        f"Failed to recreate relationship table {rel_type}"
                    ) from drop_error
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

    def query(self, cypher: str, params: dict = None) -> list[dict[str, Any]]:
        """Execute Cypher query and return results"""
        result = self.conn.execute(cypher, parameters=params or {}).get_as_df()
        return result.to_dict("records") if not result.empty else []

    def neighbors(
        self,
        node_label: str,
        node_id: str,
        rel_types: list[str] | None = None,
        direction: str = "any",
        limit: int = 10,
        neighbor_label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch neighbors of a node with optional relation type filtering and direction.

        direction: 'out', 'in', or 'any'
        rel_types: if provided, only these relationship types are considered
        neighbor_label: restrict neighbor node label and project useful columns when set
        """
        rel_filter = "|".join([r.upper() for r in rel_types]) if rel_types else ""
        neighbor = f":{neighbor_label}" if neighbor_label else ""
        if direction == "out":
            pattern = f"(a:{node_label} {{id: $id}})-[r:{rel_filter}]->(n{neighbor})"
        elif direction == "in":
            pattern = f"(a:{node_label} {{id: $id}})<-[r:{rel_filter}]-(n{neighbor})"
        else:
            pattern = f"(a:{node_label} {{id: $id}})-[r:{rel_filter}]-(n{neighbor})"

        if neighbor_label == "Memory":
            cypher = f"""
            MATCH {pattern}
            RETURN DISTINCT n.id as id,
                            n.user_id as user_id,
                            n.content as content,
                            n.title as title,
                            n.memory_type as memory_type,
                            n.created_at as created_at,
                            type(r) as rel_type
            LIMIT $limit
            """
        else:
            cypher = f"""
            MATCH {pattern}
            RETURN DISTINCT n as node, type(r) as rel_type
            LIMIT $limit
            """
        params = {"id": node_id, "limit": limit}
        return self.query(cypher, params)
