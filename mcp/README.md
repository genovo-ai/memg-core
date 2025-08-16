# MEMG Core MCP Server - Pure YAML-Driven API

🚀 **YAML-first MCP server with zero hardcoded entity types**

## Quick Start

### Option 1: Direct Python (Development)

1. **Setup environment:**
   ```bash
   cp ../env.example ../.env
   # Edit .env if needed (No API keys required - uses FastEmbed locally!)
   ```

2. **Run MCP Server directly:**
   ```bash
   cd mcp/
   python mcp_server.py
   ```

### Option 2: Docker (Local Build)

1. **Setup environment:**
   ```bash
   cp ../env.example ../.env
   ```

2. **Start with Docker Compose:**
   ```bash
   cd mcp/
   docker-compose up -d
   ```

3. **Test it's working:**
   ```bash
   curl http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/health
   curl http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/
   ```

## What's New: Pure YAML-Driven Architecture

The MCP server is now **100% YAML-schema compliant**:
- ✅ `add_memory(memory_type, payload, user_id)` - Pure YAML validation
- ✅ `search(query, user_id, limit, mode="vector|graph|hybrid")` - Unified search
- ✅ Dynamic schema discovery via `get_system_info` tool

**Zero hardcoded fields** - everything flows from `core.minimal.yaml` schema!

## Available MCP Tools (3 Total)

The MCP server provides exactly **3 YAML-driven tools**:

### Memory Management
- **`mcp_gmem_add_memory`** - Pure YAML-driven memory addition (supports all YAML entity types)
- **`mcp_gmem_search_memories`** - Search memories with filtering
- **`mcp_gmem_get_system_info`** - Get YAML schema details and system stats

### ⚠️ Important Note
The server uses **one generic `add_memory` tool** that works with all YAML-defined entity types (`memo`, `note`, `task`, `document`) rather than separate tools for each type. This maintains YAML-first principles.

### Example Usage (YAML-Compliant)
```bash
# Get schema information first
curl -X POST http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/tools/mcp_gmem_get_system_info

# Add a memo (basic type)
curl -X POST http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/tools/mcp_gmem_add_memory \
  -H "Content-Type: application/json" \
  -d '{"memory_type": "memo", "user_id": "test_user", "payload": {"statement": "Remember to update docs"}}'

# Add a task (with YAML-defined fields)
curl -X POST http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/tools/mcp_gmem_add_memory \
  -H "Content-Type: application/json" \
  -d '{"memory_type": "task", "user_id": "test_user", "payload": {"statement": "Update documentation", "details": "Need to update MCP README", "status": "todo", "priority": "high"}}'

# Add a note (with details)
curl -X POST http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/tools/mcp_gmem_add_memory \
  -H "Content-Type: application/json" \
  -d '{"memory_type": "note", "user_id": "test_user", "payload": {"statement": "Meeting notes", "details": "Discussed YAML compliance"}}'

# Search memories
curl -X POST http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/tools/mcp_gmem_search_memories \
  -H "Content-Type: application/json" \
  -d '{"query": "documentation", "user_id": "test_user", "limit": 5}'
```

## Configuration

Key settings in `.env` file:
```bash
# Storage paths (will be created automatically)
QDRANT_STORAGE_PATH=/path/to/qdrant
KUZU_DB_PATH=/path/to/kuzu/db

# Server settings
MEMORY_SYSTEM_MCP_PORT=8787  # Change for multiple instances

# Schema configuration
MEMG_YAML_SCHEMA=/app/config/core.minimal.yaml  # Fixed in Docker
# Note: All entity types and fields come from this YAML schema
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MCP Client    │───▶│   MCP Server     │───▶│   Lean Core     │
│   (AI Agent)    │    │  (FastMCP)       │    │   Public API    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                               ┌─────────▼─────────┐
                                               │  Storage Backends │
                                               │  • Qdrant (vector)│
                                               │  • Kuzu (graph)   │
                                               └───────────────────┘
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run MCP server with debugging
python mcp_server.py --debug

# Test with latest code changes
python -m pytest ../tests/ -v
```

## Architecture Notes

- **Local builds only**: No registry dependencies, everything builds from source
- **MCP as side integration**: This will eventually move to the parent "memg" repo
- **Requirements separation**: MCP dependencies in `requirements_mcp.txt` for lighter builds

That's it! 🎉
