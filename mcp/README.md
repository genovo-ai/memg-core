# MEMG Core - Docker Quickstart

🚀 **Simple Docker deployment for MEMG Core memory system**

## Quick Start (Public Image)

**Fastest way to get started:**
```bash
# 1. Setup configuration
cp ../env.example ../.env
# Edit .env and set your GOOGLE_API_KEY

# 2. Run MEMG MCP Server directly
docker run -d \
  -p 8787:8787 \
  --env-file ../.env \
  ghcr.io/genovo-ai/memg-core-mcp:latest

# 3. Test it's working
curl http://localhost:8787/health
```

## Alternative: Docker Compose

1. **Setup environment:**
   ```bash
   cp ../env.example ../.env
   # Edit .env and set your GOOGLE_API_KEY
   ```

2. **Start MEMG Core:**
   ```bash
   cd dockerfiles/
   docker-compose up -d
   ```

3. **Stop when done:**
   ```bash
   docker-compose down
   ```

## What You Get

- **MEMG Core MCP Server** on port 8787
- **Persistent Storage** in `~/.local/share/memory_system_8787/`
- **Health Monitoring** with automatic restarts
- **20+ Memory Tools** for AI integration

## Configuration

Key settings in `.env` file:
```bash
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Core settings
GEMINI_MODEL=gemini-2.0-flash
MEMORY_SYSTEM_MCP_PORT=8787
MEMG_TEMPLATE=software_development

# Storage & Performance
BASE_MEMORY_PATH=$HOME/.local/share/memory_system
QDRANT_COLLECTION=memories
EMBEDDING_DIMENSION_LEN=384
MEMORY_SYSTEM_DEBUG=false
```

## Usage

Once running, connect your AI client to:
- **MCP Server**: `http://localhost:8787`
- **Available Tools**: `mcp_gmem_add_memory`, `mcp_gmem_search_memories`, etc.

## Logs & Debugging

```bash
# View logs
docker-compose logs -f memg-mcp-server

# Check container status
docker-compose ps

# Reset everything
docker-compose down && docker-compose up -d
```

That's it! 🎉
