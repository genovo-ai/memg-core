# MEMG Core MCP Server - Pure YAML-Driven API

🚀 **YAML-first MCP server with zero hardcoded entity types**

## Quick Test with Latest Code

**Test the MCP server with your latest wheel:**
```bash
# Build and test with latest code
./test-mcp-server.sh

# This will:
# 1. Build a fresh wheel from your code
# 2. Build Docker image with the wheel
# 3. Start MCP server and test it
```

## Quick Start (Docker Compose)

1. **Setup environment:**
   ```bash
   cp ../env.example ../.env
   # Edit .env if needed (No API keys required - uses FastEmbed locally!)
   ```

2. **Start MEMG Core MCP Server:**
   ```bash
   cd mcp/
   docker-compose up -d
   ```

   **Note**: The docker-compose is configured with `pull_policy: always` to ensure you always get the latest image from the GitHub Container Registry, never using local cached versions.

3. **Test it's working:**
   ```bash
   curl http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/health
   curl http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/
   ```

4. **Stop when done:**
   ```bash
   docker-compose down
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
MEMG_YAML_SCHEMA=/app/schema/core.minimal.yaml  # Fixed in Docker
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

## Logs & Debugging

```bash
# View logs
docker-compose logs -f memg-mcp-server

# Check container status
docker-compose ps

# Interactive shell in container
docker-compose exec memg-mcp-server bash

# Reset everything
docker-compose down && docker-compose up -d
```

## Development

```bash
# Test with latest code changes
./test-mcp-server.sh

# Build wheel manually
python -m build

# Build Docker image manually
docker build -f mcp/Dockerfile.mcp -t memg-core-mcp:latest .
```

That's it! 🎉
