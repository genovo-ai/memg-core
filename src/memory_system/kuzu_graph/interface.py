#!/usr/bin/env python3
"""Simple Kuzu interface wrapper"""

import os
from typing import Any, Dict, List

import kuzu
from dotenv import load_dotenv


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

    def add_node(self, table: str, properties: Dict[str, Any]) -> bool:
        """Add a node to the graph"""
        try:
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
                        project_id STRING,
                        project_name STRING,
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
            elif table == "Project":
                self.conn.execute(
                    """
                    CREATE NODE TABLE IF NOT EXISTS Project(
                        id STRING,
                        user_id STRING,
                        name STRING,
                        description STRING,
                        created_at STRING,
                        last_used STRING,
                        is_active BOOLEAN,
                        PRIMARY KEY (id)
                    )
                """
                )

            props = ", ".join([f"{k}: ${k}" for k in properties.keys()])
            query = f"CREATE (:{table} {{{props}}})"
            self.conn.execute(query, parameters=properties)
            return True
        except Exception as e:
            print(f"❌ add_node error: {e}")
            return False

    def add_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        props: Dict = None,
    ) -> bool:
        """Add relationship between nodes"""
        try:
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
                elif key in ["is_valid"]:
                    return "BOOLEAN"
                elif isinstance(value, (int, float)):
                    return "DOUBLE"
                elif isinstance(value, bool):
                    return "BOOLEAN"
                else:
                    return "STRING"

            prop_columns = (
                ", ".join([f"{k} {get_kuzu_type(k, v)}" for k, v in props.items()]) if props else ""
            )
            extra_cols = f", {prop_columns}" if prop_columns else ""

            # Try to create table, if it fails due to schema mismatch, recreate it
            create_table_sql = f"CREATE REL TABLE IF NOT EXISTS {rel_type}(FROM {from_table} TO {to_table}{extra_cols})"
            try:
                self.conn.execute(create_table_sql)
            except Exception as schema_error:
                if "type" in str(schema_error).lower():
                    # Schema mismatch - drop and recreate table
                    print(f"🔧 Recreating relationship table {rel_type} due to schema mismatch")
                    try:
                        self.conn.execute(f"DROP TABLE {rel_type}")
                        self.conn.execute(create_table_sql)
                    except Exception as drop_error:
                        print(f"❌ Failed to recreate table {rel_type}: {drop_error}")
                        raise
                else:
                    raise

            # Add the relationship
            prop_str = ", ".join([f"{k}: ${k}" for k in props.keys()]) if props else ""
            rel_props = f" {{{prop_str}}}" if prop_str else ""
            query = f"MATCH (a:{from_table} {{id: $from_id}}), (b:{to_table} {{id: $to_id}}) CREATE (a)-[:{rel_type}{rel_props}]->(b)"
            params = {"from_id": from_id, "to_id": to_id, **props}
            self.conn.execute(query, parameters=params)
            return True
        except Exception as e:
            print(f"❌ add_relationship error: {e}")
            return False

    def query(self, cypher: str, params: Dict = None) -> List[Dict[str, Any]]:
        """Execute Cypher query and return results"""
        try:
            result = self.conn.execute(cypher, parameters=params or {}).get_as_df()
            return result.to_dict("records") if not result.empty else []
        except Exception:
            return []
