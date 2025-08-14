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
