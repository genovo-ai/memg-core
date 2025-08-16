# MEMG Core MCP Server - Enhanced YAML-Driven API

🚀 **YAML-first MCP server with enhanced developer schema support**

## Quick Start

### Option 1: Docker Build & Run (Recommended)

1. **Setup environment:**
   ```bash
   cd mcp/
   cp ../env.example .env
   # IMPORTANT: Edit .env to use the enhanced schema - based on your yaml policy
   # Change: MEMG_YAML_SCHEMA=config/core.minimal.yaml
   # To:     MEMG_YAML_SCHEMA=config/software_dev.yaml
   ```

2. **Build and start with automated script:**
   ```bash
   ./build_and_run.sh
   ```

   This script will:
   - Load `.env` configuration
   - Create required directories with proper permissions
   - Build Docker image from source
   - Start MCP server with health checks
   - Show status and available tools

3. **Test it's working:**
   ```bash
   curl http://localhost:8787/health
   curl http://localhost:8787/
   ```

### Option 2: Direct Docker Compose

1. **Setup environment:**
   ```bash
   cd mcp/
   cp ../env.example .env
   # IMPORTANT: Edit .env to change YAML schema:
   # MEMG_YAML_SCHEMA=config/software_dev.yaml
   mkdir -p ~/.local/share/memory_system_8787/qdrant ~/.local/share/memory_system_8787/kuzu
   ```

2. **Start manually:**
   ```bash
   docker-compose up -d
   ```

## Enhanced Developer Schema

🎯 **Now includes 6 entity types for full software development workflows**:
- ✅ **Basic types**: `memo`, `document`, `task`, `note`
- ✅ **Developer types**: `bug`, `solution`
- ✅ Enhanced fields: severity levels, file paths, code snippets, status tracking
- ✅ Rich relationships: bugs link to solutions, solutions implement tasks
- ✅ **See Also feature**: Automatic discovery of semantically related memories

**Zero hardcoded fields** - everything flows from `config/software_dev.yaml` schema!

### 🔍 See Also Feature

The "See Also" functionality provides **knowledge graph-style associative discovery**:

- **Automatic**: When enabled, searches return primary results PLUS semantically related memories
- **YAML-configured**: Each entity type can specify target types, thresholds, and limits
- **Transparent**: Related memories are clearly tagged with `see_also_*` source attribution
- **Efficient**: Single Qdrant query with OR filtering across multiple target types

**Example Configuration (in YAML schema):**
```yaml
entities:
  - name: task
    see_also:
      enabled: true
      threshold: 0.7        # 70% similarity required
      limit: 3             # Max 3 suggestions per type
      target_types: [bug, solution, note]
```

## Available MCP Tools (3 Total)

The MCP server provides exactly **3 YAML-driven tools**:

### Memory Management
- **`mcp_gmem_add_memory`** - Pure YAML-driven memory addition (supports all 6 entity types)
- **`mcp_gmem_search_memories`** - Semantic search with vector similarity scoring
- **`mcp_gmem_get_system_info`** - Get complete YAML schema details and system stats

### ✅ Verified Working
All tools tested and working with enhanced schema including new `bug` and `solution` types.

### Example Usage (Enhanced Schema)
```bash
# Get schema information first
curl -X POST http://localhost:8787/tools/mcp_gmem_get_system_info

# Add a bug (developer type with enhanced fields)
curl -X POST http://localhost:8787/tools/mcp_gmem_add_memory \
  -H "Content-Type: application/json" \
  -d '{"memory_type": "bug", "user_id": "cursor", "payload": {"statement": "Docker mount permission issue", "details": "Docker failing to mount volumes on macOS due to chown errors", "severity": "medium", "status": "resolved"}}'

# Add a solution (with implementation details)
curl -X POST http://localhost:8787/tools/mcp_gmem_add_memory \
  -H "Content-Type: application/json" \
  -d '{"memory_type": "solution", "user_id": "cursor", "payload": {"statement": "Pre-create mount directories", "details": "Create directories before docker-compose runs", "implementation": "Modified build_and_run.sh to expand .env and mkdir -p required paths"}}'

# Add a task (basic type)
curl -X POST http://localhost:8787/tools/mcp_gmem_add_memory \
  -H "Content-Type: application/json" \
  -d '{"memory_type": "task", "user_id": "cursor", "payload": {"statement": "Update MCP documentation", "status": "in_progress", "priority": "high"}}'

# Search memories with semantic similarity
curl -X POST http://localhost:8787/tools/mcp_gmem_search_memories \
  -H "Content-Type: application/json" \
  -d '{"query": "Docker permission", "user_id": "cursor", "limit": 5}'

# Search with "See Also" feature enabled (finds related memories automatically)
curl -X POST http://localhost:8787/tools/mcp_gmem_search_memories \
  -H "Content-Type: application/json" \
  -d '{"query": "Docker setup", "user_id": "cursor", "limit": 8, "include_see_also": true}'
```

## Configuration

Key settings in `.env` file (copy from `../env.example` and edit):
```bash
# Storage and networking (REQUIRED)
BASE_MEMORY_PATH=$HOME/.local/share/memory_system  # Will be expanded to full path
MEMORY_SYSTEM_MCP_PORT=8787                        # Change for multiple instances

# YAML Schema (MUST EDIT: change from core.minimal.yaml to software_dev.yaml)
MEMG_YAML_SCHEMA=config/software_dev.yaml         # Enhanced schema with 6 types

# Note: The env.example defaults to core.minimal.yaml (4 types)
# You MUST change it to software_dev.yaml to get bug/solution types
# Available types: memo, document, task, note, bug, solution
```

### Automatic Directory Creation
The `build_and_run.sh` script automatically:
- Reads `.env` configuration
- Expands `$HOME` to full path
- Creates `~/.local/share/memory_system_8787/qdrant` and `kuzu` directories
- Sets proper permissions to avoid Docker mount issues

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

## Development & Troubleshooting

### Quick Commands
```bash
# View server logs
docker-compose logs -f

# Stop server
docker-compose down

# Restart with fresh build
./build_and_run.sh

# Manual directory creation (if needed)
mkdir -p ~/.local/share/memory_system_8787/{qdrant,kuzu}
```

### Common Issues

**Docker mount permission errors on macOS?**
- The `build_and_run.sh` script automatically fixes this
- Creates directories with proper permissions before Docker runs

**MCP tools not available in Cursor?**
- Ensure server is registered in Cursor MCP settings
- Check server is running: `curl http://localhost:8787/health`

### Architecture Notes

- **Enhanced YAML schema**: 6 entity types for full developer workflows
- **Local builds only**: No registry dependencies, builds from source
- **Cross-platform**: Works on macOS and Linux with automatic path handling
- **Persistent storage**: Memories stored in `~/.local/share/memory_system_*` directories

## ✅ Status: Fully Working

All 3 MCP tools tested and verified working with enhanced developer schema including `bug` and `solution` types! 🎉
