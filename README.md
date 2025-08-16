# 💾 memg-core

**The foundation of structured memory for AI agents.**

memg-core is the deterministic, schema-driven memory engine at the heart of the larger MEMG system. It gives AI developers a fast, reliable, testable memory layer powered by:

- **YAML-based schema definition** (for custom memory types)
- **Dual-store backend** (Qdrant for vectors, Kuzu for graph queries)
- **Public Python API** for all memory operations
- **Built-in support** for auditability, structured workflows, and self-managed memory loops

It's designed for AI agents that build, debug, and improve themselves — and for humans who demand clean, explainable, memory-driven systems.

🧩 **This is just the core.** The full memg system builds on this to add multi-agent coordination, long-term memory policies, and deeper retrieval pipelines — currently in progress.

## Features

- **Vector Search**: Fast semantic search with Qdrant
- **Graph Storage**: Optional relationship analysis with Kuzu
- **Offline-First**: 100% local embeddings with FastEmbed - no API keys needed
- **Type-Agnostic**: Configurable memory types via YAML schemas
- **See Also Discovery**: Knowledge graph-style associative memory retrieval
- **Lightweight**: Minimal dependencies, optimized for performance

## Quick Start

### Python Package
```bash
pip install memg-core

# Set up environment variables for storage paths
export QDRANT_STORAGE_PATH="/path/to/qdrant"
export KUZU_DB_PATH="/path/to/kuzu.db"

# Use the core library in your app
# Example usage shown below in the Usage section
```

### Development setup
```bash
# 1) Create virtualenv and install slim runtime deps for library usage
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) For running tests and linters locally, install dev deps
pip install -r requirements-dev.txt

# 3) Run tests
export MEMG_TEMPLATE="software_development"
export QDRANT_STORAGE_PATH="$HOME/.local/share/qdrant"
export KUZU_DB_PATH="$HOME/.local/share/kuzu/memg.db"
mkdir -p "$QDRANT_STORAGE_PATH" "$HOME/.local/share/kuzu"
PYTHONPATH=$(pwd)/src pytest -q
```

## Usage

```python
from memg_core.api.public import add_note, add_document, add_task, search

# Add a note
note = add_note(
    text="Set up Postgres with Docker for local development",
    user_id="demo_user",
    title="Docker Postgres Setup",
    tags=["docker", "postgres", "dev"],
)

# Search (GraphRAG-first pipeline)
results = search("postgres performance", user_id="demo_user", limit=5)
for r in results:
    print(f"[{r.memory.memory_type.value}] {r.memory.title} - Score: {r.score:.2f}")

# Search with "See Also" discovery (finds semantically related memories)
results = search("postgres setup", user_id="demo_user", limit=10, include_see_also=True)
for r in results:
    source = r.source  # 'qdrant' for primary, 'see_also_bug' for related
    print(f"[{source}] {r.memory.memory_type.value}: {r.memory.title} - Score: {r.score:.2f}")
```

### YAML Schema Examples

Core ships with example schemas under `config/`:

- `core.memo.yaml`: Basic memory types (`memo`, `note`, `document`, `task`)
- `software_dev.yaml`: Enhanced schema with `bug` and `solution` types for development workflows
- `core.test.yaml`: Test configuration for development

Enable:

```bash
export MEMG_ENABLE_YAML_SCHEMA=true
export MEMG_YAML_SCHEMA=$(pwd)/config/core.memo.yaml
```

## Embedding Configuration

MEMG Core uses FastEmbed for 100% offline, local embeddings. By default, it uses the highly efficient Snowflake Arctic model:

```bash
# Optional: Configure a different FastEmbed model
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"  # Default
# Other options: intfloat/e5-small, BAAI/bge-small-en-v1.5, etc.
```



## Configuration

Configure via `.env` file (copy from `env.example`):

```bash
# Core settings
MEMORY_SYSTEM_MCP_PORT=8787  # Change for multiple instances
MEMG_TEMPLATE=software_development

# Embeddings (optional)
EMBEDDER_MODEL=Snowflake/snowflake-arctic-embed-xs

# Storage
BASE_MEMORY_PATH=$HOME/.local/share/memory_system
QDRANT_COLLECTION=memories
EMBEDDING_DIMENSION_LEN=384
```

## Requirements

- Python 3.11+
- No API keys required!

## Architecture

memg-core provides a deterministic, YAML-driven memory layer with dual storage:

- **YAML-driven schema engine** - Define custom memory types with zero hardcoded fields
- **Qdrant/Kuzu dual-store** - Vector similarity + graph relationships
- **Public Python API** - Clean interface for all memory operations
- **Configurable schemas** - Examples in `config/` for different use cases

### In Scope
- ✅ YAML schema definition and validation
- ✅ Memory CRUD operations with dual storage
- ✅ Semantic search and "see also" discovery
- ✅ Public Python API with full functionality

### Coming in Full MEMG System
- 🔄 Schema contracts and multi-agent coordination
- 🔄 Async job processing and bulk operations
- 🔄 Advanced memory policies and retention
- 🔄 Multi-agent memory orchestration

## Links

- [Repository](https://github.com/genovo-ai/memg-core)
- [Issues](https://github.com/genovo-ai/memg-core/issues)
- [Documentation](https://github.com/genovo-ai/memg-core#readme)

## License

MIT License - see LICENSE file for details.
