# `memg_core/core/pipeline/retrieval.py`

## Module Description
This module implements a unified retrieval pipeline with automatic mode selection (`vector`, `graph`, `hybrid`) and neighbor expansion. The pipeline uses the `statement` field as the primary textual anchor for embeddings. It supports filtering by `user_id`, `memo_type`, modification date (`modified_within_days`), and other arbitrary filters. All search results are returned with deterministic ordering, sorted first by score (descending), then by HRID index (ascending), then by ID (ascending). Features field projection capabilities to control payload detail levels.

## Internal Dependencies
- `...utils.hrid`: `hrid_to_index` for deterministic HRID-based sorting.
- `..exceptions`: `DatabaseError` for database-related exceptions.
- `..interfaces.embedder`: `Embedder` for generating query embeddings.
- `..interfaces.kuzu`: `KuzuInterface` for interacting with the Kuzu graph database.
- `..interfaces.qdrant`: `QdrantInterface` for interacting with the Qdrant vector database.
- `..models`: `Memory`, `SearchResult` for data models.

## Functions

### `_project_payload` (private)
- **Description**: Returns a pruned payload based on include_details and optional projection mapping. Controls field visibility for memory payloads.
- **Inputs**:
  - `memory_type`: str - The type of memory for projection lookups.
  - `payload`: dict[str, Any] | None - The original payload to filter.
  - `include_details`: str - Detail level control ("none" for anchors only, "self" for anchors plus projection).
  - `projection`: dict[str, list[str]] | None - Per-type field allow-list mapping.
- **Returns**: `dict[str, Any]` - The filtered payload dictionary.

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

### `_sort_key` (private)
- **Description**: Generates a stable sort key for SearchResult objects, ordering by score (descending), HRID index (ascending), then ID (ascending).
- **Inputs**:
  - `r`: SearchResult - The SearchResult object to generate a sort key for.
- **Returns**: `tuple` - A tuple suitable for sorting with the desired precedence.

### `_build_graph_query_for_memos` (private)
- **Description**: Constructs a Cypher query and parameters to fetch Memory nodes from Kuzu based on `user_id`, `memo_type`, and modification date. Returns m.* fields only; neighbors are fetched separately.
- **Inputs**:
  - `user_id`: str | None - The user ID to filter by.
  - `limit`: int - The maximum number of results.
  - `memo_type`: str | None - The memory type to filter by.
  - `modified_within_days`: int | None - The number of days to look back for modifications.
- **Returns**: `tuple[str, dict[str, Any]]` - A tuple containing the Cypher query string and its parameters.

### `_rows_to_memories` (private)
- **Description**: Converts raw rows from a Kuzu query result into a list of `Memory` objects, handling various field formats and ensuring a consistent structure. Includes HRID field extraction for sorting.
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
- **Description**: Expands a set of search results by fetching their immediate graph neighbors from Kuzu and merging them into the result list, ensuring no duplicates and prioritizing higher scores. Uses default relation whitelist if none provided.
- **Inputs**:
  - `seeds`: list[SearchResult] - The initial list of `SearchResult` objects.
  - `kuzu`: KuzuInterface - An instance of the Kuzu interface.
  - `neighbor_limit`: int - The maximum number of neighbors to fetch for each seed.
  - `relation_names`: list[str] | None - Optional list of relation types to traverse. Defaults to ["RELATED_TO", "HAS_DOCUMENT", "REQUIRES"] if None.
- **Returns**: `list[SearchResult]` - An expanded and merged list of `SearchResult` objects.

### `graph_rag_search`
- **Description**: The main entry point for the unified retrieval pipeline. It automatically determines the search mode (`vector`, `graph`, or `hybrid`) based on the provided arguments. If a `query` is given, it defaults to vector-first search. If only filters like `memo_type` or `modified_within_days` are provided, it performs a graph-first search. In hybrid mode, it merges results from both. The pipeline also includes a graceful fallback to vector-only search if the graph database fails, and always appends graph neighbors to the final results. Supports field projection for controlling payload detail levels.
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
  - `include_details`: str = "none" - (Keyword-only) Controls payload detail level. "none" returns anchors only, "self" includes anchor plus optional projection fields.
  - `projection`: dict[str, list[str]] | None - (Keyword-only) Per-type field allow-list for controlling which fields are returned in payloads.
- **Returns**: `list[SearchResult]` - A sorted list of `SearchResult` objects with deterministic HRID-based ordering.
