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
