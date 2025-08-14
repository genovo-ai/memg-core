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
