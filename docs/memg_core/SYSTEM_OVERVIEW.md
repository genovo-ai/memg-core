# MEMG Core System Overview

## Executive Summary

MEMG Core is a **type-agnostic memory system for AI agents** built on the principle of **dual storage** (Kuzu graph + Qdrant vector) with **YAML-defined entity schemas**. The system follows a **GraphRAG retrieval approach**, prioritizing structural relationships while leveraging semantic similarity for reranking.

## Core Architecture Principles

1. **Type Agnosticism**: Core system has NO hardcoded memory types - all entity definitions live in YAML registries
2. **Dual Storage**: Kuzu handles relationships/structure, Qdrant handles vector similarity
3. **YAML-Driven**: Entity schemas, anchor fields, and relationships defined in external YAML
4. **Graph-First Retrieval**: GraphRAG prioritizes graph traversal, then vector reranking
5. **Single Writer Pattern**: Deterministic indexing prevents data inconsistency

## System Components Overview

### 🔌 API Layer (`api/`)
- **`public.py`**: Minimal external interface - `add_note()`, `add_document()`, `add_task()`, `search()`
- **Purpose**: Clean abstraction over complex pipeline operations
- **Key Functions**: Validates inputs, calls pipeline, handles YAML integration

### 🧠 Core Engine (`core/`)

#### Configuration & Setup
- **`config.py`**: Environment-driven configuration (thresholds, paths, dimensions)
- **`exceptions.py`**: Structured error hierarchy with context preservation
- **`logging.py`**: Centralized logging with operation/performance tracking

#### Data Models
- **`models.py`**: Type-agnostic primitives (`Memory`, `Entity`, `Relationship`, `SearchResult`)
- **Key Model**: `Memory` with `memory_type: str` and generic `payload: dict[str, Any]`

#### YAML Translation Engine
- **`yaml_translator.py`**: **CRITICAL** - Validates payloads against YAML schema, builds anchor text
- **`indexing.py`**: **DEPRECATED** - Legacy index building (being phased out)

#### Storage Interfaces
- **`interfaces/embedder.py`**: FastEmbed wrapper for local embeddings
- **`interfaces/kuzu.py`**: Simple Kuzu graph database CRUD operations
- **`interfaces/qdrant.py`**: Simple Qdrant vector database operations

#### Processing Pipeline
- **`pipeline/indexer.py`**: Deterministic dual-storage indexing (Qdrant + Kuzu)
- **`pipeline/retrieval.py`**: **GraphRAG** implementation - graph discovery → vector reranking → neighbor expansion

### 🔧 Plugins (`plugins/`)
- **`yaml_schema.py`**: **TRANSITIONAL** - Schema loading utilities (moving to core)

### 🎪 Showcase (`showcase/`)
- **`examples/simple_demo.py`**: Basic usage demonstration
- **`retriever.py`**: Convenience wrappers for specialized searches

### 📊 System Utilities (`system/`)
- **`info.py`**: Health checks and system statistics gathering

## Data Flow Architecture

```
Input → YAML Validation → Memory Creation → Dual Indexing → GraphRAG Retrieval
  ↓           ↓               ↓              ↓                ↓
User API → Translator → Memory Model → Kuzu+Qdrant → Graph+Vector Search
```

### Indexing Flow
1. **Input Validation**: Check `memory_type` exists in YAML schema
2. **Payload Validation**: Validate fields against entity definition
3. **Anchor Text Generation**: Extract embedding text from designated anchor field
4. **Dual Storage**: Index in both Kuzu (node) and Qdrant (vector point)

### Retrieval Flow (GraphRAG)
1. **Graph Discovery**: Query Kuzu for entity-based candidates
2. **Vector Reranking**: Use Qdrant to rescore candidates by semantic similarity
3. **Neighbor Expansion**: Add connected graph nodes to results
4. **Fallback**: Pure vector search if graph discovery fails

## Critical Evaluation & Redundancy Analysis

### ✅ Well-Aligned Components

**`yaml_translator.py`** - Perfectly embodies type-agnostic principle. Enables extensible entity definitions without core changes.

**`pipeline/retrieval.py`** - Excellent GraphRAG implementation that leverages both storage systems optimally.

**`models.py`** - Clean, minimal, type-agnostic data models that serve as stable foundation.

### ⚠️ Transitional/Redundant Components

**`indexing.py`** - **REDUNDANT** - Should be removed after `yaml_translator.py` fully replaces it.

**`plugins/yaml_schema.py`** - **TRANSITIONAL** - Moving to core, will be redundant once migration completes.

### 🔍 Potential Issues

**Dual Storage Complexity** - Maintaining consistency across Kuzu + Qdrant adds operational overhead. Consider if simpler approach would suffice.

**YAML Dependency** - System heavily relies on YAML schema correctness. Malformed YAML could break entire system.

**Showcase Layer Confusion** - `showcase/retriever.py` has placeholder methods that don't add value. Consider simplification.

### 📋 Alignment with Core Principles

| Component | Type-Agnostic | YAML-Driven | Graph-First | Single Writer |
|-----------|---------------|-------------|-------------|---------------|
| `yaml_translator.py` | ✅ | ✅ | ➖ | ➖ |
| `pipeline/retrieval.py` | ✅ | ➖ | ✅ | ➖ |
| `pipeline/indexer.py` | ✅ | ➖ | ➖ | ✅ |
| `models.py` | ✅ | ➖ | ➖ | ➖ |
| `indexing.py` | ❌ | ❌ | ➖ | ➖ |

## Recommended Actions

1. **Remove `indexing.py`** after confirming `yaml_translator.py` handles all cases
2. **Complete YAML schema migration** from plugins to core
3. **Simplify showcase layer** - remove placeholder methods
4. **Add YAML schema validation** on system startup
5. **Consider graph storage alternatives** if Kuzu proves overly complex

## Summary

MEMG Core successfully implements a type-agnostic memory system with strong separation of concerns. The YAML-driven approach enables extensibility without code changes. GraphRAG retrieval provides sophisticated search capabilities. Main areas for improvement: complete deprecated component removal and simplify transitional layers.

**Core Strength**: Type-agnostic design with YAML entity definitions
**Architecture Highlight**: GraphRAG retrieval combining structural and semantic search
**Key Refactoring Need**: Remove deprecated `indexing.py` and complete YAML migration
