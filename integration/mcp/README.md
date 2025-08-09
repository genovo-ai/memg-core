# MEMG MCP Server

🚀 **MCP Server integration for MEMG Core memory system**

This package provides a Model Context Protocol (MCP) server that exposes MEMG Core functionality as MCP tools for AI agents.

## Quick Start

### Using Docker (Recommended)

1. **Pull and run:**
   ```bash
   docker run -p 8787:8787 -e GOOGLE_API_KEY=your_key ghcr.io/genovo-ai/memg-mcp-server:latest
   ```

### Using Python Package

1. **Install:**
   ```bash
   pip install memg-mcp-server
   ```

2. **Run:**
   ```bash
   memg-mcp-server
   ```

## Configuration

Set these environment variables:

- `GOOGLE_API_KEY` - Your Google API key (required)
- `MEMORY_SYSTEM_MCP_PORT=8787` - Server port
- `MEMG_TEMPLATE=software_development` - Memory template
- `QDRANT_STORAGE_PATH=/qdrant` - Vector storage path
- `KUZU_DB_PATH=/kuzu/memory_db` - Graph database path

## Available MCP Tools

- `mcp_gmem_add_memory` - Add new memories
- `mcp_gmem_search_memories` - Search existing memories  
- `mcp_gmem_graph_search` - Graph-based memory search
- `mcp_gmem_validate_graph` - Validate memory graph
- `mcp_gmem_get_memory_schema` - Get memory schema info
- `mcp_gmem_get_system_info` - Get system information

## Usage with AI Clients

Once running, connect your MCP-compatible AI client to:
```
http://localhost:8787
```

The server implements the MCP protocol and provides 20+ memory tools for AI agents.

## Development

See the main [MEMG Core repository](https://github.com/genovo-ai/memg-core) for development setup.
