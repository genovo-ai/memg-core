# `memg_core/core/models.py`

## Module Description
This module defines the core, type-agnostic data models for the MEMG memory system. These models are designed to be minimal, stable, and extensible, providing foundational structures for various memory components like `Memory`, `MemoryPoint`, `SearchResult`, and `ProcessingResult`.

## Internal Dependencies
- `datetime`: `UTC`, `datetime` for handling temporal fields.
- `typing`: `Any` for flexible type annotations.
- `uuid`: `uuid4` for generating unique identifiers.
- `pydantic`: `BaseModel`, `ConfigDict`, `Field`, `field_validator` for data validation and model definition.

## Classes

### `Memory`
- **Description**: A type-agnostic data model representing a single piece of memory in the system. It encapsulates core identification, a generic payload for entity-specific fields, metadata, temporal information, and version tracking.
- **Attributes**:
  - `id`: `str` - Unique identifier for the memory (defaults to a new UUID).
  - `user_id`: `str` - User ID for isolating memories by user.
  - `memory_type`: `str` - The name of the entity type as defined in the YAML schema (e.g., "note", "document").
  - `payload`: `dict[str, Any]` - A dictionary containing entity-specific fields, as defined in the YAML schema.
  - `tags`: `list[str]` - A flexible list of tags for categorization.
  - `confidence`: `float` - A confidence score for the memory's storage (between 0.0 and 1.0).
  - `vector`: `list[float] | None` - The embedding vector associated with the memory.
  - `is_valid`: `bool` - A flag indicating whether the memory is currently considered valid.
  - `created_at`: `datetime` - The timestamp when the memory was created.
  - `supersedes`: `str | None` - The ID of a previous memory that this one supersedes.
  - `superseded_by`: `str | None` - The ID of a subsequent memory that supersedes this one.
  - `hrid`: `str | None` - Human-readable ID (e.g., TASK_AAA001).
- **Methods**:
  - `memory_type_not_empty` (field_validator):
    - **Description**: A Pydantic field validator that ensures the `memory_type` field is not empty or consists only of whitespace.
    - **Inputs**:
      - `v`: `str` - The value of the `memory_type` field.
    - **Returns**: `str` - The stripped `memory_type` value.
    - **Raises**: `ValueError` - If the `memory_type` is empty.
    - **Schema**:
      - Input: `v` (String)
      - Output: `str` (String)
      - Type Mixing: Defined type

  - `to_qdrant_payload`:
    - **Description**: Converts the `Memory` object into a nested dictionary suitable for storage as a payload in Qdrant. It separates core metadata from entity-specific fields.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Qdrant payload.
    - **Schema**:
      - Input: None
      - Output: `dict[str, Any]` (Dictionary with Any type values)
      - Type Mixing: Mixed type (output `Any`)

  - `to_kuzu_node`:
    - **Description**: Converts the `Memory` object into a dictionary of properties for creating a node in Kuzu. It includes core metadata and flattens specific, queryable fields from the payload.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu node properties.
    - **Schema**:
      - Input: None
      - Output: `dict[str, Any]` (Dictionary with Any type values)
      - Type Mixing: Mixed type (output `Any`)

  - `__getattr__`:
    - **Description**: Dynamic attribute access for YAML-defined payload fields ONLY. This enforces strict YAML schema compliance by raising an `AttributeError` if the field is not in the payload dictionary.
    - **Inputs**:
      - `item`: `str` - The attribute name being accessed.
    - **Returns**: `Any` - The value of the payload field if found.
    - **Raises**: `AttributeError` - If the attribute is not found in the payload.
    - **Schema**:
      - Input: `item` (String)
      - Output: `Any` (Any type)
      - Type Mixing: Mixed type (output `Any`)

  - `to_entity_model`:
    - **Description**: Projects this Memory into a dynamic Pydantic entity model, returning an instance of the auto-generated model class that matches the entity type defined in the YAML schema. Only non-system fields are included.
    - **Inputs**: None
    - **Returns**: `BaseModel` - An instance of the dynamic Pydantic entity model.
    - **Schema**:
      - Input: None
      - Output: `BaseModel` (Pydantic BaseModel)
      - Type Mixing: Defined type

### `MemoryPoint`
- **Description**: A data model that combines a `Memory` object with its embedding vector and an optional Qdrant point ID, designed for representing memories specifically for Qdrant storage.
- **Attributes**:
  - `memory`: `memg_core.core.models.Memory` - The associated `Memory` object.
  - `vector`: `list[float]` - The embedding vector for the memory.
  - `point_id`: `str | None` - The unique ID assigned by Qdrant to this point.
- **Methods**:
  - `vector_not_empty` (field_validator):
    - **Description**: A Pydantic field validator that ensures the `vector` field is not an empty list.
    - **Inputs**:
      - `v`: `list[float]` - The embedding vector.
    - **Returns**: `list[float]` - The validated vector.
    - **Raises**: `ValueError` - If the `vector` is empty.
    - **Schema**:
      - Input: `v` (List of Floats)
      - Output: `list[float]` (List of Floats)
      - Type Mixing: Defined type

### `SearchResult`
- **Description**: A data model representing a single result from a memory search operation, including the found memory, its relevance score, and the search source.
- **Attributes**:
  - `memory`: `memg_core.core.models.Memory` - The `Memory` object found by the search.
  - `score`: `float` - The similarity score of the memory to the query.
  - `distance`: `float | None` - The vector distance, if applicable.
  - `source`: `str` - The source of the search result (e.g., "qdrant", "kuzu", "hybrid").
  - `metadata`: `dict[str, Any]` - Additional metadata related to the search result.
- **Schema**:
  - Input: None (instantiated directly)
  - Output: `SearchResult` (Pydantic Model)
  - Type Mixing: Defined type, with `metadata` allowing mixed types internally due to `Any`

### `ProcessingResult`
- **Description**: A data model encapsulating the outcome of a memory processing pipeline operation, including success status, lists of created memories, and any errors encountered.
- **Attributes**:
  - `success`: `bool` - Indicates whether the processing operation was successful.
  - `memories_created`: `list[memg_core.core.models.Memory]` - A list of `Memory` objects created during processing.
  - `errors`: `list[str]` - A list of error messages encountered during processing.
  - `processing_time_ms`: `float | None` - The time taken for processing in milliseconds.
- **Properties**:
  - `total_created`:
    - **Description**: Calculates the total number of memories created.
    - **Inputs**: None
    - **Returns**: `int` - The sum of all created items.
    - **Schema**:
      - Input: None
      - Output: `int` (Integer)
      - Type Mixing: Defined type
