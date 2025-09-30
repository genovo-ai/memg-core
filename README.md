# 💾 memg-core

[![PyPI](https://img.shields.io/pypi/v/memg-core.svg)](https://pypi.org/project/memg-core/)
[![Python Version](https://img.shields.io/pypi/pyversions/memg-core.svg)](https://pypi.org/project/memg-core/)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://genovo-ai.github.io/memg-core/)
[![License](https://img.shields.io/github/license/genovo-ai/memg-core.svg)](https://github.com/genovo-ai/memg-core/blob/main/LICENSE)
[![Tests](https://github.com/genovo-ai/memg-core/workflows/tests/badge.svg)](https://github.com/genovo-ai/memg-core/actions)

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
- **Enhanced Search Control**: Granular control over result detail levels (`none`, `self`, `all`)
- **Display Field Overrides**: Custom display fields that override anchor fields for better UX
- **YAML-Based Datetime Formatting**: Consistent datetime formatting across all operations
- **Force/Exclude Display**: Fine-grained control over which fields are always shown or hidden
- **Offline-First**: 100% local embeddings with FastEmbed - no API keys needed
- **Type-Agnostic**: Configurable memory types via YAML schemas
- **See Also Discovery**: Knowledge graph-style associative memory retrieval
- **Lightweight**: Minimal dependencies, optimized for performance
- **Production Ready**: Robust error handling, deterministic ID management, comprehensive testing

## Quick Start

### Python Package
```bash
pip install memg-core

# Set up environment variables for storage paths
export MEMG_YAML_PATH="config/core.memo.yaml"
export MEMG_DB_PATH="/path/to/databases"

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
export MEMG_YAML_PATH="config/core.test.yaml"
export MEMG_DB_PATH="$HOME/.local/share/memg"
mkdir -p "$MEMG_DB_PATH"
PYTHONPATH=$(pwd)/src pytest -q
```

## Usage

```python
from memg_core.api.public import add_memory, search, delete_memory, update_memory, get_memory, get_memories

# Add a note
note_hrid = add_memory(
    memory_type="note",
    payload={
        "statement": "Set up Postgres with Docker for local development",
        "project": "backend-setup"
    },
    user_id="demo_user"
)
print(f"Created note: {note_hrid}")  # Returns HRID like "NOTE_AAA001"

# Add a document with more details
doc_hrid = add_memory(
    memory_type="document",
    payload={
        "statement": "Docker Postgres Configuration Guide",
        "details": "Complete setup guide for running PostgreSQL in Docker containers for local development",
        "project": "backend-setup"
    },
    user_id="demo_user"
)

# Search for memories
results = search(
    query="postgres docker setup",
    user_id="demo_user",
    limit=5
)
for memory_seed in results.memories:
    print(f"[{memory_seed.memory_type}] {memory_seed.hrid}: {memory_seed.payload['statement']} - Score: {memory_seed.score:.2f}")

# Search with memory type filtering
note_results = search(
    query="postgres",
    user_id="demo_user",
    memory_type="note",
    limit=10
)

# Enhanced search control (v0.7.4+)
# Control result detail levels: "none" (minimal), "self" (default), "all" (maximum)
minimal_results = search(
    query="postgres docker",
    user_id="demo_user",
    include_details="none",  # Shows only display fields
    limit=5
)

# Search with graph expansion and full details
expanded_results = search(
    query="postgres setup",
    user_id="demo_user",
    include_details="all",    # Shows full payload for both seeds and neighbors
    hops=2,                   # Expand 2 levels in the knowledge graph
    limit=3
)

# Delete a memory using HRID
success = delete_memory(hrid=note_hrid, user_id="demo_user")
print(f"Deletion successful: {success}")

# Update a memory
success = update_memory(
    hrid=doc_hrid,
    payload_updates={"details": "Updated details"},
    user_id="demo_user"
)

# Get a specific memory with relationships
memory_result = get_memory(
    hrid=doc_hrid,
    user_id="demo_user",
    include_neighbors=True,
    hops=1
)
if memory_result:
    print(f"Found: {memory_result.memories[0].hrid}")
    print(f"Neighbors: {len(memory_result.neighbors)}")

# Get all memories of a type
all_notes = get_memories(
    user_id="demo_user",
    memory_type="note",
    limit=20
)
print(f"Found {len(all_notes.memories)} notes")
```

### YAML Schema Examples

Core ships with example schemas under `config/`:

- `core.memo.yaml`: Basic memory types (`memo`, `note`, `document`, `task`)
- `software_dev.yaml`: Enhanced schema with `bug` and `solution` types for development workflows
- `core.test.yaml`: Test configuration for development

Configure the schema:

```bash
export MEMG_YAML_PATH="config/core.memo.yaml"  # Basic schema
# or
export MEMG_YAML_PATH="config/software_dev.yaml"  # Enhanced with bug/solution types
# or
export MEMG_YAML_PATH="config/core.test.yaml"  # For testing
```

#### New v0.7.4 YAML Features

**Display Field Overrides**: Customize what field is shown in search results
```yaml
- name: task
  parent: memo
  fields:
    details: { type: string }
    status: { type: enum, choices: [todo, done] }
  override:
    display_field: details  # Show 'details' instead of 'statement' in results
```

**Force/Exclude Display**: Control field visibility
```yaml
- name: document
  parent: memo
  fields:
    title: { type: string }
    content: { type: string }
    internal_notes: { type: string }
  override:
    force_display: [title]        # Always show title, even in minimal mode
    exclude_display: [internal_notes]  # Never show internal notes
```

**YAML-Based Datetime Formatting**: Consistent timestamps
```yaml
defaults:
  datetime_format: "%Y-%m-%d %H:%M:%S"  # Applied to all datetime fields
```

## Embedding Configuration

MEMG Core uses FastEmbed for 100% offline, local embeddings. By default, it uses the highly efficient Snowflake Arctic model:

```bash
# Optional: Configure a different FastEmbed model
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"  # Default
# Other options: intfloat/e5-small, BAAI/bge-small-en-v1.5, etc.
```



## Configuration

Configure via environment variables:

```bash
# Required: Storage paths and schema
export MEMG_YAML_PATH="config/core.memo.yaml"
export MEMG_DB_PATH="$HOME/.local/share/memg"

# Optional: Embeddings
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"  # Default

# Optional: Advanced configuration
export MEMG_QDRANT_COLLECTION="memg"  # Qdrant collection name
export MEMG_KUZU_DB_PATH="kuzu_db"    # Kuzu database path (relative to MEMG_DB_PATH)

# Optional: For MCP server (if using)
export MEMORY_SYSTEM_MCP_PORT=8787
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
- ✅ Semantic search with memory type filtering
- ✅ Public Python API with HRID-based interface
- ✅ User isolation with per-user HRID scoping

### Coming in Full MEMG System

- 🔄 Schema contracts and multi-agent coordination
- 🔄 Async job processing and bulk operations
- 🔄 Advanced memory policies and retention
- 🔄 Multi-agent memory orchestration

## Links

- [📚 Documentation](https://genovo-ai.github.io/memg-core/)
- [📦 PyPI Package](https://pypi.org/project/memg-core/)
- [🐙 Repository](https://github.com/genovo-ai/memg-core)
- [🐛 Issues](https://github.com/genovo-ai/memg-core/issues)

## License

MIT License - see LICENSE file for details.
