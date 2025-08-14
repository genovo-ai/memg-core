# MEMG Core - Complete Documentation

*This document contains the complete concatenated documentation for MEMG Core.*

---

## Section 1: README.md

# MEMG Core Documentation

This directory contains the comprehensive documentation for the `memg-core` project, focusing on its architecture, modules, classes, and functions. The documentation is organized by module, with each Markdown file corresponding to a key component of the system.

## Start Here
- **[System Overview](SYSTEM_OVERVIEW.md)**: High-level architecture, data flow, and critical evaluation of all components

## Project Overview
MEMG Core ("True memory for AI") is a lightweight, open-source memory system designed for AI agents. It emphasizes a modular architecture with dual storage (Kuzu and Qdrant), type-agnostic memory handling via YAML registries, and a graph-first retrieval approach (GraphRAG).

## Module Documentation

### API Layer
- [`api/public.md`](api/public.md): Minimal public API for memory system interactions.

### Core Components
- [`core/config.md`](core/config.md): Configuration settings for the memory system.
- [`core/exceptions.md`](core/exceptions.md): Custom exception hierarchy for error handling.
- [`core/indexing.md`](core/indexing.md): Deprecated indexing logic (superseded by YAML translator).
- [`core/models.md`](core/models.md): Core data models (Memory, Entity, Relationship, etc.).
- [`core/yaml_translator.md`](core/yaml_translator.md): YAML to Memory translator for schema validation and anchor text generation.

#### Core Interfaces
- [`core/interfaces/embedder.md`](core/interfaces/embedder.md): FastEmbed-based text embedder.
- [`core/interfaces/kuzu.md`](core/interfaces/kuzu.md): Simple Kuzu graph database interface.
- [`core/interfaces/qdrant.md`](core/interfaces/qdrant.md): Simple Qdrant vector database interface.

#### Core Pipeline
- [`core/pipeline/indexer.md`](core/pipeline/indexer.md): Deterministic memory indexing pipeline.
- [`core/pipeline/retrieval.md`](core/pipeline/retrieval.md): Graph-first retrieval pipeline with vector reranking.

### Plugins
- [`plugins/yaml_schema.md`](plugins/yaml_schema.md): YAML schema loader for entity/relationship catalogs (to be moved to core).

### Showcase & Examples
- [`showcase/examples/simple_demo.md`](showcase/examples/simple_demo.md): A simple demonstration of the `memg-core` API.
- [`showcase/retriever.md`](showcase/retriever.md): Convenience wrappers and specialized search methods for memory retrieval.

### System Utilities
- [`system/info.md`](system/info.md): Utilities for retrieving core system information and health checks.
- [`utils/hrid.md`](utils/hrid.md): Human-Readable ID (HRID) generator and parser.

---

## Section 2: SYSTEM_OVERVIEW.md

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

---

## Section 3: api/public.md

# `memg_core/api/public.py`

## Module Description
This module provides a minimal public API that exposes a generic `add_memory` function and a unified `search` function. It uses the YAML translator to validate payloads and resolve an entity's anchor field to a `statement` for embedding. The `add_note`, `add_document`, and `add_task` functions are thin shims that build normalized payloads for their respective types. The `search` function supports vector-first, graph-first, or hybrid modes and allows for date-based scoping.

## Internal Dependencies
- `..core.config`: `get_config` for retrieving system configuration.
- `..core.exceptions`: `ValidationError` for input validation.
- `..core.interfaces.embedder`: `Embedder` for generating embeddings.
- `..core.interfaces.kuzu`: `KuzuInterface` for graph database operations.
- `..core.interfaces.qdrant`: `QdrantInterface` for vector database operations.
- `..core.models`: `Memory`, `SearchResult` for data models.
- `..core.pipeline.indexer`: `add_memory_index` for indexing memories.
- `..core.pipeline.retrieval`: `graph_rag_search` for memory retrieval.
- `..core.yaml_translator`: `build_anchor_text`, `create_memory_from_yaml` for YAML schema integration.
- `..plugins.yaml_schema`: `get_relation_names` (conditionally imported) for dynamic relation names.

## Functions

### `_index_memory_with_optional_yaml`
- **Description**: A helper function to index a memory using a YAML-driven anchor text if available. It initializes the necessary storage interfaces, resolves the anchor text via the YAML translator (suppressing fallbacks), and then upserts the memory into Qdrant and mirrors it to Kuzu.
- **Inputs**:
  - `memory`: Memory - The Memory object to be indexed.
- **Returns**: `str` - The point ID of the indexed memory in Qdrant.

### `add_note`
- **Description**: Adds a new memory of type 'note'. The `text` input is used as the `statement` field, which serves as the anchor for embedding.
- **Inputs**:
  - `text`: str - The content of the note, which becomes the `statement`.
  - `user_id`: str - Identifier for the user creating the note.
  - `title`: str | None - Optional title for the note.
  - `tags`: list[str] | None - Optional list of tags.
- **Returns**: `Memory` - The created Memory object.

### `add_document`
- **Description**: Adds a new memory of type 'document'. It normalizes the input so that `statement` (the anchor) is either the provided `summary` or a truncated version of the `text`, and the full content is stored in `details`.
- **Inputs**:
  - `text`: str - The main content body of the document.
  - `user_id`: str - Identifier for the user.
  - `title`: str | None - Optional title for the document.
  - `summary`: str | None - Optional summary, which is prioritized as the `statement` for embedding. If not provided, the `statement` is a truncated version of the `text`.
  - `tags`: list[str] | None - Optional list of tags.
- **Returns**: `Memory` - The created Memory object.

### `add_task`
- **Description**: Adds a new memory of type 'task'. The `text` is used as the `statement` (anchor), and a default `status` of "OPEN" is assigned.
- **Inputs**:
  - `text`: str - The description of the task, used as its `statement`.
  - `user_id`: str - Identifier for the user.
  - `title`: str | None - Optional title for the task.
  - `due_date`: datetime | None - Optional due date for the task.
  - `tags`: list[str] | None - Optional list of tags.
- **Returns**: `Memory` - The created Memory object.

### `search`
- **Description**: A unified search function that can query memories using vector, graph, or hybrid approaches. It requires at least one of `query` or `memo_type` to be provided. It initializes storage interfaces and calls the `graph_rag_search` pipeline function with various filtering and mode options.
- **Inputs**:
  - `query`: str | None - The search query string.
  - `user_id`: str - User ID for filtering search results.
  - `limit`: int = 20 - Maximum number of results to return.
  - `filters`: dict[str, Any] | None - Optional additional filters for vector search.
  - `memo_type`: str | None - (Keyword-only) Specific memory type to filter by.
  - `modified_within_days`: int | None - (Keyword-only) Scopes the search to memories modified within the last N days.
  - `mode`: str | None - (Keyword-only) The search mode to use. Can be 'vector', 'graph', or 'hybrid'.
- **Returns**: `list[SearchResult]` - A list of SearchResult objects, ranked by relevance.
- **Raises**: `ValidationError` - If both `query` and `memo_type` are missing.

### `add_memory`
- **Description**: A generic function to create and index a memory using a YAML-defined entity type and payload. It normalizes tags, validates the payload against the YAML schema, builds the `Memory` object via the translator, and then indexes it into both storage systems.
- **Inputs**:
  - `memory_type`: str - The entity type name (e.g., "note", "document", "task") as defined in the YAML schema.
  - `payload`: dict[str, Any] - Dictionary containing field values for the entity, as specified by the YAML schema.
  - `user_id`: str - User identifier for isolation.
  - `tags`: list[str] | None - Optional list of tags to associate with the memory.
- **Returns**: `Memory` - The created Memory object with its `id` populated from the indexing result.
- **Raises**: `ValidationError` - If `memory_type`, `user_id`, or `payload` are empty, or if the payload is invalid for the specified entity type according to the YAML schema.

---

## Section 4: core/config.md

# `memg_core/core/config.py`

## Module Description
This module defines the core configuration settings for the MEMG memory system. It includes data classes for memory-specific settings (`MemGConfig`) and system-wide settings (`MemorySystemConfig`), along with functions to load configurations primarily from environment variables.

## Internal Dependencies
- None

## Classes

### `MemGConfig`
- **Description**: Dataclass holding core memory system configuration parameters such as similarity thresholds, processing settings, and database names. It includes validation logic upon initialization and methods for conversion to/from dictionaries and environment variables.
- **Attributes**:
  - `similarity_threshold`: float = 0.7 - Threshold for conflict detection.
  - `score_threshold`: float = 0.3 - Minimum score for search results.
  - `high_similarity_threshold`: float = 0.9 - Threshold for duplicate detection.
  - `max_summary_tokens`: int = 750 - Maximum tokens for document summarization.
  - `enable_ai_type_verification`: bool = True - Flag for AI-based type detection.
  - `enable_temporal_reasoning`: bool = False - Flag to enable temporal reasoning.
  - `vector_dimension`: int = 384 - Dimension of embedding vectors.
  - `batch_processing_size`: int = 50 - Batch size for bulk operations.
  - `template_name`: str = "default" - Name of the active template.
  - `qdrant_collection_name`: str = "memories" - Name of the Qdrant collection.
  - `kuzu_database_path`: str = "kuzu_db" - Path to the Kuzu database.
- **Methods**:
  - `__post_init__`:
    - **Description**: Validates the range of threshold parameters and `max_summary_tokens` after initialization.
    - **Inputs**: None
    - **Returns**: None
  - `to_dict`:
    - **Description**: Converts the `MemGConfig` instance into a dictionary.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - Dictionary representation of the configuration.
  - `from_dict` (classmethod):
    - **Description**: Creates a `MemGConfig` instance from a dictionary.
    - **Inputs**:
      - `config_dict`: dict[str, Any] - Dictionary containing configuration parameters.
    - **Returns**: `MemGConfig` - A new `MemGConfig` object.
  - `from_env` (classmethod):
    - **Description**: Creates a `MemGConfig` instance by reading configuration values from environment variables. Provides default values if environment variables are not set.
    - **Inputs**: None
    - **Returns**: `MemGConfig` - A new `MemGConfig` object populated from environment variables.

### `MemorySystemConfig`
- **Description**: Dataclass representing system-wide configuration, including a nested `MemGConfig` instance, debug mode, logging level, and MCP server settings.
- **Attributes**:
  - `memg`: MemGConfig - An instance of `MemGConfig` for memory-specific settings.
  - `debug_mode`: bool = False - Flag for enabling debug mode.
  - `log_level`: str = "INFO" - Logging level for the system.
  - `mcp_port`: int = 8787 - Port number for the MCP server.
  - `mcp_host`: str = "0.0.0.0" - Host address for the MCP server.
- **Methods**:
  - `__post_init__`:
    - **Description**: Validates the `mcp_port` and `log_level` parameters after initialization.
    - **Inputs**: None
    - **Returns**: None
  - `from_env` (classmethod):
    - **Description**: Creates a `MemorySystemConfig` instance by reading system configuration values from environment variables. It also calls `MemGConfig.from_env` to populate nested memory configurations.
    - **Inputs**: None
    - **Returns**: `MemorySystemConfig` - A new `MemorySystemConfig` object populated from environment variables.

## Functions

### `get_config`
- **Description**: Retrieves the system configuration, prioritizing values set via environment variables.
- **Inputs**: None
- **Returns**: `MemorySystemConfig` - The current system configuration.

---

## Section 5: core/exceptions.md

# `memg_core/core/exceptions.py`

## Module Description
This module defines a custom exception hierarchy for the MEMG memory system. It provides specific exception classes for different types of errors (e.g., configuration, database, validation, processing) and utility functions for wrapping generic exceptions with more context.

## Internal Dependencies
- None

## Classes

### `MemorySystemError`
- **Description**: Base exception for all errors within the memory system. It extends Python's `Exception` and allows for storing additional context such as the operation being performed and the original error that caused it.
- **Attributes**:
  - `message`: str - The main error message.
  - `operation`: str | None - The name of the operation during which the error occurred.
  - `context`: dict[str, Any] - A dictionary providing additional context about the error.
  - `original_error`: Exception | None - The original exception that triggered this error.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `MemorySystemError` instance with a message, optional operation, context, and original error.
    - **Inputs**:
      - `message`: str - The primary error message.
      - `operation`: str | None = None - The operation name.
      - `context`: dict[str, Any] | None = None - Additional context as a dictionary.
      - `original_error`: Exception | None = None - The underlying exception.
    - **Returns**: None

### `ConfigurationError`
- **Description**: A subclass of `MemorySystemError` specifically for errors related to configuration, such as invalid environment variables or configuration validation failures.

### `DatabaseError`
- **Description**: A subclass of `MemorySystemError` for failures during database operations, covering issues with Qdrant or Kuzu interactions.

### `ValidationError`
- **Description**: A subclass of `MemorySystemError` for errors arising from data validation failures, such as schema mismatches or invalid input formats.

### `ProcessingError`
- **Description**: A subclass of `MemorySystemError` serving as a catch-all for failures that occur during memory processing operations within the pipeline.

## Functions

### `wrap_exception`
- **Description**: Wraps a generic Python exception in an appropriate `MemorySystemError` subclass based on the type of the original error. It maps common exceptions like `FileNotFoundError`, `PermissionError`, and `ValueError` to specific `MemorySystemError` types.
- **Inputs**:
  - `original_error`: Exception - The exception to be wrapped.
  - `operation`: str - The name of the operation where the error occurred.
  - `context`: dict[str, Any] | None = None - Optional additional context for the error.
- **Returns**: `MemorySystemError` - An instance of a `MemorySystemError` subclass.

### `handle_with_context`
- **Description**: A decorator that provides consistent error handling by wrapping function executions. It catches exceptions, re-raises `MemorySystemError` instances as-is, and wraps other unknown exceptions using `wrap_exception`, adding contextual information.
- **Inputs**:
  - `operation`: str - The name of the operation to be used in error messages.
- **Returns**: `Callable` - A decorator function.

---

## Section 6: core/models.md

# `memg_core/core/models.py`

## Module Description
This module defines the core, type-agnostic data models for the MEMG memory system. These models are designed to be minimal, stable, and extensible, providing foundational structures for various memory components like `Memory`, `Entity`, `Relationship`, `MemoryPoint`, `SearchResult`, and `ProcessingResult`.

## Internal Dependencies
- None

## External Dependencies
- `datetime`: `UTC`, `datetime` for handling temporal fields.
- `typing`: `Any` for flexible type annotations.
- `uuid`: `uuid4` for generating unique identifiers.
- `pydantic`: `BaseModel`, `ConfigDict`, `Field`, `field_validator` for data validation and model definition.

## Classes

### `Memory`
- **Description**: A type-agnostic data model representing a single piece of memory in the system. It encapsulates core identification, a generic payload for entity-specific fields, metadata, temporal information, and version tracking.
- **Attributes**:
  - `id`: str - Unique identifier for the memory (defaults to a new UUID).
  - `user_id`: str - User ID for isolating memories by user.
  - `memory_type`: str - The name of the entity type as defined in the YAML schema (e.g., "note", "document").
  - `payload`: dict[str, Any] - A dictionary containing entity-specific fields, as defined in the YAML schema.
  - `tags`: list[str] - A flexible list of tags for categorization.
  - `confidence`: float - A confidence score for the memory's storage (between 0.0 and 1.0).
  - `vector`: list[float] | None - The embedding vector associated with the memory.
  - `is_valid`: bool - A flag indicating whether the memory is currently considered valid.
  - `created_at`: datetime - The timestamp when the memory was created.
  - `supersedes`: str | None - The ID of a previous memory that this one supersedes.
  - `superseded_by`: str | None - The ID of a subsequent memory that supersedes this one.
- **Methods**:
  - `to_qdrant_payload`:
    - **Description**: Converts the `Memory` object into a nested dictionary suitable for storage as a payload in Qdrant. It separates core metadata from entity-specific fields.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Qdrant payload.
  - `to_kuzu_node`:
    - **Description**: Converts the `Memory` object into a dictionary of properties for creating a node in Kuzu. It includes core metadata and flattens specific, queryable fields from the payload, such as `statement`, `title`, and task-related attributes.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu node properties.
  - `memory_type_not_empty` (field_validator):\
    - **Description**: A Pydantic field validator that ensures the `memory_type` field is not empty or consists only of whitespace.
    - **Inputs**:\
      - `v`: str - The value of the `memory_type` field.
    - **Returns**: `str` - The stripped `memory_type` value.
    - **Raises**: `ValueError` - If the `memory_type` is empty.

### `Entity`
- **Description**: A data model representing an extracted entity from memories. These entities are typically nodes in the Kuzu graph database and are used for structural organization and retrieval.
- **Attributes**:
  - `id`: str | None - Unique identifier for the entity (defaults to a new UUID).
  - `user_id`: str - User ID for isolating entities by user.
  - `name`: str - The name of the entity.
  - `type`: str - The type of the entity (e.g., "PERSON", "TECHNOLOGY").
  - `description`: str - A textual description of the entity.
  - `confidence`: float - A confidence score for the entity extraction.
  - `created_at`: datetime - The timestamp when the entity was created.
  - `is_valid`: bool - A flag indicating whether the entity is currently valid.
  - `source_memory_id`: str | None - The ID of the memory from which this entity was extracted.
- **Methods**:
  - `to_kuzu_node`:\
    - **Description**: Converts the `Entity` object into a dictionary of properties suitable for creating a node in the Kuzu graph database.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu node properties.

### `Relationship`
- **Description**: A data model representing a relationship between two entities or memories in the graph database.
- **Attributes**:
  - `id`: str | None - Unique identifier for the relationship (defaults to a new UUID).
  - `user_id`: str - User ID for isolating relationships by user.
  - `source_id`: str - The ID of the source node of the relationship.
  - `target_id`: str - The ID of the target node of the relationship.
  - `relationship_type`: str - The type of the relationship (e.g., "MENTIONS", "HAS_PROPERTY").
  - `confidence`: float - A confidence score for the relationship.
  - `created_at`: datetime - The timestamp when the relationship was created.
  - `is_valid`: bool - A flag indicating whether the relationship is currently valid.
- **Methods**:
  - `to_kuzu_props`:\
    - **Description**: Converts the `Relationship` object into a dictionary of properties suitable for creating a relationship in the Kuzu graph database.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu relationship properties.

### `MemoryPoint`
- **Description**: A data model that combines a `Memory` object with its embedding vector and an optional Qdrant point ID, designed for representing memories specifically for Qdrant storage.
- **Attributes**:
  - `memory`: Memory - The associated `Memory` object.
  - `vector`: list[float] - The embedding vector for the memory.
  - `point_id`: str | None - The unique ID assigned by Qdrant to this point.
- **Methods**:
  - `vector_not_empty` (field_validator):\
    - **Description**: A Pydantic field validator that ensures the `vector` field is not an empty list.
    - **Inputs**:\
      - `v`: list[float] - The embedding vector.
    - **Returns**: `list[float]` - The validated vector.
    - **Raises**: `ValueError` - If the `vector` is empty.

### `SearchResult`
- **Description**: A data model representing a single result from a memory search operation, including the found memory, its relevance score, and the search source.
- **Attributes**:
  - `memory`: Memory - The `Memory` object found by the search.
  - `score`: float - The similarity score of the memory to the query.
  - `distance`: float | None - The vector distance, if applicable.
  - `source`: str - The source of the search result (e.g., "qdrant", "kuzu", "hybrid").
  - `metadata`: dict[str, Any] - Additional metadata related to the search result.

### `ProcessingResult`
- **Description**: A data model encapsulating the outcome of a memory processing pipeline operation, including success status, lists of created memories, entities, and relationships, and any errors encountered.
- **Attributes**:
  - `success`: bool - Indicates whether the processing operation was successful.
  - `memories_created`: list[Memory] - A list of `Memory` objects created during processing.
  - `entities_created`: list[Entity] - A list of `Entity` objects created during processing.
  - `relationships_created`: list[Relationship] - A list of `Relationship` objects created during processing.
  - `errors`: list[str] - A list of error messages encountered during processing.
  - `processing_time_ms`: float | None - The time taken for processing in milliseconds.
- **Properties**:
  - `total_created`:\
    - **Description**: Calculates the total number of memories, entities, and relationships created.
    - **Inputs**: None
    - **Returns**: `int` - The sum of all created items.

---

## Section 7: core/logging.md

# `memg_core/core/logging.py`

## Module Description
This module provides a centralized logging configuration for the MEMG memory system. It offers a `MemorySystemLogger` class for setting up and managing loggers, along with convenience functions for logging operations, performance metrics, and errors with consistent formatting and contextual information.

## Internal Dependencies
- None

## External Dependencies
- `logging`: Python's standard logging library.
- `pathlib`: `Path` for handling file paths.
- `sys`: For interacting with the Python interpreter, specifically `sys.stdout` for console logging.

## Classes

### `MemorySystemLogger`
- **Description**: A class that manages the centralized logging for the MEMG system. It allows for configuring root and component-specific loggers, handling console and file output, and providing structured logging for various event types.
- **Attributes**:
  - `_loggers`: dict[str, logging.Logger] - A class-level dictionary to store created logger instances, keyed by their full names.
  - `_configured`: bool - A class-level flag indicating whether the root logger has been configured.
- **Methods**:
  - `setup_logging` (classmethod):
    - **Description**: Configures the centralized logging for the entire memory system. It creates and configures a root logger (`memg_core`) with optional console and file handlers. It ensures that logging is configured only once.
    - **Inputs**:
      - `level`: str = "INFO" - The default logging level for console output (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
      - `log_file`: str | None = None - Optional path to a log file. If provided, logs will also be written to this file.
      - `console_output`: bool = True - If True, logs will be printed to the console.
      - `file_level`: str | None = None - Optional logging level specifically for the file output. Defaults to `level` if not provided.
    - **Returns**: `logging.Logger` - The root logger instance for `memg_core`.
  - `get_logger` (classmethod):
    - **Description**: Retrieves an existing logger for a specific component or creates a new one if it doesn't exist. If the root logger hasn't been configured, it calls `setup_logging` to perform a basic configuration.
    - **Inputs**:
      - `component`: str - The name of the component for which to get the logger (e.g., "api", "core.pipeline").
    - **Returns**: `logging.Logger` - The logger instance for the specified component.
  - `log_operation` (classmethod):
    - **Description**: Logs a general operation with structured context. The log message includes the operation name and a pipe-separated list of context key-value pairs.
    - **Inputs**:
      - `component`: str - The component logging the operation.
      - `operation`: str - A descriptive name for the operation.
      - `level`: str = "INFO" - The logging level for this message (e.g., "INFO", "DEBUG").
      - `**context`: Any - Arbitrary keyword arguments representing contextual information.
    - **Returns**: None
  - `log_performance` (classmethod):
    - **Description**: Logs performance metrics for operations, including the duration in milliseconds and any additional context. Messages are prefixed with a '⚡' symbol.
    - **Inputs**:
      - `component`: str - The component logging the performance.
      - `operation`: str - The name of the operation measured.
      - `duration_ms`: float - The duration of the operation in milliseconds.
      - `**context`: Any - Arbitrary keyword arguments for additional context.
    - **Returns**: None
  - `log_error` (classmethod):
    - **Description**: Logs error messages with consistent formatting, including the exception type and message, and additional context. Errors are logged with `logging.ERROR` level and `exc_info=True` for traceback inclusion.
    - **Inputs**:
      - `component`: str - The component where the error occurred.
      - `operation`: str - The name of the operation that failed.
      - `error`: Exception - The exception object caught.
      - `**context`: Any - Arbitrary keyword arguments for additional context.
    - **Returns**: None

## Functions

### `get_logger`
- **Description**: Convenience function to get a logger instance for a given component.
- **Inputs**:
  - `component`: str - The component name.
- **Returns**: `logging.Logger` - The logger instance.

### `setup_memory_logging`
- **Description**: Convenience function to set up the memory system's logging, forwarding parameters to `MemorySystemLogger.setup_logging`.
- **Inputs**:
  - `level`: str = "INFO" - The default logging level.
  - `log_file`: str | None = None - Optional path to a log file.
- **Returns**: `logging.Logger` - The root logger instance.

### `log_operation`
- **Description**: Convenience function to log an operation with context, forwarding parameters to `MemorySystemLogger.log_operation`.
- **Inputs**:
  - `component`: str - The component name.
  - `operation`: str - The operation name.
  - `**context`: Any - Additional context.
- **Returns**: None

### `log_performance`
- **Description**: Convenience function to log performance metrics, forwarding parameters to `MemorySystemLogger.log_performance`.
- **Inputs**:
  - `component`: str - The component name.
  - `operation`: str - The operation name.
  - `duration_ms`: float - The duration in milliseconds.
  - `**context`: Any - Additional context.
- **Returns**: None

### `log_error`
- **Description**: Convenience function to log errors with context, forwarding parameters to `MemorySystemLogger.log_error`.
- **Inputs**:
  - `component`: str - The component name.
  - `operation`: str - The operation name.
  - `error`: Exception - The exception object.
  - `**context`: Any - Additional context.
- **Returns**: None

---

## Section 8: core/indexing.md

# `memg_core/core/indexing.py`

## Module Description
This module contains **DEPRECATED** indexing logic. Its functions have been superseded by the YAML translator module, which handles anchor text generation based on YAML-defined entity schemas. This module is retained for backward compatibility but is slated for removal.

## Internal Dependencies
- `..models`: `Memory` for the memory data model.

## Functions

### `build_index_text`
- **Description**: **DEPRECATED**. This function previously built the index text for a memory. It attempts to extract text from the `content` or `summary` fields within the memory's payload. This functionality has been replaced by `build_anchor_text` in `yaml_translator.py`, which uses a more robust YAML-defined anchor field strategy.
- **Inputs**:
  - `memory`: Memory - The Memory object for which to build index text.
- **Returns**: `str` - The extracted index text, or a fallback string if no relevant fields are found.

---

## Section 9: core/yaml_translator.md

# `memg_core/core/yaml_translator.py`

## Module Description
This module provides the core functionality for translating YAML entity definitions into the `Memory` data model, making the system type-agnostic. It reads entity definitions from a YAML registry and supports flexible schema shapes (entities as a dictionary or a list). Key functionalities include validating payloads against the schema, resolving anchor text for embeddings with robust fallbacks, and creating `Memory` objects. If a YAML schema is not present, it falls back to using common field names like `statement` or `summary` for anchor text.

## Internal Dependencies
- `..exceptions`: `MemorySystemError`, `YamlTranslatorError` for specific translator errors.
- `..models`: `Memory` for the core data model.

## External Dependencies
- `functools`: `lru_cache` for caching the YAML translator instance.
- `os`: For interacting with environment variables.
- `pathlib`: `Path` for handling file paths.
- `typing`: `Any` for flexible type annotations.
- `pydantic`: `BaseModel`, `Field` for data validation and model definition.
- `yaml`: For loading YAML schema files.

## Classes

### `YamlTranslatorError`
- **Description**: A custom exception class specifically for errors that occur within the YAML translator module. It inherits from `MemorySystemError`.

### `EntitySpec`
- **Description**: A Pydantic BaseModel that defines the structure of an entity specification as parsed from the YAML schema.
- **Attributes**:
  - `name`: str - The name of the entity type (e.g., "note", "document").
  - `description`: str | None - A brief description of the entity type.
  - `anchor`: str - The name of the payload field to be used as anchor text. Defaults to "statement".
  - `fields`: dict[str, Any] | None - A flexible dictionary defining the schema and properties of each field.

### `YamlTranslator`
- **Description**: The main class responsible for loading, caching, and translating YAML entity definitions. It provides methods to retrieve entity specifications, determine anchor fields, build anchor text from `Memory` objects, and validate/create `Memory` objects based on the YAML schema. It can handle various YAML structures and provides fallbacks when a schema is missing or incomplete.
- **Attributes**:
  - `yaml_path`: str | None - The file path to the YAML schema.
  - `_schema`: dict[str, Any] | None - A cached dictionary representation of the loaded YAML schema.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `YamlTranslator` instance with an optional YAML schema file path. It prioritizes an explicitly provided path, then the `MEMG_YAML_SCHEMA` environment variable.
    - **Inputs**:
      - `yaml_path`: str | None = None - The path to the YAML schema file.
    - **Returns**: None
  - `schema` (property):
    - **Description**: Property that loads and caches the YAML schema from the `yaml_path`.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - The loaded YAML schema as a dictionary.
    - **Raises**: `YamlTranslatorError` - If `MEMG_YAML_SCHEMA` is not set, the file is not found, or the YAML is invalid/empty.
  - `_load_schema` (private):
    - **Description**: Internal method to perform the actual loading of the YAML schema file from the specified path. It handles file existence, parsing, and potential YAML syntax errors.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - The loaded YAML schema.
    - **Raises**: `YamlTranslatorError` - For file system issues, invalid YAML syntax, or empty schema.
  - `_entities_map` (private):
    - **Description**: Normalizes the 'entities' section of the YAML schema into a consistent dictionary format, whether it's defined as a list or a dictionary.
    - **Inputs**: None
    - **Returns**: `dict[str, dict[str, Any]]` - A dictionary of entity specifications, keyed by their lowercase name.
  - `get_entity_spec`:
    - **Description**: Retrieves the `EntitySpec` for a given entity name by looking it up in the normalized entity map from the YAML schema.
    - **Inputs**:
      - `entity_name`: str - The name of the entity type (e.g., "note", "document", "task").
    - **Returns**: `EntitySpec` - The Pydantic model representing the entity's specification.
    - **Raises**: `YamlTranslatorError` - If the specified entity name is empty or not found in the schema.
  - `get_anchor_field`:
    - **Description**: Returns the name of the anchor field for a given entity type. If the type is not found in the YAML schema, it falls back to "statement".
    - **Inputs**:
      - `entity_name`: str - The name of the entity type.
    - **Returns**: `str` - The name of the anchor field.
  - `build_anchor_text`:
    - **Description**: Constructs the anchor text from a `Memory` object. It first attempts to use the anchor field defined in the YAML schema, but includes a robust fallback mechanism that checks a list of common fields (`statement`, `summary`, `content`, etc.) to find the first non-empty string.
    - **Inputs**:
      - `memory`: Memory - The `Memory` object from which to build the anchor text.
    - **Returns**: `str` - The extracted and stripped anchor text.
    - **Raises**: `YamlTranslatorError` - If no valid anchor text can be resolved from any of the candidate fields.
  - `_fields_contract` (private):
    - **Description**: Determines the required and optional fields for an entity based on its specification in the YAML schema. It supports both a flat dictionary of fields and a structured `{ "required": [...], "optional": [...] }` format.
    - **Inputs**:
        - `spec`: dict[str, Any] - The raw entity specification dictionary from the YAML schema.
    - **Returns**: `tuple[list[str], list[str]]` - A tuple containing two lists: required field names and optional field names.
  - `validate_memory_against_yaml`:
    - **Description**: Validates a memory payload against the fields defined in the YAML schema for a specific `memory_type`. If the entity type is not found in the schema, the payload is returned as-is. Otherwise, it checks for the presence of required fields and strips any system-reserved keys from the payload.
    - **Inputs**:
      - `memory_type`: str - The name of the memory type (entity name).
      - `payload`: dict[str, Any] - The raw payload dictionary to validate.
    - **Returns**: `dict[str, Any]` - The validated payload, with system-reserved keys removed.
    - **Raises**: `YamlTranslatorError` - If a required field is missing from the payload.
  - `create_memory_from_yaml`:
    - **Description**: Creates a `Memory` object from a given `memory_type`, `payload`, and `user_id` after validating the payload against the YAML schema.
    - **Inputs**:
      - `memory_type`: str - The name of the entity type.
      - `payload`: dict[str, Any] - The dictionary of field values for the entity.
      - `user_id`: str - The user ID for the memory.
    - **Returns**: `Memory` - The newly created and populated `Memory` object.

## Functions

### `get_yaml_translator`
- **Description**: A globally accessible, cached function that returns a singleton instance of `YamlTranslator`. This ensures that the YAML schema is loaded and parsed only once.
- **Inputs**: None
- **Returns**: `YamlTranslator` - The cached instance of the translator.

### `build_anchor_text`
- **Description**: A convenience function that delegates to the `YamlTranslator` instance's `build_anchor_text` method. It is used to get the primary text for vector embedding from a `Memory` object based on its YAML definition.
- **Inputs**:
  - `memory`: Memory - The `Memory` object.
- **Returns**: `str` - The anchor text.

### `create_memory_from_yaml`
- **Description**: A convenience function that delegates to the `YamlTranslator` instance's `create_memory_from_yaml` method. It facilitates the creation of `Memory` objects, validating their payloads against the YAML schema.
- **Inputs**:
  - `memory_type`: str - The name of the entity type.
  - `payload`: dict[str, Any] - The raw payload dictionary.
  - `user_id`: str - The user ID for the memory.
- **Returns**: `Memory` - The created `Memory` object.

---

## Section 10: core/interfaces/embedder.md

# `memg_core/core/interfaces/embedder.py`

## Module Description
This module provides an interface for generating text embeddings using `FastEmbed`. It's designed for local execution, eliminating the need for external API keys for embedding generation. It supports embedding single texts or lists of texts.

## Internal Dependencies
- None

## External Dependencies
- `fastembed`: `TextEmbedding` for generating embeddings.

## Classes

### `Embedder`
- **Description**: A wrapper class around the `FastEmbed` library, providing methods to generate vector embeddings for text. It allows for specification of a model name, defaulting to an environment variable or a predefined model.
- **Attributes**:
  - `model_name`: str - The name of the FastEmbed model being used.
  - `model`: TextEmbedding - An instance of the `TextEmbedding` class from `fastembed`.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `Embedder` with an optional model name. It prioritizes the `EMBEDDER_MODEL` environment variable, then a default model.
    - **Inputs**:
      - `model_name`: str | None = None - The specific model name to use for embeddings.
    - **Returns**: None
  - `get_embedding`:
    - **Description**: Generates a single embedding vector for a given text string.
    - **Inputs**:
      - `text`: str - The input text to be embedded.
    - **Returns**: `list[float]` - A list of floats representing the embedding vector.
    - **Raises**: `RuntimeError` - If FastEmbed returns an empty embedding.
  - `get_embeddings`:
    - **Description**: Generates embedding vectors for a list of text strings.
    - **Inputs**:
      - `texts`: list[str] - A list of input texts to be embedded.
    - **Returns**: `list[list[float]]` - A list of lists of floats, where each inner list is an embedding vector for the corresponding input text.

---

## Section 11: core/interfaces/kuzu.md

# `memg_core/core/interfaces/kuzu.py`

## Module Description
This module provides a simple wrapper interface for interacting with the Kuzu graph database. It encapsulates basic CRUD (Create, Read, Update, Delete) operations for nodes and relationships, as well as general Cypher query execution and neighbor fetching. It focuses purely on I/O operations with the Kuzu database.

## Internal Dependencies
- `..exceptions`: `DatabaseError` for handling database-related exceptions.

## External Dependencies
- `kuzu`: The Kuzu database client library.

## Classes

### `KuzuInterface`
- **Description**: A class that provides a simplified, high-level interface for performing operations on a Kuzu graph database. It manages the database connection and offers methods to add nodes, add relationships, execute Cypher queries, and retrieve node neighbors.
- **Attributes**:
  - `db`: kuzu.Database - The Kuzu database instance.
  - `conn`: kuzu.Connection - The connection object to the Kuzu database.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the Kuzu interface by establishing a connection to the database at the specified `db_path`. It resolves the path from environment variables if not provided directly and creates necessary directories.
    - **Inputs**:
      - `db_path`: str | None = None - The file path to the Kuzu database. If None, it defaults to the `KUZU_DB_PATH` environment variable.
    - **Returns**: None
    - **Raises**: `DatabaseError` - If `KUZU_DB_PATH` is not set or if there's a failure in initializing the Kuzu database.
  - `add_node`:
    - **Description**: Adds a new node to the graph database. It dynamically creates node tables (`Entity` or `Memory`) if they don't already exist, based on the provided `table` argument.
    - **Inputs**:
      - `table`: str - The name of the node table (e.g., "Entity", "Memory").
      - `properties`: dict[str, Any] - A dictionary of properties for the new node.
    - **Returns**: `None`
    - **Raises**: `DatabaseError` - If the node cannot be added to the specified table.
  - `add_relationship`:
    - **Description**: Adds a relationship between two existing nodes in the graph. It sanitizes the relationship type and creates the relationship table if it does not exist. It also handles schema mismatches by dropping and recreating the table.
    - **Inputs**:
      - `from_table`: str - The label of the source node's table.
      - `to_table`: str - The label of the target node's table.
      - `rel_type`: str - The type of the relationship (e.g., "MENTIONS", "RELATED_TO").
      - `from_id`: str - The ID of the source node.
      - `to_id`: str - The ID of the target node.
      - `props`: dict[str, Any] | None = None - Optional dictionary of properties for the relationship.
    - **Returns**: `None`
    - **Raises**: `DatabaseError` - If the relationship cannot be added.
  - `_extract_query_results` (private):
    - **Description**: Extracts and formats results from a Kuzu `QueryResult` object into a list of dictionaries.
    - **Inputs**:
      - `query_result`: Any - The raw query result object returned by Kuzu.
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries, where each dictionary represents a row in the query result.
  - `query`:
    - **Description**: Executes a Cypher query against the Kuzu database and returns the results. It handles optional parameters for the query.
    - **Inputs**:
      - `cypher`: str - The Cypher query string to execute.
      - `params`: dict[str, Any] | None = None - Optional dictionary of parameters to pass to the query.
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries representing the query results.
    - **Raises**: `DatabaseError` - If the query execution fails.
  - `neighbors`:
    - **Description**: Fetches the neighbors of a specified node in the graph, optionally filtered by relationship types, direction, and neighbor node labels. It constructs the appropriate Cypher query for neighbor retrieval.
    - **Inputs**:
      - `node_label`: str - The label of the starting node (e.g., "Memory", "Entity").
      - `node_id`: str - The ID of the starting node.
      - `rel_types`: list[str] | None = None - Optional list of relationship types to traverse.
      - `direction`: str = "any" - The direction of relationships to follow ("in", "out", or "any").
      - `limit`: int = 10 - The maximum number of neighbors to return.
      - `neighbor_label`: str | None = None - Optional label for the neighbor nodes.
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries, each representing a neighbor node and its relationship type.
    - **Raises**: `DatabaseError` - If fetching neighbors fails.
  - `_get_kuzu_type` (private):
    - **Description**: A helper method to map Python data types to their corresponding Kuzu database types. It's used internally for dynamic schema creation.
    - **Inputs**:
      - `key`: str - The name of the property.
      - `value`: Any - The Python value of the property.
    - **Returns**: `str` - The Kuzu data type string (e.g., "STRING", "DOUBLE", "BOOLEAN").

---

## Section 12: core/interfaces/qdrant.md

# `memg_core/core/interfaces/qdrant.py`

## Module Description
This module provides a simple wrapper interface for interacting with the Qdrant vector database. It focuses on pure I/O operations, including managing collections, adding and searching vector points, retrieving points by ID, deleting points, and fetching collection information.

## Internal Dependencies
- `..exceptions`: `DatabaseError` for handling database-related exceptions.

## External Dependencies
- `qdrant_client`: `QdrantClient`, `Distance`, `FieldCondition`, `Filter`, `MatchAny`, `MatchValue`, `PointStruct`, `Range`, `VectorParams` for Qdrant database interactions.
- `uuid`: For generating UUIDs for point IDs.

## Classes

### `QdrantInterface`
- **Description**: A class that provides a simplified, high-level interface for performing CRUD and search operations on a Qdrant vector database. It handles collection management and vector point operations.
- **Attributes**:
  - `client`: QdrantClient - An instance of the Qdrant client.
  - `collection_name`: str - The name of the Qdrant collection being managed.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the Qdrant interface. It sets up the Qdrant client, using a specified `storage_path` or deriving it from the `QDRANT_STORAGE_PATH` environment variable. It ensures the storage directory exists.
    - **Inputs**:
      - `collection_name`: str = "memories" - The name of the collection to operate on.
      - `storage_path`: str | None = None - The file path for Qdrant storage. If None, it defaults to the `QDRANT_STORAGE_PATH` environment variable.
    - **Returns**: None
    - **Raises**: `DatabaseError` - If `QDRANT_STORAGE_PATH` is not set or if there's an error in initialization.
  - `collection_exists`:
    - **Description**: Checks if a specified Qdrant collection exists.
    - **Inputs**:
      - `collection`: str | None = None - The name of the collection to check. Defaults to the instance's `collection_name`.
    - **Returns**: `bool` - True if the collection exists, False otherwise.
    - **Raises**: `DatabaseError` - If an error occurs while checking collection existence.
  - `create_collection`:
    - **Description**: Creates a new Qdrant collection with a specified vector size and cosine distance. If the collection already exists, it returns True.
    - **Inputs**:
      - `collection`: str | None = None - The name of the collection to create. Defaults to the instance's `collection_name`.
      - `vector_size`: int = 384 - The dimension of the vectors to be stored in the collection.
    - **Returns**: `bool` - True if the collection is created or already exists, False otherwise.
    - **Raises**: `DatabaseError` - If an error occurs during collection creation.
  - `ensure_collection`:
    - **Description**: Ensures that a Qdrant collection exists, creating it if it doesn't.
    - **Inputs**:
      - `collection`: str | None = None - The name of the collection to ensure. Defaults to the instance's `collection_name`.
      - `vector_size`: int = 384 - The vector dimension for the collection if it needs to be created.
    - **Returns**: `bool` - True if the collection exists or was successfully created.
  - `add_point`:
    - **Description**: Adds a single vector point with a payload to the specified Qdrant collection. It generates a UUID for the point ID if not provided.
    - **Inputs**:
      - `vector`: list[float] - The embedding vector for the point.
      - `payload`: dict[str, Any] - The associated payload data for the point.
      - `point_id`: str | None = None - Optional unique ID for the point. If None, a new UUID is generated.
      - `collection`: str | None = None - The target collection name. Defaults to the instance's `collection_name`.
    - **Returns**: `tuple[bool, str]` - A tuple containing a boolean indicating success and the ID of the added point.
    - **Raises**: `DatabaseError` - If an error occurs while adding the point.
  - `search_points`:
    - **Description**: Searches for similar vector points in the collection based on a query vector, with optional filtering by `user_id` and additional payload filters.
    - **Inputs**:
      - `vector`: list[float] - The query vector for similarity search.
      - `limit`: int = 5 - The maximum number of results to return.
      - `collection`: str | None = None - The collection to search in. Defaults to the instance's `collection_name`.
      - `user_id`: str | None = None - Optional user ID for filtering results.
      - `filters`: dict[str, Any] | None = None - Optional dictionary of additional payload filters. Supports exact matches, list matches (`MatchAny`), and range queries (`Range`).
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries, each containing `id`, `score`, and `payload` of matching points.
    - **Raises**: `DatabaseError` - If an error occurs during the search operation.
  - `get_point`:
    - **Description**: Retrieves a single vector point from the collection by its ID.
    - **Inputs**:
      - `point_id`: str - The ID of the point to retrieve.
      - `collection`: str | None = None - The collection to retrieve from. Defaults to the instance's `collection_name`.
    - **Returns**: `dict[str, Any] | None` - A dictionary containing the point's `id`, `vector`, and `payload`, or None if not found.
    - **Raises**: `DatabaseError` - If an error occurs during retrieval.
  - `delete_points`:
    - **Description**: Deletes specified vector points from the collection by their IDs.
    - **Inputs**:
      - `point_ids`: list[str] - A list of point IDs to delete.
      - `collection`: str | None = None - The collection to delete from. Defaults to the instance's `collection_name`.
    - **Returns**: `bool` - True if points were successfully deleted or if the collection does not exist, False otherwise.
    - **Raises**: `DatabaseError` - If an error occurs during deletion.
  - `get_collection_info`:
    - **Description**: Retrieves detailed information about a Qdrant collection, including existence, vector and point counts, and vector configuration (size and distance).
    - **Inputs**:
      - `collection`: str | None = None - The name of the collection to get info for. Defaults to the instance's `collection_name`.
    - **Returns**: `dict[str, Any]` - A dictionary containing collection information.
    - **Raises**: `DatabaseError` - If an error occurs while fetching collection information.

---

## Section 13: core/pipeline/indexer.md

# `memg_core/core/pipeline/indexer.py`

## Module Description
This module implements the deterministic, single-writer indexing pipeline for MEMG Core. It is responsible for adding memories to both the Qdrant vector store and the Kuzu graph database. The pipeline uses the `yaml_translator` to resolve the anchor text for embeddings and no longer depends on the deprecated `core/indexing.py` module.

## Internal Dependencies
- `..exceptions`: `ProcessingError` for handling errors during memory processing.
- `..interfaces.embedder`: `Embedder` for creating vector embeddings.
- `..interfaces.kuzu`: `KuzuInterface` for interacting with the Kuzu graph database.
- `..interfaces.qdrant`: `QdrantInterface` for interacting with the Qdrant vector database.
- `..models`: `Memory` for the memory data model.
- `..yaml_translator`: `build_anchor_text` for resolving the anchor text for embeddings.

## Functions

### `add_memory_index`
- **Description**: Indexes a `Memory` object into both Qdrant (vector store) and Kuzu (graph store). The anchor text for the embedding is resolved using `index_text_override` if provided, or otherwise by the `build_anchor_text` function from the YAML translator. The function computes the embedding, upserts the memory into Qdrant, and mirrors it as a node in Kuzu.
- **Inputs**:
  - `memory`: Memory - The `Memory` object to be indexed.
  - `qdrant`: QdrantInterface - An instance of the Qdrant interface for vector database operations.
  - `kuzu`: KuzuInterface - An instance of the Kuzu interface for graph database operations.
  - `embedder`: Embedder - An instance of the Embedder for generating vector embeddings.
  - `collection`: str | None = None - Optional name of the Qdrant collection to use.
  - `index_text_override`: str | None = None - Optional string to explicitly use as the index text, bypassing the YAML translator's anchor resolution.
- **Returns**: `str` - The point ID of the indexed memory in Qdrant, which should match `memory.id`.
- **Raises**: `ProcessingError` - If the anchor text is empty after resolution, or if there is a failure during the upsert operation in Qdrant, node addition in Kuzu, or any other unexpected error during the indexing process.

---

## Section 14: core/pipeline/retrieval.md

# `memg_core/core/pipeline/retrieval.py`

## Module Description
This module implements a unified retrieval pipeline with automatic mode selection (`vector`, `graph`, `hybrid`) and neighbor expansion. The pipeline uses the `statement` field as the primary textual anchor for embeddings. It supports filtering by `user_id`, `memo_type`, modification date (`modified_within_days`), and other arbitrary filters. All search results are returned with deterministic ordering, sorted first by score (descending) and then by ID (ascending).

## Internal Dependencies
- `..exceptions`: `DatabaseError` for database-related exceptions.
- `..interfaces.embedder`: `Embedder` for generating query embeddings.
- `..interfaces.kuzu`: `KuzuInterface` for interacting with the Kuzu graph database.
- `..interfaces.qdrant`: `QdrantInterface` for interacting with the Qdrant vector database.
- `..models`: `Memory`, `SearchResult` for data models.

## Functions

### `_now` (private)
- **Description**: Returns the current time with UTC timezone.
- **Inputs**: None
- **Returns**: `datetime` - The current UTC datetime.

### `_iso` (private)
- **Description**: Converts a datetime object to an ISO 8601 string.
- **Inputs**:
  - `dt`: datetime | None - The datetime object to convert. Defaults to now if None.
- **Returns**: `str` - The ISO-formatted string.

### `_cutoff` (private)
- **Description**: Calculates the cutoff datetime for a given number of days in the past.
- **Inputs**:
  - `days`: int | None - The number of days to look back.
- **Returns**: `datetime | None` - The cutoff datetime, or None if days is not provided.

### `_parse_datetime` (private)
- **Description**: Parses a string into a `datetime` object, defaulting to the current time if parsing fails.
- **Inputs**:
  - `date_str`: Any - The input date string or `None`.
- **Returns**: `datetime` - A `datetime` object.

### `_build_graph_query_for_memos` (private)
- **Description**: Constructs a Cypher query and parameters to fetch memories from Kuzu based on `user_id`, `memo_type`, and modification date.
- **Inputs**:
  - `user_id`: str | None - The user ID to filter by.
  - `limit`: int - The maximum number of results.
  - `memo_type`: str | None - The memory type to filter by.
  - `modified_within_days`: int | None - The number of days to look back for modifications.
- **Returns**: `tuple[str, dict[str, Any]]` - A tuple containing the Cypher query string and its parameters.

### `_rows_to_memories` (private)
- **Description**: Converts raw rows from a Kuzu query result into a list of `Memory` objects, handling various field formats and ensuring a consistent structure.
- **Inputs**:
  - `rows`: list[dict[str, Any]] - A list of dictionaries, where each dictionary represents a row from a Kuzu query result.
- **Returns**: `list[Memory]` - A list of `Memory` objects.

### `_qdrant_filters` (private)
- **Description**: Constructs a filter dictionary for a Qdrant search query based on `user_id`, `memo_type`, modification date, and any extra filters provided.
- **Inputs**:
    - `user_id`: str | None - The user ID.
    - `memo_type`: str | None - The memory type.
    - `modified_within_days`: int | None - The number of days to look back.
    - `extra`: dict[str, Any] | None - Additional filters.
- **Returns**: `dict[str, Any]` - The constructed filter dictionary for Qdrant.

### `_rerank_with_vectors` (private)
- **Description**: Reranks a list of candidate `Memory` objects (from graph search) using vector similarity scores from Qdrant.
- **Inputs**:
  - `query`: str - The original search query string.
  - `candidates`: list[Memory] - A list of `Memory` objects to be reranked.
  - `qdrant`: QdrantInterface - An instance of the Qdrant interface.
  - `embedder`: Embedder - An instance of the Embedder for generating embeddings.
- **Returns**: `list[SearchResult]` - A list of `SearchResult` objects, sorted by their new similarity scores.

### `_append_neighbors` (private)
- **Description**: Expands a set of search results by fetching their immediate graph neighbors from Kuzu and merging them into the result list, ensuring no duplicates and prioritizing higher scores.
- **Inputs**:
  - `seeds`: list[SearchResult] - The initial list of `SearchResult` objects.
  - `kuzu`: KuzuInterface - An instance of the Kuzu interface.
  - `neighbor_limit`: int - The maximum number of neighbors to fetch for each seed.
  - `relation_names`: list[str] | None - Optional list of relation types to traverse.
- **Returns**: `list[SearchResult]` - An expanded and merged list of `SearchResult` objects.

### `graph_rag_search`
- **Description**: The main entry point for the unified retrieval pipeline. It automatically determines the search mode (`vector`, `graph`, or `hybrid`) based on the provided arguments. If a `query` is given, it defaults to vector-first search. If only filters like `memo_type` or `modified_within_days` are provided, it performs a graph-first search. In hybrid mode, it merges results from both. The pipeline also includes a graceful fallback to vector-only search if the graph database fails, and always appends graph neighbors to the final results.
- **Inputs**:
  - `query`: str | None - The search query string.
  - `user_id`: str - User ID for filtering all search operations.
  - `limit`: int - The maximum number of final results.
  - `qdrant`: QdrantInterface - An instance of the Qdrant interface.
  - `kuzu`: KuzuInterface - An instance of the Kuzu interface.
  - `embedder`: Embedder - An instance of the Embedder.
  - `filters`: dict[str, Any] | None - Optional additional filters for the search.
  - `relation_names`: list[str] | None - Optional list of relation types to consider during graph traversal.
  - `neighbor_cap`: int = 5 - The maximum number of neighbors to append per relevant search result.
  - `memo_type`: str | None - (Keyword-only) Specific memory type to filter by.
  - `modified_within_days`: int | None - (Keyword-only) Scopes search to memories modified in the last N days.
  - `mode`: str | None - (Keyword-only) Explicitly sets the search mode: 'vector', 'graph', or 'hybrid'.
- **Returns**: `list[SearchResult]` - A sorted list of `SearchResult` objects.

---

## Section 15: plugins/yaml_schema.md

# `memg_core/plugins/yaml_schema.py`

## Module Description
This module is responsible for loading the YAML schema that defines entity and relationship catalogs for the MEMG memory system. **IMPORTANT:** While currently residing in `plugins`, this module's functionality is being integrated directly into the `core` as a required component, meaning the YAML schema will no longer be optional. It provides utilities for resolving the schema path, loading the schema, and extracting relation names and entity anchor fields. [[memory:6216549]] [[memory:6216620]]

## Internal Dependencies
- None

## External Dependencies
- `functools`: `lru_cache` for caching the loaded YAML schema.
- `os`: For interacting with environment variables, specifically to find the `MEMG_YAML_SCHEMA` path and check `MEMG_ENABLE_YAML_SCHEMA`.
- `pathlib`: `Path` for handling file path existence checks.
- `typing`: `Any` for flexible type annotations.
- `yaml`: For parsing YAML files (`yaml.safe_load`).

## Functions

### `_resolve_yaml_path` (private)
- **Description**: Resolves the full path to the YAML schema file by checking the `MEMG_YAML_SCHEMA` environment variable and verifying its existence. This function is an internal helper.
- **Inputs**: None
- **Returns**: `str | None` - The absolute path to the YAML schema file if found and exists, otherwise `None`.

### `load_yaml_schema`
- **Description**: Loads the YAML schema that defines the memory system's entities and relationships. It uses `lru_cache` to ensure the schema is loaded only once. It checks if YAML schema is enabled via `MEMG_ENABLE_YAML_SCHEMA` environment variable and resolves the schema path. If the schema cannot be loaded (e.g., file not found, invalid YAML), it returns `None`.
- **Inputs**: None
- **Returns**: `dict[str, Any] | None` - The loaded YAML schema as a dictionary, or `None` if not enabled or an error occurs during loading.

### `get_relation_names`
- **Description**: Extracts and returns a list of all relationship names (converted to uppercase) defined in the loaded YAML schema. If the schema is not loaded or no relations are defined, it returns `None`.
- **Inputs**: None
- **Returns**: `list[str] | None` - A list of uppercase relation names, or `None`.

### `get_entity_anchor`
- **Description**: Retrieves the `anchor` field name for a specified `entity_type` from the YAML schema. The `anchor` field is the designated field within an entity's payload whose value should be used for generating embeddings.
- **Inputs**:
  - `entity_type`: str - The name of the entity type (e.g., "note", "document"). Case-insensitive.
- **Returns**: `str | None` - The name of the anchor field as a string if found and valid, otherwise `None`.

### `build_index_text_with_yaml`
- **Description**: Constructs the indexable text for a given `memory` object by looking up its `memory_type` in the YAML schema and extracting the value from the defined `anchor` field. It includes a fallback mechanism for document types to use `content` if the `summary` (anchor) is empty.
- **Inputs**:
  - `memory`: Any - The memory object (expected to have `memory_type` and a `payload` or direct attributes like `content`).
- **Returns**: `str | None` - The extracted index text (anchor text) if available and valid, otherwise `None`.

---

## Section 16: showcase/examples/simple_demo.md

# `memg_core/showcase/examples/simple_demo.py`

## Module Description
This module provides a simple, illustrative demonstration of how to use the `memg-core` public API. It showcases the basic functionalities of adding different types of memories (notes, documents, tasks) and performing searches within the memory system.

## Internal Dependencies
- None (It imports directly from `memg_core` package, which exports public API functions).

## External Dependencies
- `os`: For setting environment variables (`QDRANT_STORAGE_PATH`, `KUZU_DB_PATH`, `GOOGLE_API_KEY`).
- `memg_core`: `add_document`, `add_note`, `add_task`, `search` from the public API.

## Functions

### `main`
- **Description**: The main function of the demo script. It sets up required environment variables for storage paths and a placeholder API key, then demonstrates adding a note, a document, and a task to the memory system. Finally, it performs a search query and prints the results.
- **Inputs**: None
- **Returns**: None

---

## Section 17: showcase/retriever.md

# `memg_core/showcase/retriever.py`

## Module Description
This module provides a `MemoryRetriever` class as a convenience wrapper for specialized memory retrieval operations. It offers higher-level search methods that build upon the core API's `search` function, allowing for more specific queries related to technologies, errors, or components. It does not directly interact with storage interfaces but rather through the public API.

## Internal Dependencies
- `..api.public`: `search` for performing core memory searches.
- `..core.models`: `SearchResult` for data models.

## Classes

### `MemoryRetriever`
- **Description**: A convenience wrapper class that simplifies common memory retrieval patterns. It abstracts away the direct interaction with underlying storage interfaces by routing all search operations through the public API layer. It provides specialized methods for various search use cases.
- **Attributes**:
  - None (It does not hold state, all operations are stateless and delegated to the API layer).
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `MemoryRetriever`. It has no direct dependencies or state, as all operations are passed to the public API.
    - **Inputs**: None
    - **Returns**: None
  - `search_memories`:
    - **Description**: A generic search method for memories, allowing for convenience filters such as `days_back` and `score_threshold`, which are converted into the core API's filter format. It then calls the `memg_core.search` function.
    - **Inputs**:
      - `query`: str - The search query text.
      - `user_id`: str - User ID for memory isolation.
      - `filters`: dict[str, Any] | None = None - Optional metadata filters. Supported keys include `entity_types` (List[str]), `days_back` (int), `tags` (List[str]), and `memory_type` (str). `days_back` is converted to a `created_at` timestamp range filter.
      - `limit`: int = 10 - Maximum number of results to return.
      - `score_threshold`: float = 0.0 - Minimum similarity score for results to be included (between 0.0 and 1.0).
    - **Returns**: `list[SearchResult]` - A list of `SearchResult` objects that meet the criteria and threshold.
  - `search_by_technology`:
    - **Description**: Searches for memories specifically related to a given technology. It constructs a technology-focused query and applies entity type filters relevant to technology concepts.
    - **Inputs**:
      - `technology`: str - The name of the technology to search for.
      - `user_id`: str - User ID for filtering.
      - `limit`: int = 10 - Maximum results to return.
    - **Returns**: `list[SearchResult]` - A list of `SearchResult` objects related to the technology.
  - `find_error_solutions`:
    - **Description**: Searches for potential solutions to a given error message. It crafts an error-focused query and applies entity type filters for error, issue, and solution-related entities.
    - **Inputs**:
      - `error_message`: str - The error message to find solutions for.
      - `user_id`: str - User ID for filtering.
      - `limit`: int = 10 - Maximum results to return.
    - **Returns**: `list[SearchResult]` - A list of `SearchResult` objects with potential solutions.
  - `search_by_component`:
    - **Description**: Searches for memories associated with a specific software component. It builds a component-focused query and filters results by relevant entity types like `COMPONENT`, `SERVICE`, and `ARCHITECTURE`.
    - **Inputs**:
      - `component`: str - The name of the component to search for.
      - `user_id`: str - User ID for filtering.
      - `limit`: int = 10 - Maximum results to return.
    - **Returns**: `list[SearchResult]` - A list of `SearchResult` objects related to the component.
  - `get_category_stats`:
    - **Description**: (Placeholder) Returns a dictionary of memory count statistics by category. This is noted as a placeholder because direct database queries for statistics are not supported at this showcase layer, and real statistics would come from a system info API.
    - **Inputs**:
      - `user_id`: str - User ID for filtering.
    - **Returns**: `dict[str, int]` - A dictionary with memory type names as keys and zero counts as values (due to placeholder nature).
  - `list_categories`:
    - **Description**: Lists all available memory categories (types) - placeholder implementation as real categories come from YAML schema.
    - **Inputs**: None
    - **Returns**: `list[str]` - A list of hardcoded memory type strings.
  - `expand_with_graph_neighbors`:
    - **Description**: (Placeholder) This method is included for API compatibility but functionally does nothing, as graph neighbor expansion is already handled automatically by the core search pipeline (`graph_rag_search`). It simply returns the original `results`.
    - **Inputs**:
      - `results`: list[SearchResult] - The initial search results.
      - `user_id`: str - User ID for filtering (ignored).
      - `neighbor_limit`: int = 5 - Maximum neighbors per result (ignored).
    - **Returns**: `list[SearchResult]` - The original list of `SearchResult` objects.

---

## Section 18: system/info.md

# `memg_core/system/info.py`

## Module Description
This module provides utility functions for retrieving core system information about the MEMG memory system. It gathers details related to configuration, storage statistics (Qdrant and Kuzu), and the status of optional plugins like the YAML schema loader. This information is crucial for health checks and operational insights.

## Internal Dependencies
- `..core.config`: `get_config` for retrieving system-wide configuration.
- `..core.interfaces.kuzu`: `KuzuInterface` for checking Kuzu database availability.
- `..core.interfaces.qdrant`: `QdrantInterface` for retrieving Qdrant collection information.

## Functions

### `get_system_info`
- **Description**: Gathers and returns a comprehensive dictionary of system information for MEMG. This includes details from the core configuration, the status and statistics of the Qdrant and Kuzu storage interfaces, and the enablement and loading status of the YAML schema plugin.
- **Inputs**:
  - `qdrant`: QdrantInterface | None = None - An optional instance of `QdrantInterface`. If not provided, a temporary instance will be created to fetch stats.
  - `kuzu`: KuzuInterface | None = None - An optional instance of `KuzuInterface`. If not provided, a temporary instance will be created to test availability.
- **Returns**: `dict[str, Any]` - A dictionary containing various system information:
  - `config`: Core configuration settings.
  - `plugins`: Status of plugins, specifically `yaml_schema` (enabled, path, loaded).
  - `qdrant`: Qdrant collection statistics (collection name, existence, vector/point counts, vector size) or an error message if unavailable.
  - `kuzu`: Kuzu database availability and path, or an error message.
  - `graph`: Graph-specific settings, such as `neighbor_limit`.

---

## Section 19: utils/hrid.md

# `memg_core/utils/hrid.py`

## Module Description
This module provides a utility for generating and parsing Human-Readable IDs (HRIDs) for MEMG Core. The HRID format is `{TYPE_UPPER}_{AAA000}`, where `TYPE_UPPER` is an uppercase alphanumeric type name, `AAA` is a base-26 alphabetical component, and `000` is a numeric suffix. The module uses in-memory counters for generation, which are reset when the application restarts.

## Internal Dependencies
- None

## External Dependencies
- `re`: For regular expression matching of HRIDs.
- `typing`: For type hints (`Tuple`).

## Functions

### `_alpha_to_idx` (private)
- **Description**: Converts a three-letter alphabetical string (e.g., "AAA") into its corresponding base-26 integer index.
- **Inputs**:
  - `alpha`: str - The alphabetical string to convert.
- **Returns**: `int` - The integer index.

### `_idx_to_alpha` (private)
- **Description**: Converts a base-26 integer index back into its three-letter alphabetical string representation.
- **Inputs**:
  - `idx`: int - The integer index.
- **Returns**: `str` - The three-letter alphabetical string.

### `generate_hrid`
- **Description**: Generates the next sequential HRID for a given type name. It uses an in-memory counter that increments the numeric part and rolls over to the alphabetical part when the numeric part exceeds 999.
- **Inputs**:
  - `type_name`: str - The type name for the HRID (e.g., "TASK", "NOTE").
- **Returns**: `str` - The newly generated HRID.
- **Raises**: `ValueError` - If the HRID space is exhausted for the given type.

### `parse_hrid`
- **Description**: Parses a given HRID string into its constituent parts: type, alphabetical component, and numeric component.
- **Inputs**:
  - `hrid`: str - The HRID string to parse.
- **Returns**: `Tuple[str, str, int]` - A tuple containing the type, alphabetical part, and numeric part.
- **Raises**: `ValueError` - If the HRID format is invalid.

### `reset_counters`
- **Description**: Resets all in-memory HRID counters. This is primarily intended for use in testing environments to ensure a clean state between test runs.
- **Inputs**: None
- **Returns**: None

### `_type_key` (private)
- **Description**: Generates a deterministic numeric key for type names to enable cross-type ordering. It encodes up to the first 8 characters of the type name in base-37 (A–Z=1–26, 0–9=27–36).
- **Inputs**:
  - `t`: str - The type name to encode.
- **Returns**: `int` - The numeric key for the type.

### `hrid_to_index`
- **Description**: Converts an HRID into a single integer index for ordering across different types. It uses the type key in the upper bits and the intra-type ordering (alphabetical + numeric) in the lower bits.
- **Inputs**:
  - `hrid`: str - The HRID string to convert.
- **Returns**: `int` - The corresponding integer index that enables cross-type ordering.

---
