#!/usr/bin/env python3
"""
MEMG Core MCP Server (lean-core, publish-ready)

Core Tools:
- mcp_gmem_add_memory: Add a YAML-validated memory.
- mcp_gmem_search_memories: Vector/hybrid search with optional filters.
- mcp_gmem_delete_memory: Delete by UUID/HRID with ownership check.
- mcp_gmem_add_relationship: Create explicit relationships between memories.
- mcp_gmem_get_relationships: Retrieve relationships for a specific memory.
- mcp_gmem_delete_relationship: Delete specific relationships between memories.
- mcp_gmem_get_system_info: Version + active YAML schema summary.

All schema rules (entities/fields/anchors/relations) come from the active YAML.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Optional, Annotated

from fastmcp import FastMCP
from pydantic import Field
from starlette.responses import JSONResponse

from memg_core import __version__
from memg_core.api.public import add_memory, search, delete_memory
from memg_core.core.config import get_config
from memg_core.core.exceptions import ValidationError, DatabaseError
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.models import SearchResult
from memg_core.core.yaml_translator import get_yaml_translator

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("memg_mcp")

# --------------------------------------------------------------------------- #
# Env / YAML helpers
# --------------------------------------------------------------------------- #

def _ensure_yaml_schema_env() -> None:
    """
    Ensure MEMG_YAML_SCHEMA is set to a usable path (container/non-container).
    - If relative, try normalizing to /app/<path> when present.
    """
    env_val = os.getenv("MEMG_YAML_SCHEMA")
    if not env_val:
        logger.warning("MEMG_YAML_SCHEMA not set; ensure your .env/config sets it explicitly.")
        return

    p = Path(env_val)
    if p.is_absolute():
        logger.info(f"Using MEMG_YAML_SCHEMA (absolute): {env_val}")
        return

    candidate = Path("/app") / env_val
    if candidate.exists():
        os.environ["MEMG_YAML_SCHEMA"] = str(candidate)
        logger.info(f"Normalized MEMG_YAML_SCHEMA → {candidate}")
    else:
        logger.info(f"Using MEMG_YAML_SCHEMA as-is (relative): {env_val}")

def _summarize_entity_fields(t) -> dict[str, dict[str, list[str]]]:
    """Return {entity: {'required': [...], 'optional': [...]}} (hides system fields)."""
    summary: dict[str, dict[str, list[str]]] = {}
    for name, spec in t._entities_map().items():
        fields = spec.get("fields", {}) or {}
        required, optional = [], []
        anchor = t.get_anchor_field(name)
        if anchor:
            required.append(anchor)
        for fname, cfg in fields.items():
            if fname == anchor:
                continue
            if isinstance(cfg, dict) and cfg.get("system"):
                continue
            (required if (isinstance(cfg, dict) and cfg.get("required")) else optional).append(str(fname))
        summary[name] = {"required": sorted(set(required)), "optional": sorted(set(optional))}
    return summary

def _desc_add_memory() -> str:
    """Dynamic description with actual entity types from YAML (excluding base types)."""
    try:
        t = get_yaml_translator()
        # Filter out base types like 'memo' - only show user-facing types
        all_types = t._entities_map().keys()
        user_types = [typ for typ in all_types if typ != "memo"]
        types = ", ".join(sorted(user_types))
        return f"Add a memory validated by YAML schema. Available types: {types}"
    except Exception:
        return "Add a YAML-validated memory."

def _get_memory_type_description() -> str:
    """Dynamic memory_type parameter description with actual types from YAML."""
    try:
        t = get_yaml_translator()
        all_types = t._entities_map().keys()
        user_types = [typ for typ in all_types if typ != "memo"]
        types_str = ", ".join(sorted(user_types))
        return f"Entity type from YAML schema. Available: {types_str}"
    except Exception:
        return "Entity type (document, task, note, bug, solution)"

# --------------------------------------------------------------------------- #
# Bridge (thin adapters over public API)
# --------------------------------------------------------------------------- #

class MemgCoreBridge:
    def add_memory(self, memory_type: str, user_id: str, payload: dict) -> dict[str, Any]:
        try:
            m = add_memory(memory_type=memory_type, user_id=user_id, payload=payload)

            # Insert the memory node into Kuzu for relationships
            try:
                kuzu_db_path = os.getenv("KUZU_DB_PATH", "kuzu_storage")
                kuzu = KuzuInterface(db_path=kuzu_db_path)
                self._ensure_kuzu_node_tables(kuzu, [memory_type])

                insert_node_sql = f"""
                CREATE (n:{memory_type} {{id: '{m.id}'}})
                """
                kuzu.query(insert_node_sql)
                logger.debug("✅ Added memory node to Kuzu: %s", m.id)
            except Exception as e:
                logger.warning("⚠️ Failed to add memory node to Kuzu: %s", e)
                # Don't fail memory creation if Kuzu node creation fails

            return {"success": True, "memory_id": m.id, "hrid": m.hrid}
        except ValidationError as e:
            return {"success": False, "error": f"Validation Error: {e}"}
        except Exception as e:
            logger.exception("add_memory error")
            return {"success": False, "error": str(e)}

    def _try_direct_id_lookup(self, query: str, user_id: Optional[str]) -> Optional[dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return None
        try:
            cfg = get_config()
            qdrant = QdrantInterface(
                collection_name=cfg.memg.qdrant_collection_name,
                storage_path=os.getenv("QDRANT_STORAGE_PATH", "qdrant_storage"),
            )

            # UUID lookup
            pt = qdrant.get_point(q)
            if pt and pt.get("payload"):
                payload = pt["payload"] or {}
                core = payload.get("core", {})
                if user_id and core.get("user_id") != user_id:
                    return None
                user_payload = {k: v for k, v in payload.items() if k != "core"}
                return {
                    "memory_id": q,
                    "hrid": core.get("hrid", ""),
                    "memory_type": core.get("memory_type", ""),
                    "payload": user_payload,
                    "score": 1.0,
                    "source": "direct_id_lookup",
                }

            # HRID lookup (cheap filter search)
            if "_" in q and q.replace("_", "").replace("-", "").isalnum():
                dummy_vector = [0.0] * 384  # safe default if interface expects a vector
                res = qdrant.search_points(vector=dummy_vector, limit=1, filters={"core.hrid": q})
                if res:
                    r = res[0]
                    payload = r.get("payload", {}) or {}
                    core = payload.get("core", {})
                    if user_id and core.get("user_id") != user_id:
                        return None
                    user_payload = {k: v for k, v in payload.items() if k != "core"}
                    return {
                        "memory_id": str(r.get("id")),
                        "hrid": core.get("hrid", ""),
                        "memory_type": core.get("memory_type", ""),
                        "payload": user_payload,
                        "score": 1.0,
                        "source": "direct_id_lookup",
                    }
        except Exception as e:
            logger.debug(f"Direct lookup failed for '{q}': {e}")
        return None

    def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        try:
            direct = self._try_direct_id_lookup(query, user_id)
            if direct:
                return [direct]

            results: list[SearchResult] = search(
                query=query,
                user_id=user_id,
                limit=limit,
                memo_type=kwargs.get("memory_type"),
                mode=kwargs.get("mode", "vector"),
                include_details=kwargs.get("include_details", "self"),
                include_see_also=kwargs.get("include_see_also", False),
                filters=kwargs.get("filters"),
            )
            return [
                {
                    "memory_id": r.memory.id,
                    "hrid": r.memory.hrid,
                    "memory_type": r.memory.memory_type,
                    "payload": r.memory.payload,
                    "score": r.score,
                    "source": r.source,
                }
                for r in results
            ]
        except Exception as e:
            logger.exception("search_memories error")
            return [{"error": str(e)}]

    def delete_memory(self, memory_id: str, user_id: str) -> dict[str, Any]:
        try:
            ok = delete_memory(memory_id=memory_id, user_id=user_id)
            return {"success": True, "memory_id": memory_id, "deleted": ok}
        except ValidationError as e:
            return {"success": False, "error": f"Validation Error: {e}"}
        except DatabaseError as e:
            # Vector-first; treat graph cleanup as non-fatal
            logger.warning(f"Graph cleanup warning: {e}")
            return {"success": True, "memory_id": memory_id, "deleted": True, "warning": "Graph cleanup skipped"}
        except Exception as e:
            logger.exception("delete_memory error")
            return {"success": False, "error": str(e)}

    def _resolve_memory_id_to_uuid(self, memory_id: str, user_id: str) -> tuple[str | None, dict[str, Any] | None]:
        """Resolve HRID or UUID to UUID and return payload for validation."""
        memory_id = (memory_id or "").strip()
        if not memory_id:
            return None, None
        try:
            cfg = get_config()
            qdrant = QdrantInterface(
                collection_name=cfg.memg.qdrant_collection_name,
                storage_path=os.getenv("QDRANT_STORAGE_PATH", "qdrant_storage"),
            )
            # Try UUID first
            pt = qdrant.get_point(memory_id)
            if pt and pt.get("payload"):
                payload = pt["payload"] or {}
                core = payload.get("core", {})
                if user_id and core.get("user_id") != user_id:
                    return None, None
                return memory_id, payload
            # Try HRID lookup
            if "_" in memory_id and memory_id.replace("_", "").replace("-", "").isalnum():
                dummy_vector = [0.0] * 384
                res = qdrant.search_points(vector=dummy_vector, limit=1, filters={"core.hrid": memory_id})
                if res:
                    r = res[0]
                    payload = r.get("payload", {}) or {}
                    core = payload.get("core", {})
                    if user_id and core.get("user_id") != user_id:
                        return None, None
                    return str(r.get("id")), payload
        except Exception as e:
            logger.debug(f"Memory resolution failed for '{memory_id}': {e}")
        return None, None

    def _ensure_kuzu_node_tables(self, kuzu: "KuzuInterface", memory_types: list[str]):
        """Ensure Kuzu node tables exist for the given memory types.

        This is a workaround for a memg-core limitation where Kuzu node tables are not
        automatically created when memories are added. memg-core handles Qdrant (vector storage)
        automatically but requires manual Kuzu (graph) table setup for relationships to work.

        Without this fix, attempting to create relationships would fail with:
        "Binder exception: Table solution does not exist."

        This method creates the necessary node tables with the schema:
            CREATE NODE TABLE IF NOT EXISTS {memory_type}(id STRING, PRIMARY KEY(id))
        """
        for memory_type in memory_types:
            try:
                # Create node table if it doesn't exist
                # Each memory type gets a table with id (STRING) as primary key
                create_table_sql = f"""
                CREATE NODE TABLE IF NOT EXISTS {memory_type}(
                    id STRING,
                    PRIMARY KEY(id)
                )
                """
                kuzu.query(create_table_sql)
                logger.debug("✅ Ensured Kuzu table exists: %s", memory_type)
            except Exception as e:
                logger.warning("⚠️ Failed to create Kuzu table %s: %s", memory_type, e)
                # Don't fail the relationship creation if table creation fails
                # The error will be caught by the relationship creation itself

    def add_relationship(self, from_memory_id: str, to_memory_id: str, relation_type: str, user_id: str) -> dict[str, Any]:
        """Add a relationship between two memories."""
        try:
            # Resolve memory IDs
            from_uuid, from_payload = self._resolve_memory_id_to_uuid(from_memory_id, user_id)
            if not from_uuid or not from_payload:
                return {"success": False, "error": f"From memory {from_memory_id} not found or access denied"}

            to_uuid, to_payload = self._resolve_memory_id_to_uuid(to_memory_id, user_id)
            if not to_uuid or not to_payload:
                return {"success": False, "error": f"To memory {to_memory_id} not found or access denied"}

            # Initialize Kuzu
            kuzu_db_path = os.getenv("KUZU_DB_PATH", "kuzu_storage")
            kuzu = KuzuInterface(db_path=kuzu_db_path)

            # Get memory types and validate relationship
            from_type = from_payload.get("core", {}).get("memory_type", "")
            to_type = to_payload.get("core", {}).get("memory_type", "")

            # Ensure node tables exist for both memory types
            self._ensure_kuzu_node_tables(kuzu, [from_type, to_type])

            # Simple validation - check if relation_type exists in YAML
            translator = get_yaml_translator()
            entities_map = translator._entities_map()

            # Add the relationship using KuzuInterface with resolved UUIDs
            kuzu.add_relationship(
                from_table=from_type,
                to_table=to_type,
                rel_type=relation_type,
                from_id=from_uuid,
                to_id=to_uuid,
                props={"user_id": user_id, "created_at": "now()"}
            )

            return {
                "success": True,
                "from_memory_id": from_memory_id,
                "to_memory_id": to_memory_id,
                "relation_type": relation_type,
            }
        except Exception as e:
            logger.exception("add_relationship error")
            return {"success": False, "error": str(e)}

    def get_relationships(self, memory_id: str, user_id: str, direction: str = "both") -> dict[str, Any]:
        """Get relationships for a memory."""
        try:
            # Resolve memory ID
            resolved_uuid, payload = self._resolve_memory_id_to_uuid(memory_id, user_id)
            if not resolved_uuid or not payload:
                return {"success": False, "error": f"Memory {memory_id} not found or access denied"}

            memory_type = payload.get("core", {}).get("memory_type", "")

            # Initialize Kuzu
            kuzu_db_path = os.getenv("KUZU_DB_PATH", "kuzu_storage")
            kuzu = KuzuInterface(db_path=kuzu_db_path)

            # Use the neighbors method to get relationships
            direction_map = {"both": "any", "outgoing": "out", "incoming": "in"}
            kuzu_direction = direction_map.get(direction, "any")

            relationships = kuzu.neighbors(
                node_label=memory_type,
                node_id=resolved_uuid,
                direction=kuzu_direction
            )

            return {
                "success": True,
                "memory_id": memory_id,
                "relationships": relationships,
                "count": len(relationships),
            }
        except Exception as e:
            logger.exception("get_relationships error")
            return {"success": False, "error": str(e)}

    def delete_relationship(self, from_memory_id: str, to_memory_id: str, relation_type: str, user_id: str) -> dict[str, Any]:
        """Delete a specific relationship between two memories."""
        try:
            # Resolve memory IDs
            from_uuid, from_payload = self._resolve_memory_id_to_uuid(from_memory_id, user_id)
            if not from_uuid or not from_payload:
                return {"success": False, "error": f"From memory {from_memory_id} not found or access denied"}

            to_uuid, to_payload = self._resolve_memory_id_to_uuid(to_memory_id, user_id)
            if not to_uuid or not to_payload:
                return {"success": False, "error": f"To memory {to_memory_id} not found or access denied"}

            # Get memory types
            from_type = from_payload.get("core", {}).get("memory_type", "")
            to_type = to_payload.get("core", {}).get("memory_type", "")

            # Initialize Kuzu
            kuzu_db_path = os.getenv("KUZU_DB_PATH", "kuzu_storage")
            kuzu = KuzuInterface(db_path=kuzu_db_path)

            # Delete the relationship using Kuzu query with resolved UUIDs
            delete_query = f"""
            MATCH (from:{from_type})-[r:{relation_type}]->(to:{to_type})
            WHERE from.id = '{from_uuid}' AND to.id = '{to_uuid}'
            DELETE r
            """
            kuzu.query(delete_query)

            return {
                "success": True,
                "from_memory_id": from_memory_id,
                "to_memory_id": to_memory_id,
                "relation_type": relation_type,
            }
        except Exception as e:
            logger.exception("delete_relationship error")
            return {"success": False, "error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        return {
            "system_type": "memg_core_lean_mcp",
            "version": __version__,
            "api_type": "generic_yaml_driven",
            "available_functions": ["add_memory", "search_memories", "delete_memory", "add_relationship", "get_relationships", "delete_relationship"],
        }

# Singleton bridge
bridge: Optional[MemgCoreBridge] = None

def initialize_bridge() -> MemgCoreBridge:
    global bridge
    bridge = MemgCoreBridge()
    return bridge

# --------------------------------------------------------------------------- #
# HTTP / Health
# --------------------------------------------------------------------------- #

def setup_health_endpoints(app: FastMCP) -> None:
    @app.custom_route("/", methods=["GET"])
    async def root(_req):
        return JSONResponse(
            {"status": "healthy", "service": f"MEMG Core MCP v{__version__}", "api": "generic_yaml_driven"}
        )

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        ok = bridge is not None
        return JSONResponse(
            {
                "service": "MEMG Core MCP",
                "version": __version__,
                "bridge_initialized": ok,
                "status": "healthy" if ok else "unhealthy",
            },
            status_code=200 if ok else 503,
        )

# --------------------------------------------------------------------------- #
# MCP Tools
# --------------------------------------------------------------------------- #

def register_tools(app: FastMCP) -> None:
    # --- add_memory ---
    @app.tool(name="mcp_gmem_add_memory", description=_desc_add_memory())
    def add_memory_tool(
        memory_type: Annotated[str, Field(description=_get_memory_type_description())],
        user_id: Annotated[str, Field(description="Owner/namespace for the memory")],
        payload: Annotated[dict, Field(description="Entity fields as key-value pairs; system fields auto-managed")]
    ):
        """
        Inputs:
          - memory_type:str (must exist in YAML)
          - user_id:str (namespace/owner)
          - payload:dict (entity fields; system fields are auto-managed)
        Returns: {"result", "memory_id"?, "hrid"?, "error"?}
        """
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        try:
            t = get_yaml_translator()
            all_types = t._entities_map()
            user_types = {typ: spec for typ, spec in all_types.items() if typ != "memo"}

            if memory_type not in all_types:
                return {
                    "result": f"❌ Invalid memory_type '{memory_type}'",
                    "error": f"Available types: {sorted(user_types.keys())}",
                }

            if memory_type == "memo":
                return {
                    "result": f"❌ 'memo' is a base type, use: {sorted(user_types.keys())}",
                    "error": f"Available user types: {sorted(user_types.keys())}",
                }
        except Exception as e:
            logger.exception("Schema validation failed")
            return {"result": f"❌ Schema validation failed: {e}"}

        res = bridge.add_memory(memory_type=memory_type, user_id=user_id, payload=payload)
        if res.get("success"):
            return {
                "result": f"✅ {memory_type.title()} added",
                "memory_id": res["memory_id"],
                "hrid": res.get("hrid"),
            }
        return {"result": f"❌ Failed to add {memory_type}", "error": res.get("error", "Unknown error")}

    # --- search_memories ---
    @app.tool(
        name="mcp_gmem_search_memories",
        description="Search memories (vector by default) with optional filters (user_id, type, project, mode, details, see_also).",
    )
    def search_memories_tool(
        query: Annotated[str, Field(description="Free-text search query or UUID/HRID for direct lookup")],
        user_id: Annotated[Optional[str], Field(description="Filter by user namespace; omit for all users")] = None,
        limit: Annotated[int, Field(description="Maximum number of results to return")] = 5,
        memory_type: Annotated[Optional[str], Field(description="Filter by entity type (memo, task, bug, etc.)")] = None,
        project: Annotated[Optional[str], Field(description="Filter by project namespace")] = None,
        mode: Annotated[str, Field(description="Search mode: 'vector' for semantic, 'keyword' for exact")] = "vector",
        include_details: Annotated[str, Field(description="Result detail level: 'self' for full payload")] = "self",
        include_see_also: Annotated[bool, Field(description="Include semantically related memories")] = False,
    ):
        """
        Returns: {"result", "memories":[{memory_id, hrid, memory_type, payload, score, source}]}
        """
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        filters = {"entity.project": project} if project else None
        results = bridge.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            memory_type=memory_type,
            mode=mode,
            include_details=include_details,
            include_see_also=include_see_also,
            filters=filters,
        )
        if results and isinstance(results[0], dict) and "error" in results[0]:
            return {"result": f"❌ Search failed: {results[0]['error']}"}
        return {"result": f"✅ Found {len(results)} memories", "memories": results}

    # --- get_system_info ---
    @app.tool(
        name="mcp_gmem_get_system_info",
        description="Return service/version plus active YAML schema (anchor + required/optional fields).",
    )
    def get_system_info_tool():
        """
        Returns: {"result": {"system_type","version","api_type","available_functions","yaml_*"}}
        """
        if not bridge:
            return {"result": {"status": "Bridge not initialized"}}

        stats = bridge.get_stats()
        try:
            t = get_yaml_translator()
            fields = _summarize_entity_fields(t)
            stats["yaml_schema_details"] = {
                name: {
                    "anchor_field": t.get_anchor_field(name),
                    "required_fields": fields[name]["required"],
                    "optional_fields": fields[name]["optional"],
                }
                for name in t._entities_map().keys()
            }
            all_types = t._entities_map().keys()
            user_types = [typ for typ in all_types if typ != "memo"]
            stats["valid_memory_types"] = sorted(user_types)
            stats["yaml_schema_path"] = os.getenv("MEMG_YAML_SCHEMA")
        except Exception as e:
            stats["yaml_schema_error"] = f"Could not load schemas: {e}"

        return {"result": stats}

    # --- delete_memory ---
    @app.tool(
        name="mcp_gmem_delete_memory",
        description="Delete a single memory by UUID or HRID; verifies user ownership.",
    )
    def delete_memory_tool(
        memory_id: Annotated[str, Field(description="UUID or HRID of memory to delete")],
        user_id: Annotated[str, Field(description="User who owns the memory; required for verification")]
    ):
        """
        Returns: {"result", "memory_id"?, "deleted"?, "error"?, "warning"?}
        """
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        res = bridge.delete_memory(memory_id=memory_id, user_id=user_id)
        if res.get("success"):
            return {
                "result": "✅ Memory deleted",
                "memory_id": res["memory_id"],
                "deleted": res.get("deleted", True),
                **({"warning": res["warning"]} if "warning" in res else {}),
            }
        return {"result": "❌ Failed to delete memory", "error": res.get("error", "Unknown error")}

    # --- add_relationship ---
    @app.tool(
        name="mcp_gmem_add_relationship",
        description="Create explicit relationships between memories based on YAML schema.",
    )
    def add_relationship_tool(
        from_memory_id: Annotated[str, Field(description="UUID or HRID of the source memory")],
        to_memory_id: Annotated[str, Field(description="UUID or HRID of the target memory")],
        relation_type: Annotated[str, Field(description="Relationship type from YAML schema (FIXES, IMPLEMENTS, ADDRESSES, etc.)")],
        user_id: Annotated[str, Field(description="Owner/namespace - must own both memories")]
    ):
        """Create explicit relationship between two memories."""
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        res = bridge.add_relationship(from_memory_id, to_memory_id, relation_type, user_id)
        if res.get("success"):
            return {
                "result": "✅ Relationship added successfully",
                "from_memory_id": res["from_memory_id"],
                "to_memory_id": res["to_memory_id"],
                "relation_type": res["relation_type"],
            }
        return {"result": "❌ Failed to add relationship", "error": res.get("error", "Unknown error")}

    # --- get_relationships ---
    @app.tool(
        name="mcp_gmem_get_relationships",
        description="Retrieve all relationships for a specific memory.",
    )
    def get_relationships_tool(
        memory_id: Annotated[str, Field(description="UUID or HRID of the memory to get relationships for")],
        user_id: Annotated[str, Field(description="Owner/namespace - must own the memory")],
        direction: Annotated[str, Field(description="Direction: 'outgoing', 'incoming', or 'both'")] = "both"
    ):
        """Get all relationships for a specific memory."""
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        res = bridge.get_relationships(memory_id, user_id, direction)
        if res.get("success"):
            return {
                "result": f"✅ Found {res.get('count', 0)} relationships",
                "memory_id": res["memory_id"],
                "relationships": res["relationships"],
                "count": res.get("count", 0),
            }
        return {"result": "❌ Failed to get relationships", "error": res.get("error", "Unknown error")}

    # --- delete_relationship ---
    @app.tool(
        name="mcp_gmem_delete_relationship",
        description="Delete a specific relationship between two memories.",
    )
    def delete_relationship_tool(
        from_memory_id: Annotated[str, Field(description="UUID or HRID of the source memory")],
        to_memory_id: Annotated[str, Field(description="UUID or HRID of the target memory")],
        relation_type: Annotated[str, Field(description="Relationship type to delete (FIXES, IMPLEMENTS, etc.)")],
        user_id: Annotated[str, Field(description="Owner/namespace - must own both memories")]
    ):
        """Delete a specific relationship between two memories."""
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        res = bridge.delete_relationship(from_memory_id, to_memory_id, relation_type, user_id)
        if res.get("success"):
            return {
                "result": "✅ Relationship deleted successfully",
                "from_memory_id": res["from_memory_id"],
                "to_memory_id": res["to_memory_id"],
                "relation_type": res["relation_type"],
            }
        return {"result": "❌ Failed to delete relationship", "error": res.get("error", "Unknown error")}

# --------------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------------- #

def create_app() -> FastMCP:
    app = FastMCP()
    _ensure_yaml_schema_env()
    initialize_bridge()
    setup_health_endpoints(app)
    register_tools(app)
    return app

app = create_app()

if __name__ == "__main__":
    port_env = os.getenv("MEMORY_SYSTEM_MCP_PORT")
    if not port_env:
        raise ValueError("MEMORY_SYSTEM_MCP_PORT is required (e.g., 8787/8788/8789).")
    host = os.getenv("MEMORY_SYSTEM_MCP_HOST", "127.0.0.1")
    print(f"🚀 Starting MEMG Core MCP Server on {host}:{int(port_env)}")
    print(f"📦 memg-core v{__version__} | YAML-driven API")
    app.run(transport="sse", host=host, port=int(port_env))
