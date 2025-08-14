# `memg_core/api/public.py`

## Module Description
This module provides a minimal public API that exposes a generic `add_memory` function and a unified `search` function. The public API is a thin façade; all logic lives in core. It uses the YAML translator to validate payloads and resolve an entity's anchor field to a `statement` for embedding. The `add_note`, `add_document`, and `add_task` functions are thin shims that build normalized payloads with `statement` as the anchor and optional `details`. The `search` function supports vector-first, graph-first, or hybrid modes via the `mode` parameter and accepts date scoping via `modified_within_days`.

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
- **Description**: A unified search function that can query memories using vector, graph, or hybrid approaches. It requires at least one of `query` or `memo_type` to be provided. It initializes storage interfaces and calls the `graph_rag_search` pipeline function with various filtering and mode options. Supports new projection and detail control features.
- **Inputs**:
  - `query`: str | None - The search query string.
  - `user_id`: str - User ID for filtering search results.
  - `limit`: int = 20 - Maximum number of results to return.
  - `filters`: dict[str, Any] | None - Optional additional filters for vector search.
  - `memo_type`: str | None - (Keyword-only) Specific memory type to filter by.
  - `modified_within_days`: int | None - (Keyword-only) Scopes the search to memories modified within the last N days.
  - `mode`: str | None - (Keyword-only) The search mode to use. Can be 'vector', 'graph', or 'hybrid'.
  - `include_details`: str = "none" - (Keyword-only) Controls payload detail level. "none" returns anchors only, "self" includes anchor plus optional projection fields.
  - `projection`: dict[str, list[str]] | None - (Keyword-only) Per-type field allow-list for controlling which fields are returned in payloads.
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
