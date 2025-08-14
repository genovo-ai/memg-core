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
