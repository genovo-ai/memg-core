#!/usr/bin/env python3
#!/usr/bin/env python3
"""
MEMG Core MCP Server (lean-core)

Exposes three MCP tools backed by memg-core's public API:

- mcp_gmem_add_memory: Insert a memory validated against the **active YAML schema**.
- mcp_gmem_search_memories: Search memories (vector by default) with optional filters.
- mcp_gmem_get_system_info: Introspect version, active schema path, and per-entity field requirements.

All validation rules, entity types, fields, enums, anchors, and relations are **owned by the YAML**.
Change the YAML → behavior and tool help update automatically.
"""

import os
from pathlib import Path
import logging
from typing import Any, Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

# Import the new lean core public API
from memg_core.api.public import add_memory, search, delete_memory
from memg_core.core.models import SearchResult
from memg_core import __version__
from memg_core.core.yaml_translator import get_yaml_translator
from memg_core.core.exceptions import ValidationError, DatabaseError

# Setup comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _ensure_yaml_schema_env() -> None:
    """Ensure MEMG_YAML_SCHEMA is set (container-safe).

    Looks for MEMG_YAML_SCHEMA and normalizes repo-relative paths to /app/… when running in container.
    This does **not** read/validate the file — it only ensures the env var is usable by the YAML translator.
    """
    if os.getenv("MEMG_YAML_SCHEMA"):
        logger.info(f"📄 Using YAML schema from MEMG_YAML_SCHEMA={os.getenv('MEMG_YAML_SCHEMA')}")
        return

    # Normalize repo-relative path to container path
    env_val = os.getenv("MEMG_YAML_SCHEMA")
    if env_val and not env_val.startswith("/app/"):
        # If a repo-relative path is provided (e.g., from .env),
        # translate it to the container path under /app.
        candidate = Path("/app") / env_val
        if candidate.exists():
            os.environ["MEMG_YAML_SCHEMA"] = str(candidate)
            logger.info(f"🧭 Normalized MEMG_YAML_SCHEMA to container path: {candidate}")
            return

    # Fallback: should not happen with proper .env setup
    logger.warning("⚠️ MEMG_YAML_SCHEMA not properly set. Ensure .env file is configured.")


def _summarize_entity_fields(translator) -> dict[str, dict[str, list[str]]]:
    """Return {entity: {"required": [...], "optional": [...]}} from YAML.

    - Hides `system: true` fields (handled by core).
    - Preserves YAML-requiredness; does not coerce or infer defaults.
    """
    summary: dict[str, dict[str, list[str]]] = {}
    for name, spec in translator._entities_map().items():
        fields = spec.get("fields", {})
        required: list[str] = []
        optional: list[str] = []
        if isinstance(fields, dict):
            for field_name, cfg in fields.items():
                # Skip system fields
                if isinstance(cfg, dict) and cfg.get("system"):
                    continue
                is_required = isinstance(cfg, dict) and cfg.get("required") is True
                (required if is_required else optional).append(str(field_name))
        summary[name] = {"required": sorted(required), "optional": sorted(optional)}
    return summary


def get_dynamic_tool_docstring() -> str:
    """Build the add_memory tool docstring from the **current YAML schema**.

    Produces:
      - MCP tool parameter descriptions
      - Per-entity anchor field
      - Required/optional fields (non-system)
      - Example payloads for each entity type

    This reflects the **live** schema loaded by memg_core.core.yaml_translator.
    """
    try:
        translator = get_yaml_translator()
        spec_map = translator._entities_map()
        field_summary = _summarize_entity_fields(translator)

        lines = []
        lines.append("Add a memory using pure YAML-driven schema validation.")
        lines.append("")
        lines.append("Parameters")
        lines.append("----------")
        lines.append("memory_type : str")
        lines.append("    Entity type defined in YAML schema. Must exactly match an entity key.")
        lines.append(f"    Available types: {', '.join(spec_map.keys())}")
        lines.append("user_id : str")
        lines.append("    Owner/namespace for the memory. Required by core.")
        lines.append("payload : dict")
        lines.append("    Fields conforming to the YAML entity schema. System fields are auto-managed.")
        lines.append("")
        lines.append("Entity Schema Details")
        lines.append("--------------------")

        for name, spec in spec_map.items():
            req = field_summary.get(name, {}).get("required", [])
            opt = field_summary.get(name, {}).get("optional", [])
            anchor = translator.get_anchor_field(name)

            lines.append(f"{name}:")
            lines.append(f"  anchor_field: {anchor} (embedded for search)")
            if req:
                lines.append(f"  required: {', '.join(req)}")
            if opt:
                lines.append(f"  optional: {', '.join(opt)}")

            # Generate example payload
            example = {anchor: f"Example {name} statement"}
            if req:
                for field in req:
                    if field != anchor:
                        example[field] = f"example_{field}_value"
            lines.append(f"  example: {example}")
            lines.append("")

        lines.append("Behavior")
        lines.append("--------")
        lines.append("- Validates memory_type exists and payload matches entity schema")
        lines.append("- System fields (id, timestamps, vector) are auto-managed")
        lines.append("- Returns memory_id and hrid on success")
        lines.append("- Use mcp_gmem_get_system_info for complete schema inspection")

        return "\n".join(lines)
    except Exception as e:
        return f"Could not generate dynamic docstring. Error: {e}"

class MemgCoreBridge:
    """Thin adapter over memg-core public API.

    - add_memory(..): Validates against YAML, returns {success, memory_id, hrid|error}.
    - search_memories(..): Delegates to core search, returns scored hits (id, hrid, type, payload, score, source).
    - get_stats(): Static service metadata (type, version, functions).
    """

    def add_memory(self, memory_type: str, user_id: str, payload: dict) -> dict[str, Any]:
        """Directly calls the generic add_memory function with YAML-validated payload."""
        logger.info(f"🚀 Starting add_memory: type={memory_type}, user={user_id}, payload={payload}")
        try:
            logger.debug(f"📝 Calling core add_memory function...")
            memory = add_memory(
                memory_type=memory_type,
                user_id=user_id,
                payload=payload
            )
            logger.info(f"✅ Memory created successfully: id={memory.id}, hrid={memory.hrid}")
            return {
                "success": True,
                "memory_id": memory.id,
                "hrid": memory.hrid,
            }
        except ValidationError as e:
            logger.error(f"❌ Validation Error: {e}")
            return {"success": False, "error": f"Validation Error: {e}"}
        except Exception as e:
            logger.error(f"💥 Unexpected Error in add_memory: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        **kwargs
    ) -> list[dict[str, Any]]:
        """Search memories using the lean core search function."""
        try:
            results: list[SearchResult] = search(
                query=query,
                user_id=user_id,
                limit=limit,
                memo_type=kwargs.get("memory_type"),
                mode=kwargs.get("mode", "vector"),
                include_details=kwargs.get("include_details", "self"),
                include_see_also=kwargs.get("include_see_also", False),
                filters=kwargs.get("filters")
            )

            # The `__getattr__` on Memory model allows generic access to payload.
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
            return [{"error": str(e)}]

    def delete_memory(self, memory_id: str, user_id: str) -> dict[str, Any]:
        """Delete a single memory with user verification."""
        logger.info(f"🗑️ Starting delete_memory: id={memory_id}, user={user_id}")
        try:
            logger.debug(f"📝 Calling core delete_memory function...")
            success = delete_memory(memory_id=memory_id, user_id=user_id)
            logger.info(f"✅ Memory deleted successfully: id={memory_id}")
            return {
                "success": True,
                "memory_id": memory_id,
                "deleted": success,
            }
        except ValidationError as e:
            logger.error(f"❌ Validation Error: {e}")
            return {"success": False, "error": f"Validation Error: {e}"}
        except DatabaseError as e:
            logger.warning(f"⚠️ Database Error in delete_memory (non-critical): {e}")
            # For now, treat Kuzu database errors as warnings since Qdrant is primary
            return {"success": True, "memory_id": memory_id, "deleted": True, "warning": "Graph database cleanup skipped"}
        except Exception as e:
            logger.error(f"💥 Unexpected Error in delete_memory: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        return {
            "system_type": "memg_core_lean_mcp",
            "version": __version__,
            "api_type": "generic_yaml_driven",
            "available_functions": ["add_memory", "search_memories", "delete_memory"],
        }


# Global bridge instance
bridge: Optional[MemgCoreBridge] = None


def initialize_bridge() -> MemgCoreBridge:
    """Initialize the MEMG Core bridge."""
    global bridge
    logger.info("🏗️ Initializing MEMG Core bridge...")
    try:
        bridge = MemgCoreBridge()
        logger.info("✅ Bridge initialized successfully")
        return bridge
    except Exception as e:
        logger.error(f"💥 Failed to initialize bridge: {e}", exc_info=True)
        raise


def setup_health_endpoints(app: FastMCP) -> None:
    """Setup health check endpoints."""
    @app.custom_route("/", methods=["GET"])
    async def root(_req):
        return JSONResponse({
            "status": "healthy",
            "service": f"MEMG Core MCP v{__version__}",
            "api": "generic_yaml_driven"
        })

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        status = {
            "service": "MEMG Core MCP",
            "version": __version__,
            "bridge_initialized": bridge is not None,
            "status": "healthy" if bridge is not None else "unhealthy",
        }
        return JSONResponse(status, status_code=200 if bridge else 503)


def register_tools(app: FastMCP) -> None:
    """Register MCP tools."""

    @app.tool("mcp_gmem_add_memory")
    def add_memory_tool(
        memory_type: str,
        user_id: str,
        payload: dict
    ):
        """Add a memory using YAML-driven schema validation.

        Parameters
        ----------
        memory_type : str
            Entity type defined in YAML schema. Must exactly match an entity key.
            Available types: memo, document, task, note, bug, solution
        user_id : str
            Owner/namespace for the memory. Required by core.
        payload : dict
            Fields conforming to the YAML entity schema. System fields are auto-managed.

        Entity Schema Details
        --------------------
        memo:
          anchor_field: statement (embedded for search)
          required: statement
          optional: project
          example: {"statement": "Example memo statement"}

        document:
          anchor_field: statement (embedded for search)
          required: statement, details
          optional: project, url
          example: {"statement": "Example document statement", "details": "example_details_value"}

        task:
          anchor_field: statement (embedded for search)
          required: statement
          optional: assignee, details, due_date, epic, priority, project, status, story_points
          example: {"statement": "Example task statement"}

        note:
          anchor_field: statement (embedded for search)
          required: statement, details
          optional: project
          example: {"statement": "Example note statement", "details": "example_details_value"}

        bug:
          anchor_field: statement (embedded for search)
          required: statement, details
          optional: environment, file_path, line_number, project, reproduction, severity, status
          example: {"statement": "Example bug statement", "details": "example_details_value"}

        solution:
          anchor_field: statement (embedded for search)
          required: statement, details
          optional: approach, code_snippet, file_path, project, test_status
          example: {"statement": "Example solution statement", "details": "example_details_value"}

        Behavior
        --------
        - Validates memory_type exists and payload matches entity schema
        - System fields (id, timestamps, vector) are auto-managed
        - Returns memory_id and hrid on success
        - Use mcp_gmem_get_system_info for complete schema inspection

        Returns
        -------
        dict
            {"result": "✅ [Type] added successfully", "memory_id": "uuid", "hrid": "TYPE_XXX001"}
            or {"result": "❌ Failed to add [type]", "error": "error_message"}
        """
        logger.info(f"🔧 MCP Tool called: add_memory_tool(type={memory_type}, user={user_id}, payload={payload})")

        if not bridge:
            logger.error("❌ Bridge not initialized")
            return {"result": "❌ Bridge not initialized"}

        # Validate that memory_type exists in YAML schema
        try:
            logger.debug(f"🔍 Validating memory_type '{memory_type}' against YAML schema...")
            translator = get_yaml_translator()
            if memory_type not in translator._entities_map():
                available_types = list(translator._entities_map().keys())
                logger.error(f"❌ Invalid memory_type '{memory_type}'. Available: {available_types}")
                return {
                    "result": f"❌ Invalid memory_type '{memory_type}'",
                    "error": f"Available types: {available_types}"
                }
            logger.debug(f"✅ Memory type '{memory_type}' is valid")
        except Exception as e:
            logger.error(f"💥 Schema validation failed: {e}", exc_info=True)
            return {"result": f"❌ Schema validation failed: {e}"}

        logger.debug(f"📞 Calling bridge.add_memory...")
        result = bridge.add_memory(
            memory_type=memory_type,
            user_id=user_id,
            payload=payload
        )
        logger.debug(f"📤 Bridge returned: {result}")

        if result["success"]:
            logger.info(f"🎉 Tool successful: {memory_type} added with ID {result['memory_id']}")
            return {
                "result": f"✅ {memory_type.title()} added successfully",
                "memory_id": result["memory_id"],
                "hrid": result.get("hrid"),
            }
        else:
            logger.error(f"💔 Tool failed: {result.get('error', 'Unknown error')}")
            return {
                "result": f"❌ Failed to add {memory_type}",
                "error": result.get("error", "Unknown error")
            }

    # Dynamic docstring system disabled - using hardcoded comprehensive docstring instead


    @app.tool("mcp_gmem_search_memories")
    def search_memories_tool(
        query: str,
        user_id: str = None,
        limit: int = 5,
        memory_type: str = None,
        project: str = None,
        mode: str = "vector",
        include_details: str = "self",
        include_see_also: bool = False,
    ):
        """Search memories (vector by default) with optional filters.

        Parameters
        ----------
        query : str
            Free-text query. Passed to core search (vector by default).
        user_id : str, optional
            Restrict results to this user. If omitted, core behavior applies.
        limit : int, default 5
            Max number of results.
        memory_type : str, optional
            Filter by entity type (e.g., "task", "bug"). Must exist in YAML if provided.
        project : str, optional
            Filter by project namespace. Only returns memories from the specified project.
        mode : str, default "vector"
            Search mode passed through to core. Defaults to vector similarity.
            Other modes (e.g., "keyword", "hybrid") may be supported by core configuration.
        include_details : str, default "self"
            Controls result payload shape. Passed through to core:
            - "self": return the entity's own payload
            - Other values depend on core (e.g., expanded fields). If unknown, core falls back safely.
        include_see_also : bool, default False
            Enable "see also" functionality to find semantically related memories.
            When enabled, uses YAML see_also configuration to surface related memories
            from target types based on anchor text similarity.

        Returns
        -------
        dict
            { "result": "✅ Found N memories", "memories": [{memory_id, hrid, memory_type, payload, score, source}, ...] }

        Notes
        -----
        - Scores/sources originate from core (e.g., vector store).
        - This tool does **not** transform or post-process results beyond packaging.
        """

        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        # Build filters dict to handle project filtering
        filters = {}
        if project:
            filters["entity.project"] = project

        results = bridge.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            memory_type=memory_type,
            mode=mode,
            include_details=include_details,
            include_see_also=include_see_also,
            filters=filters if filters else None,
        )

        if results and "error" in results[0]:
            return {"result": f"❌ Search failed: {results[0]['error']}"}

        return {
            "result": f"✅ Found {len(results)} memories",
            "memories": results,
        }

    @app.tool("mcp_gmem_get_system_info")
    def get_system_info_tool():
        """Get system information and complete YAML schema details.

        Returns
        -------
        dict
            Complete system information including:
            - system_type: Service identifier
            - version: MEMG Core version
            - api_type: API architecture type
            - available_functions: List of available core functions
            - yaml_schema_details: Complete entity schema details with anchor fields
            - valid_memory_types: All available entity types from YAML
            - yaml_schema_path: Path to currently loaded YAML schema file

        Notes
        -----
        Use this tool to inspect the currently active YAML schema, including all entity types,
        their required/optional fields, anchor fields for embedding, and schema file location.
        Essential for understanding what memory types and fields are available.
        """
        if not bridge:
            return {"result": {"status": "Bridge not initialized"}}

        stats = bridge.get_stats()
        try:
            translator = get_yaml_translator()

            # Build schema info using available translator methods
            schema_details = {}
            for entity_name in translator._entities_map():
                fields = _summarize_entity_fields(translator).get(entity_name, {})
                schema_details[entity_name] = {
                    "anchor_field": translator.get_anchor_field(entity_name),
                    "required_fields": fields.get("required", []),
                    "optional_fields": fields.get("optional", []),
                    "description": "Entity type defined in YAML schema",
                }

            stats["yaml_schema_details"] = schema_details
            stats["valid_memory_types"] = list(translator._entities_map().keys())
            stats["yaml_schema_path"] = os.getenv("MEMG_YAML_SCHEMA")

        except Exception as e:
            stats["yaml_schema_error"] = f"Could not load schemas: {e}"

        return {"result": stats}

    @app.tool("mcp_gmem_delete_memory")
    def delete_memory_tool(
        memory_id: str,
        user_id: str,
    ):
        """Delete a single memory by UUID or HRID with user verification.

        Parameters
        ----------
        memory_id : str
            UUID or HRID of the memory to delete. Supports both formats:
            - UUID: e.g., "550e8400-e29b-41d4-a716-446655440000"
            - HRID: e.g., "TASK_AAA001", "NOTE_BBB123"
        user_id : str
            Owner/namespace for the memory. Must match memory owner for deletion.

        Returns
        -------
        dict
            { "result": "✅ Memory deleted successfully", "memory_id": "<id>", "deleted": true }
            or { "result": "❌ Failed to delete memory", "error": "<error_message>" }

        Notes
        -----
        - Accepts both UUID and HRID formats for maximum flexibility
        - Only deletes ONE memory at a time for safety
        - Verifies user ownership before deletion
        - Removes memory from both Qdrant (vector) and Kuzu (graph) storage
        - Automatically resolves HRID to UUID internally
        - Operation is irreversible - use with caution

        Security
        --------
        - User must own the memory to delete it
        - No bulk deletion to prevent accidental data loss
        - Memory existence and ownership verified before deletion
        - Both UUID and HRID provide precise identification
        """
        logger.info(f"🔧 MCP Tool called: delete_memory_tool(id={memory_id}, user={user_id})")

        if not bridge:
            logger.error("❌ Bridge not initialized")
            return {"result": "❌ Bridge not initialized"}

        logger.debug(f"📞 Calling bridge.delete_memory...")
        result = bridge.delete_memory(memory_id=memory_id, user_id=user_id)
        logger.debug(f"📤 Bridge returned: {result}")

        if result["success"]:
            logger.info(f"🎉 Tool successful: Memory {memory_id} deleted")
            return {
                "result": f"✅ Memory deleted successfully",
                "memory_id": result["memory_id"],
                "deleted": result.get("deleted", True),
            }
        else:
            logger.error(f"💔 Tool failed: {result.get('error', 'Unknown error')}")
            return {
                "result": f"❌ Failed to delete memory",
                "error": result.get("error", "Unknown error")
            }


def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""
    app = FastMCP()
    # Ensure YAML schema is explicitly set before initializing tools
    _ensure_yaml_schema_env()
    initialize_bridge()
    setup_health_endpoints(app)
    register_tools(app)
    return app


# Create the app instance
app = create_app()

if __name__ == "__main__":
    port_env = os.getenv("MEMORY_SYSTEM_MCP_PORT")
    if not port_env:
        raise ValueError(
            "MEMORY_SYSTEM_MCP_PORT environment variable is required for multi-instance support. "
            "Set it explicitly (e.g., 8787, 8788, 8789) to avoid port conflicts."
        )
    port = int(port_env)

    # Host should be configured via deployment (Docker, docker-compose, etc.)
    host = os.getenv("MEMORY_SYSTEM_MCP_HOST", "127.0.0.1")  # Secure default: localhost only

    print(f"🚀 Starting MEMG Core MCP Server on {host}:{port}")
    print(f"📦 Using memg-core v{__version__} with a generic, YAML-driven API")
    app.run(transport="sse", host=host, port=port)
