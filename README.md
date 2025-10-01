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
export QDRANT_STORAGE_PATH="/path/to/qdrant"
export KUZU_DB_PATH="/path/to/kuzu/database"
export YAML_PATH="config/core.memo.yaml"

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
export YAML_PATH="config/core.test.yaml"
export QDRANT_STORAGE_PATH="$HOME/.local/share/qdrant"
export KUZU_DB_PATH="$HOME/.local/share/kuzu/memg"
mkdir -p "$QDRANT_STORAGE_PATH" "$HOME/.local/share/kuzu"
PYTHONPATH=$(pwd)/src pytest -q
```

## Usage

```python
from memg_core.api.public import add_memory, search, delete_memory

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
for r in results:
    print(f"[{r.memory.memory_type}] {r.memory.hrid}: {r.memory.payload['statement']} - Score: {r.score:.2f}")

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
```

### YAML Schema Examples

Core ships with example schemas under `config/`:

- `core.memo.yaml`: Basic memory types (`memo`, `note`, `document`, `task`)
- `software_dev.yaml`: Enhanced schema with `bug` and `solution` types for development workflows
- `core.test.yaml`: Test configuration for development

Configure the schema:

```bash
export YAML_PATH="config/core.memo.yaml"  # Basic schema
# or
export YAML_PATH="config/software_dev.yaml"  # Enhanced with bug/solution types
# or
export YAML_PATH="config/core.test.yaml"  # For testing
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

**Supported Field Types**: Rich type system
```yaml
- name: product
  fields:
    name: { type: string, required: true }  # Text (required)
    price: { type: float }           # Decimal numbers
    quantity: { type: int }          # Integers (also: integer)
    in_stock: { type: bool }         # Booleans (also: boolean)
    created_at: { type: datetime }   # Timestamps
    tags: { type: list }             # Lists
    category: { type: enum, choices: [A, B, C] }  # Enumerations
    embedding: { type: vector }      # Embedding vectors
```

**Currently Enforced Constraints:**
- ✅ `required: true` - Field must be present
- ✅ `type: <type>` - Type must match (string, int, float, bool, datetime, list, enum, vector)
- ✅ `enum` with `choices: [...]` - Value must be one of the specified choices
- ✅ `system: true` - System fields (id, user_id, timestamps) handled automatically

**Not Yet Implemented** (tracked in [#issue]):
- ⚠️ `default: value` - Defaults are not auto-applied (fields absent if not provided)
- ⚠️ `max_length: N` - String length validation not enforced
- ⚠️ Other Pydantic-style constraints (min_value, pattern, etc.)

## Embedding Configuration

### Default: FastEmbed (Offline, No API Keys)

MEMG Core uses FastEmbed by default for 100% offline, local embeddings:

```bash
# Optional: Configure a different FastEmbed model
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"  # Default
# Other options: intfloat/e5-small, BAAI/bge-small-en-v1.5, etc.
```

### Custom Embedders

You can provide your own embedder (OpenAI, Cohere, custom models, etc.) by implementing a simple protocol:

```python
from memg_core import MemgClient, EmbedderProtocol

class OpenAIEmbedder:
    """Example: Use OpenAI embeddings instead of FastEmbed."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        import openai
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(input=[text], model=self.model)
        return response.data[0].embedding

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]

# Use your custom embedder
embedder = OpenAIEmbedder(api_key="your-api-key")
client = MemgClient(
    yaml_path="config/core.memo.yaml",
    db_path="/path/to/db",
    embedder=embedder
)

# Now all memory operations use your custom embedder
hrid = client.add_memory(
    memory_type="note",
    payload={"statement": "Using OpenAI embeddings"},
    user_id="user123"
)
```

The embedder protocol is simple - just implement two methods:
- `get_embedding(text: str) -> list[float]` - for single text
- `get_embeddings(texts: list[str]) -> list[list[float]]` - for batch processing

**Note:** When using custom embedders, ensure the vector dimension matches your Qdrant configuration (default: 384 for FastEmbed's arctic-xs model).



## Configuration

Configure via environment variables:

```bash
# Required: Storage paths
export QDRANT_STORAGE_PATH="$HOME/.local/share/qdrant"
export KUZU_DB_PATH="$HOME/.local/share/kuzu/memg"
export YAML_PATH="config/core.memo.yaml"

# Optional: Embeddings
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"  # Default

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
