# `memg_core/api/public.py`

## Module Description
This module provides a minimal public API that exposes a generic `add_memory` function and a unified `search` function. It uses the YAML translator to validate payloads and resolve an entity's anchor field to a `statement` for embedding. The `search` function supports vector-first, graph-first, or hybrid modes and allows for date-based scoping.

## Internal Dependencies
- `..core.config`: `get_config` for retrieving system configuration.
- `..core.exceptions`: `ValidationError` for input validation.
- `..core.interfaces.embedder`: `Embedder` for generating embeddings.
- `..core.interfaces.kuzu`: `KuzuInterface` for graph database operations.
- `..core.interfaces.qdrant`: `QdrantInterface` for vector database operations.
- `..core.models`: `Memory`, `SearchResult` for data models.
- `..core.pipeline.indexer`: `add_memory_index` for indexing memories.
- `..core.pipeline.retrieval`: `graph_rag_search` for memory retrieval.
- `..core.yaml_translator`: `build_anchor_text`, `get_entity_model` for YAML schema integration.
- `..plugins.yaml_schema`: `get_relation_names` (conditionally imported) for dynamic relation names.

## Functions

### `_index_memory_with_yaml`
- **Description**: A helper function to index a memory with strict YAML-driven anchor text resolution. It initializes the necessary storage interfaces, resolves the anchor text via the YAML translator (REQUIRED - no fallbacks), and then upserts the memory into Qdrant and mirrors it to Kuzu.
- **Inputs**:
  - `memory`: `memg_core.core.models.Memory` - The Memory object to be indexed.
- **Returns**: `str` - The point ID of the indexed memory in Qdrant.
- **Schema**:
  - Input: `Memory` (Pydantic Model)
  - Output: `str` (String)
  - Type Mixing: Defined types

### `add_memory`
- **Description**: Create a memory using strict YAML schema validation and index it. Validates payload against dynamically generated Pydantic model from YAML schema. NO fallbacks, NO backward compatibility.
- **Inputs**:
  - `memory_type`: `str` - The entity type name (e.g., "note", "document", "task") as defined in the YAML schema.
  - `payload`: `dict[str, Any]` - Dictionary containing field values for the entity, as specified by the YAML schema.
  - `user_id`: `str` - User identifier for isolation.
  - `tags`: `list[str] | None` - Optional list of tags to associate with the memory.
- **Returns**: `memg_core.core.models.Memory` - The created Memory object with its `id` populated from the indexing result.
- **Raises**: `memg_core.core.exceptions.ValidationError` - If `memory_type`, `user_id`, or `payload` are empty, or if the payload is invalid for the specified entity type according to the YAML schema.
- **Schema**:
  - Input: `memory_type` (String), `payload` (Dictionary with Any type values), `user_id` (String), `tags` (List of Strings or None)
  - Output: `Memory` (Pydantic Model)
  - Type Mixing: Defined types, with `payload` allowing mixed types internally due to `Any`

### `search`
- **Description**: A unified search function that can query memories using vector, graph, or hybrid approaches. It requires at least one of `query` or `memo_type` to be provided. It initializes storage interfaces and calls the `graph_rag_search` pipeline function with various filtering and mode options.
- **Inputs**:
  - `query`: `str | None` - The search query string.
  - `user_id`: `str` - User ID for filtering search results.
  - `limit`: `int` = 20 - Maximum number of results to return.
  - `filters`: `dict[str, Any] | None` - Optional additional filters for vector search.
  - `memo_type`: `str | None` - (Keyword-only) Specific memory type to filter by.
  - `modified_within_days`: `int | None` - (Keyword-only) Scopes the search to memories modified within the last N days.
  - `mode`: `str | None` - (Keyword-only) The search mode to use. Can be 'vector', 'graph', or 'hybrid'.
  - `include_details`: `str` = "self" - (Keyword-only) Controls payload detail level. "none" returns anchors only, "self" includes anchor plus optional projection fields.
  - `projection`: `dict[str, list[str]] | None` - (Keyword-only) Per-type field allow-list for controlling which fields are returned in payloads.
- **Returns**: `list[memg_core.core.models.SearchResult]` - A list of SearchResult objects, ranked by relevance.
- **Raises**: `memg_core.core.exceptions.ValidationError` - If both `query` and `memo_type` are missing or `user_id` is not provided.
- **Schema**:
  - Input: `query` (String or None), `user_id` (String), `limit` (Integer), `filters` (Dictionary with Any type values or None), `memo_type` (String or None), `modified_within_days` (Integer or None), `mode` (String or None), `include_details` (String), `projection` (Dictionary mapping String to List of Strings, or None)
  - Output: `list[SearchResult]` (List of Pydantic SearchResult Models)
  - Type Mixing: Defined types, with `filters` and `projection` allowing mixed types internally due to `Any`
