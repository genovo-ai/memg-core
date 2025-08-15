# MEMG Core MCP Server - Lean Core API

🚀 **Updated MCP server using the latest lean core API**

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

3. **Test it's working:**
   ```bash
   curl http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/health
   curl http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/
   ```

4. **Stop when done:**
   ```bash
   docker-compose down
   ```

## What's New in Lean Core API

The MCP server now uses the **lean core public API**:
- ✅ `add_note(text, user_id, title, tags)`
- ✅ `add_document(text, user_id, title, summary, tags)`
- ✅ `add_task(text, user_id, title, tags, due_date, assignee)`
- ✅ `search(query, user_id, limit, mode="vector|graph|hybrid")`

## Available MCP Tools

### Memory Management
- **`mcp_gmem_add_memory`** - Generic memory addition
- **`mcp_gmem_add_note`** - Add a note
- **`mcp_gmem_add_document`** - Add a document
- **`mcp_gmem_add_task`** - Add a task
- **`mcp_gmem_search_memories`** - Search memories
- **`mcp_gmem_get_system_info`** - Get system stats

### Example Usage
```bash
# Add a note
curl -X POST http://localhost:${MEMORY_SYSTEM_MCP_PORT:-8787}/tools/mcp_gmem_add_note \
  -H "Content-Type: application/json" \
  -d '{"text": "Remember to update docs", "user_id": "test_user", "title": "Documentation Task"}'

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

# Note: Current lean core uses fixed schema (core.minimal.yaml)
# Future: MEMG_TEMPLATE for domain-specific templates
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
