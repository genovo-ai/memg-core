# `memg_core/core/interfaces/kuzu.py`

## Module Description
This module provides a simple wrapper interface for interacting with the Kuzu graph database. It encapsulates basic CRUD (Create, Read, Update, Delete) operations for nodes and relationships, as well as general Cypher query execution and neighbor fetching. It focuses purely on I/O operations with the Kuzu database.

## Internal Dependencies
- `..exceptions`: `DatabaseError` for handling database-related exceptions.

## External Dependencies
- `kuzu`: The Kuzu database client library.
- `os`: For interacting with environment variables.
- `typing`: `Any` for flexible type annotations.

## Classes

### `KuzuInterface`
- **Description**: A class that provides a simplified, high-level interface for performing operations on a Kuzu graph database. It manages the database connection and offers methods to add nodes, add relationships, execute Cypher queries, and retrieve node neighbors.
- **Attributes**:
  - `db`: `kuzu.Database` - The Kuzu database instance.
  - `conn`: `kuzu.Connection` - The connection object to the Kuzu database.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the Kuzu interface by establishing a connection to the database at the specified `db_path`. It resolves the path from environment variables if not provided directly and creates necessary directories.
    - **Inputs**:
      - `db_path`: `str | None` - The file path to the Kuzu database. If None, it defaults to the `KUZU_DB_PATH` environment variable.
    - **Returns**: None
    - **Raises**: `memg_core.core.exceptions.DatabaseError` - If `KUZU_DB_PATH` is not set or if there's a failure in initializing the Kuzu database.
    - **Schema**:
      - Input: `db_path` (String or None)
      - Output: None
      - Type Mixing: Defined type

  - `add_node`:
    - **Description**: Adds a new node to the graph with dynamic schema creation.
    - **Inputs**:
      - `table`: `str` - The name of the node table (e.g., "Memory").
      - `properties`: `dict[str, Any]` - A dictionary of properties for the new node.
    - **Returns**: `None`
    - **Raises**: `memg_core.core.exceptions.DatabaseError` - If the node cannot be added to the specified table.
    - **Schema**:
      - Input: `table` (String), `properties` (Dictionary with Any type values)
      - Output: None
      - Type Mixing: Mixed type (input `properties`)

  - `_ensure_table_schema` (private):
    - **Description**: Ensures table exists with proper schema based on properties.
    - **Inputs**:
      - `table`: `str` - The name of the table.
      - `properties`: `dict[str, Any]` - Properties to infer schema from.
    - **Returns**: `None`
    - **Raises**: `memg_core.core.exceptions.DatabaseError` - If schema creation/validation fails.
    - **Schema**:
      - Input: `table` (String), `properties` (Dictionary with Any type values)
      - Output: None
      - Type Mixing: Mixed type (input `properties`)

  - `add_relationship`:
    - **Description**: Adds relationship between nodes, sanitizing relationship type and handling dynamic table creation/schema updates.
    - **Inputs**:
      - `from_table`: `str` - The label of the source node's table.
      - `to_table`: `str` - The label of the target node's table.
      - `rel_type`: `str` - The type of the relationship (e.g., "MENTIONS").
      - `from_id`: `str` - The ID of the source node.
      - `to_id`: `str` - The ID of the target node.
      - `props`: `dict[str, Any] | None` - Optional dictionary of properties for the relationship.
    - **Returns**: `None`
    - **Raises**: `memg_core.core.exceptions.DatabaseError` - If the relationship cannot be added.
    - **Schema**:
      - Input: `from_table` (String), `to_table` (String), `rel_type` (String), `from_id` (String), `to_id` (String), `props` (Dictionary with Any type values or None)
      - Output: None
      - Type Mixing: Mixed type (input `props`)

  - `_extract_query_results` (private):
    - **Description**: Extracts and formats results from a Kuzu `QueryResult` object into a list of dictionaries.
    - **Inputs**:
      - `query_result`: `Any` - The raw query result object returned by Kuzu.
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries, where each dictionary represents a row in the query result.
    - **Schema**:
      - Input: `query_result` (Any type)
      - Output: `list[dict[str, Any]]` (List of Dictionaries with Any type values)
      - Type Mixing: Mixed type (input `query_result`, output `Any`)

  - `query`:
    - **Description**: Executes a Cypher query against the Kuzu database and returns the results.
    - **Inputs**:
      - `cypher`: `str` - The Cypher query string to execute.
      - `params`: `dict[str, Any] | None` - Optional dictionary of parameters to pass to the query.
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries representing the query results.
    - **Raises**: `memg_core.core.exceptions.DatabaseError` - If the query execution fails.
    - **Schema**:
      - Input: `cypher` (String), `params` (Dictionary with Any type values or None)
      - Output: `list[dict[str, Any]]` (List of Dictionaries with Any type values)
      - Type Mixing: Mixed type (input `params`, output `Any`)

  - `neighbors`:
    - **Description**: Fetches the neighbors of a node, optionally filtered by relationship types, direction, and neighbor label.
    - **Inputs**:
      - `node_label`: `str` - The label of the starting node (e.g., "Memory").
      - `node_id`: `str` - The ID of the starting node.
      - `rel_types`: `list[str] | None` - Optional list of relationship types to traverse.
      - `direction`: `str` = "any" - The direction of relationships to follow ("in", "out", or "any").
      - `limit`: `int` = 10 - The maximum number of neighbors to return.
      - `neighbor_label`: `str | None` - Optional label for the neighbor nodes.
    - **Returns**: `list[dict[str, Any]]` - A list of dictionaries, each representing a neighbor node and its relationship type.
    - **Raises**: `memg_core.core.exceptions.DatabaseError` - If fetching neighbors fails.
    - **Schema**:
      - Input: `node_label` (String), `node_id` (String), `rel_types` (List of Strings or None), `direction` (String), `limit` (Integer), `neighbor_label` (String or None)
      - Output: `list[dict[str, Any]]` (List of Dictionaries with Any type values)
      - Type Mixing: Mixed type (output `Any`)

  - `_get_kuzu_type` (private):
    - **Description**: Maps Python data types to their corresponding Kuzu database types dynamically.
    - **Inputs**:
      - `key`: `str` - The name of the property.
      - `value`: `Any` - The Python value of the property.
    - **Returns**: `str` - The Kuzu data type string (e.g., "STRING", "DOUBLE", "BOOLEAN").
    - **Schema**:
      - Input: `key` (String), `value` (Any type)
      - Output: `str` (String)
      - Type Mixing: Mixed type (input `value`)
