# MEMG Core

**Lightweight memory system for AI agents with dual storage (Qdrant + Kuzu)**

## Features

- **Vector Search**: Fast semantic search with Qdrant
- **Graph Storage**: Optional relationship analysis with Kuzu
- **AI Integration**: Automated entity extraction with Google Gemini
- **MCP Compatible**: Ready-to-use MCP server for AI agents
- **Lightweight**: Minimal dependencies, optimized for performance

## Quick Start

### Option 1: Docker (Recommended)
```bash
# Run MEMG MCP Server (359MB)
docker run -d \
  -p 8787:8787 \
  -e GOOGLE_API_KEY="your-api-key" \
  -e MEMG_ENABLE_GRAPH=true \
  ghcr.io/genovo-ai/memg-core-mcp:latest

# Test it's working
curl http://localhost:8787/health
```

### Option 2: Python Package
```bash
pip install memg-core

# Set up environment
export GOOGLE_API_KEY="your-api-key"
export MEMG_ENABLE_GRAPH=true

# Start MCP server
python -m memory_system.mcp_server
```

## Usage

```python
from memory_system import MemorySystem

# Initialize system
memory = MemorySystem()

# Add memories
memory.add_note("Python is great for AI development", user_id="user1")

# Search memories
results = memory.search("AI development", user_id="user1")
```

## Configuration

Configure via environment variables:

- `GOOGLE_API_KEY`: Required for AI processing
- `MEMG_ENABLE_GRAPH`: Enable graph storage (default: false)
- `QDRANT_STORAGE_PATH`: Vector database path
- `KUZU_DB_PATH`: Graph database path

## Requirements

- Python 3.11+
- Google API key for Gemini

## Links

- [Repository](https://github.com/genovo-ai/memg-core)
- [Issues](https://github.com/genovo-ai/memg-core/issues)
- [Documentation](https://github.com/genovo-ai/memg-core#readme)

## License

MIT License - see LICENSE file for details.
