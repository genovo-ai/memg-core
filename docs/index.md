# memg-core

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

### Installation

```bash
pip install memg-core
```

### Basic Usage

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

# Search for memories
results = search(
    query="postgres docker setup",
    user_id="demo_user",
    limit=5
)
for r in results:
    print(f"[{r.memory.memory_type}] {r.memory.hrid}: {r.memory.payload['statement']} - Score: {r.score:.2f}")
```

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

## Requirements

- Python 3.11+
- No API keys required!

## Links

- [Repository](https://github.com/genovo-ai/memg-core)
- [Issues](https://github.com/genovo-ai/memg-core/issues)
- [PyPI Package](https://pypi.org/project/memg-core/)

## License

MIT License - see LICENSE file for details.
