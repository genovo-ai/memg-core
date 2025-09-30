# memg-core Knowledge Guide

*A structured memory-based guide to understanding memg-core architecture and development*

## What is memg-core?

**memg-core** is a deterministic, schema-driven memory engine designed as the foundation for AI agents that need structured, evolving memory systems. Unlike traditional RAG systems that store knowledge on "sticky notes," memg-core provides a true memory architecture that can:

- **Evolve**: Update and refine knowledge as new information arrives
- **Associate**: Link related concepts through meaningful relationships
- **Validate**: Enforce strict schema compliance with zero hardcoded fields
- **Scale**: Handle complex memory operations with dual-storage efficiency

### Core Philosophy

> *"To build effective memory for AI, we should take cues from the human brain. That means storing knowledge in structured form, linking it through meaningful associations, and layering retrieval so context can be recalled at the right depth."*

memg-core implements this philosophy through:
- **YAML-driven schema definition** - No hardcoded entity types
- **Dual-storage architecture** - Vector similarity + Graph relationships
- **Deterministic behavior** - Testable, auditable, reproducible
- **Offline-first design** - No API dependencies required

---

## Architecture Overview

### The Dual Storage Strategy

memg-core uses complementary storage systems that work together, not redundantly:

**🔍 Qdrant (Vector Storage)**
- Stores full memory payloads with embeddings
- Enables semantic search and similarity matching
- Primary entry point for queries

**🕸️ Kuzu (Graph Storage)**
- Stores relationships and metadata
- Enables associative memory traversal
- Expands search results through connections

**Flow**: Query → Vector Search (seeds) → Graph Expansion (neighbors) → Results

### YAML as Single Source of Truth

Everything in memg-core is driven by YAML schema:

```yaml
entities:
  - name: note
    parent: memo
    fields:
      statement: { type: string, required: true }
      project: { type: string }
    relations:
      document:
        - name: note_annotates_document
          predicate: ANNOTATES
          directed: true
```

**Key Components:**
- **TypeRegistry**: Loads YAML once, creates Pydantic models dynamically
- **YamlTranslator**: Validates all payloads against schema
- **Zero hardcoded fields**: Everything comes from YAML definition

---

## Memory Lifecycle

Understanding how memories flow through the system:

### 1. Creation Pipeline
```
User Input → YAML Validation → Memory Object → Timestamps →
HRID Generation → Anchor Text → Embedding → Dual Storage
```

**Key Steps:**
- `YamlTranslator` validates payload against schema
- `Memory` object created with system fields
- `HridTracker` generates human-readable ID (e.g., "NOTE_AAA001")
- Anchor text extracted from YAML-defined anchor field
- `FastEmbed` generates embedding vector
- Stored in both Qdrant (full payload) and Kuzu (relationships)

### 2. Retrieval Pipeline
```
Query → Embedding → Vector Search → Seeds → Graph Expansion →
Neighbors → Payload Projection → SearchResult
```

**Key Steps:**
- Query converted to embedding vector
- `VectorSearchHandler` finds similar memories (seeds)
- `GraphExpansionHandler` traverses relationships (neighbors)
- `PayloadProjector` filters fields based on detail level
- Results returned with explicit seed/neighbor separation

---

## API Usage Patterns

### Pattern 1: MemgClient (Recommended for Servers)

```python
from memg_core.api.public import MemgClient

# Initialize once, reuse throughout server lifetime
client = MemgClient(
    yaml_path="config/software_developer.yaml",
    db_path="/path/to/databases"
)

# Use throughout application
hrid = client.add_memory("note", {"statement": "..."}, "user123")
results = client.search("query", "user123", limit=10)

# Access results correctly
for memory_seed in results.memories:
    print(f"Found: {memory_seed.hrid}")
```

### Pattern 2: Environment-Based Functions

```python
from memg_core.api.public import add_memory, search, delete_memory, update_memory, get_memory, get_memories

# Set environment variables:
# MEMG_YAML_PATH, MEMG_DB_PATH

hrid = add_memory("note", {"statement": "..."}, "user123")
results = search("query", "user123")

# Access results correctly
for memory_seed in results.memories:
    print(f"Found: {memory_seed.hrid}")
```

### Key API Features

- **HRID-based interface**: Human-readable IDs like "NOTE_AAA001"
- **User isolation**: All operations scoped to user_id
- **Memory type filtering**: Search within specific entity types
- **Graph expansion**: Control neighbor traversal depth (hops parameter)
- **Relationship management**: add_relationship, delete_relationship functions
- **Memory retrieval**: get_memory, get_memories for direct access
- **Updates**: update_memory for partial payload updates
- **Datetime formatting**: Consistent timestamp presentation

---

## HRID System

**Human-Readable Identifiers** provide stable, user-friendly memory references:

- **Format**: `{TYPE}_{SEQUENCE}` (e.g., "TASK_AAA005", "DOCUMENT_AAA020")
- **Scope**: Generated per user_id for isolation
- **Persistence**: `HridTracker` manages UUID↔HRID mapping in Kuzu
- **Benefits**: API usability, debugging, deterministic references

**Usage:**
```python
# All public API operations use HRIDs
hrid = add_memory("task", payload, "user123")  # Returns "TASK_AAA001"
memory = get_memory("TASK_AAA001", "user123")  # Retrieve by HRID
delete_memory("TASK_AAA001", "user123")        # Delete by HRID
```

---

## Development Guidelines

### Working with YAML Schemas

1. **Define entities with inheritance**:
   ```yaml
   - name: task
     parent: memo  # Inherits memo fields
     fields:
       status: { type: enum, choices: [todo, done] }
   ```

2. **Use system fields appropriately**:
   - `id`, `user_id`, `created_at`, `vector` - handled automatically
   - Never include system fields in user payloads

3. **Define meaningful relationships**:
   ```yaml
   relations:
     bug:
       - name: task_addresses_bug
         predicate: ADDRESSES
         directed: true
   ```

### Error Handling Philosophy

memg-core follows **"crash early, crash clearly"** principles:
- No silent fallbacks or defaults
- Strict YAML validation with detailed error messages
- Type safety enforced at all levels
- Deterministic behavior for testing

### Performance Considerations

- **Vector search**: Primary bottleneck, optimize query embeddings
- **Graph expansion**: Limit hops and neighbor counts for large graphs
- **Payload projection**: Use appropriate detail levels (`none`, `self`, `all`)
- **Connection reuse**: Use `MemgClient` for long-running applications
- **Environment variables**: Use MEMG_YAML_PATH and MEMG_DB_PATH for configuration
- **Offline embeddings**: FastEmbed provides 384-dimensional vectors with no API keys required

---

## Memory Structure Navigation

This guide is backed by an interconnected memory structure in the system itself. You can explore these concepts using the search functionality:

### Core Learning Nodes
- **Architecture Overview**: `search("memg-core YAML-driven dual-storage")`
- **HRID System**: `search("HRID human-readable identifiers")`
- **Dual Storage**: `search("vector similarity graph relationships")`

### Detailed Documents
- **YAML Schema System**: `search("YAML drives memg-core behavior")`
- **API Usage Patterns**: `search("MemgClient public API patterns")`
- **Memory Lifecycle**: `search("memory creation retrieval pipeline")`

### Example Search with Graph Expansion
```python
results = search(
    query="memg-core architecture",
    user_id="cursor",
    hops=2,                    # Expand 2 levels in knowledge graph
    include_details="all",     # Full details for comprehensive view
    limit=5
)
```

---

## Next Steps for memg Development

With this foundational knowledge of memg-core, you're ready to:

1. **Design memory schemas** that fit your AI agent's needs
2. **Implement memory operations** using the public API patterns
3. **Build retrieval pipelines** that leverage both vector and graph search
4. **Create evolving memory systems** that can update and refine knowledge
5. **Develop the full memg ecosystem** with advanced memory policies

The memory structure created here serves as both documentation and a living example of how structured, interconnected knowledge can be more valuable than traditional documentation approaches.

---

*This guide represents the first experiment in creating "true memory for AI" - structured, interconnected, and capable of evolution. The knowledge contained here is stored in the same memg-core system it describes, demonstrating the principles in action.*
