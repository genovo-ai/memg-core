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
# 1. Create configuration
cp env.example .env
# Edit .env and set your GOOGLE_API_KEY

# 2. Run MEMG MCP Server (359MB)
docker run -d \
  -p 8787:8787 \
  --env-file .env \
  ghcr.io/genovo-ai/memg-core-mcp:latest

# 3. Test it's working
curl http://localhost:8787/health
```

### Option 2: Python Package
```bash
pip install memg-core

# Set up environment
cp env.example .env
# Edit .env and set your GOOGLE_API_KEY

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

Configure via `.env` file (copy from `env.example`):

```bash
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Core settings
GEMINI_MODEL=gemini-2.0-flash
MEMORY_SYSTEM_MCP_PORT=8787
MEMG_TEMPLATE=software_development

# Storage
BASE_MEMORY_PATH=$HOME/.local/share/memory_system
QDRANT_COLLECTION=memories
MEMG_VECTOR_DIMENSION=768
```

## Requirements

- Python 3.11+
- Google API key for Gemini

## Links

- [Repository](https://github.com/genovo-ai/memg-core)
- [Issues](https://github.com/genovo-ai/memg-core/issues)
- [Documentation](https://github.com/genovo-ai/memg-core#readme)

## License

MIT License - see LICENSE file for details.
