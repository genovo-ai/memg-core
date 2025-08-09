# MEMG Core - Docker Quickstart

🚀 **Simple Docker deployment for MEMG Core memory system**

## Quick Start

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

3. **Test the server:**
   ```bash
   curl http://localhost:8787/health
   ```

4. **Stop when done:**
   ```bash
   docker-compose down
   ```

## What You Get

- **MEMG Core MCP Server** on port 8787
- **Persistent Storage** in `~/.local/share/memory_system_8787/`
- **Health Monitoring** with automatic restarts
- **20+ Memory Tools** for AI integration

## Configuration

Environment variables (set in `.env`):
- `GOOGLE_API_KEY` - Your Google API key (required)
- `MEMORY_SYSTEM_MCP_PORT=8787` - Server port
- `MEMG_TEMPLATE=software_development` - Memory template

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
