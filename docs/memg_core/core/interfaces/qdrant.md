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
