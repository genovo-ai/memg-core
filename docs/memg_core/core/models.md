# `memg_core/core/models.py`

## Module Description
This module defines the core, type-agnostic data models for the MEMG memory system. These models are designed to be minimal, stable, and extensible, providing foundational structures for various memory components like `Memory`, `Entity`, `Relationship`, `MemoryPoint`, `SearchResult`, and `ProcessingResult`.

## Internal Dependencies
- None

## External Dependencies
- `datetime`: `UTC`, `datetime` for handling temporal fields.
- `typing`: `Any` for flexible type annotations.
- `uuid`: `uuid4` for generating unique identifiers.
- `pydantic`: `BaseModel`, `ConfigDict`, `Field`, `field_validator` for data validation and model definition.

## Classes

### `Memory`
- **Description**: A type-agnostic data model representing a single piece of memory in the system. It encapsulates core identification, a generic payload for entity-specific fields, metadata, temporal information, and version tracking.
- **Attributes**:
  - `id`: str - Unique identifier for the memory (defaults to a new UUID).
  - `user_id`: str - User ID for isolating memories by user.
  - `memory_type`: str - The name of the entity type as defined in the YAML schema (e.g., "note", "document").
  - `payload`: dict[str, Any] - A dictionary containing entity-specific fields, as defined in the YAML schema.
  - `tags`: list[str] - A flexible list of tags for categorization.
  - `confidence`: float - A confidence score for the memory's storage (between 0.0 and 1.0).
  - `vector`: list[float] | None - The embedding vector associated with the memory.
  - `is_valid`: bool - A flag indicating whether the memory is currently considered valid.
  - `created_at`: datetime - The timestamp when the memory was created.
  - `supersedes`: str | None - The ID of a previous memory that this one supersedes.
  - `superseded_by`: str | None - The ID of a subsequent memory that supersedes this one.
- **Methods**:
  - `to_qdrant_payload`:
    - **Description**: Converts the `Memory` object into a nested dictionary suitable for storage as a payload in Qdrant. It separates core metadata from entity-specific fields.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Qdrant payload.
  - `to_kuzu_node`:
    - **Description**: Converts the `Memory` object into a dictionary of properties for creating a node in Kuzu. It includes core metadata and flattens specific, queryable fields from the payload, such as `statement`, `title`, and task-related attributes.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu node properties.
  - `memory_type_not_empty` (field_validator):\
    - **Description**: A Pydantic field validator that ensures the `memory_type` field is not empty or consists only of whitespace.
    - **Inputs**:\
      - `v`: str - The value of the `memory_type` field.
    - **Returns**: `str` - The stripped `memory_type` value.
    - **Raises**: `ValueError` - If the `memory_type` is empty.

### `Entity`
- **Description**: A data model representing an extracted entity from memories. These entities are typically nodes in the Kuzu graph database and are used for structural organization and retrieval.
- **Attributes**:
  - `id`: str | None - Unique identifier for the entity (defaults to a new UUID).
  - `user_id`: str - User ID for isolating entities by user.
  - `name`: str - The name of the entity.
  - `type`: str - The type of the entity (e.g., "PERSON", "TECHNOLOGY").
  - `description`: str - A textual description of the entity.
  - `confidence`: float - A confidence score for the entity extraction.
  - `created_at`: datetime - The timestamp when the entity was created.
  - `is_valid`: bool - A flag indicating whether the entity is currently valid.
  - `source_memory_id`: str | None - The ID of the memory from which this entity was extracted.
- **Methods**:
  - `to_kuzu_node`:\
    - **Description**: Converts the `Entity` object into a dictionary of properties suitable for creating a node in the Kuzu graph database.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu node properties.

### `Relationship`
- **Description**: A data model representing a relationship between two entities or memories in the graph database.
- **Attributes**:
  - `id`: str | None - Unique identifier for the relationship (defaults to a new UUID).
  - `user_id`: str - User ID for isolating relationships by user.
  - `source_id`: str - The ID of the source node of the relationship.
  - `target_id`: str - The ID of the target node of the relationship.
  - `relationship_type`: str - The type of the relationship (e.g., "MENTIONS", "HAS_PROPERTY").
  - `confidence`: float - A confidence score for the relationship.
  - `created_at`: datetime - The timestamp when the relationship was created.
  - `is_valid`: bool - A flag indicating whether the relationship is currently valid.
- **Methods**:
  - `to_kuzu_props`:\
    - **Description**: Converts the `Relationship` object into a dictionary of properties suitable for creating a relationship in the Kuzu graph database.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - A dictionary representation for Kuzu relationship properties.

### `MemoryPoint`
- **Description**: A data model that combines a `Memory` object with its embedding vector and an optional Qdrant point ID, designed for representing memories specifically for Qdrant storage.
- **Attributes**:
  - `memory`: Memory - The associated `Memory` object.
  - `vector`: list[float] - The embedding vector for the memory.
  - `point_id`: str | None - The unique ID assigned by Qdrant to this point.
- **Methods**:
  - `vector_not_empty` (field_validator):\
    - **Description**: A Pydantic field validator that ensures the `vector` field is not an empty list.
    - **Inputs**:\
      - `v`: list[float] - The embedding vector.
    - **Returns**: `list[float]` - The validated vector.
    - **Raises**: `ValueError` - If the `vector` is empty.

### `SearchResult`
- **Description**: A data model representing a single result from a memory search operation, including the found memory, its relevance score, and the search source.
- **Attributes**:
  - `memory`: Memory - The `Memory` object found by the search.
  - `score`: float - The similarity score of the memory to the query.
  - `distance`: float | None - The vector distance, if applicable.
  - `source`: str - The source of the search result (e.g., "qdrant", "kuzu", "hybrid").
  - `metadata`: dict[str, Any] - Additional metadata related to the search result.

### `ProcessingResult`
- **Description**: A data model encapsulating the outcome of a memory processing pipeline operation, including success status, lists of created memories, entities, and relationships, and any errors encountered.
- **Attributes**:
  - `success`: bool - Indicates whether the processing operation was successful.
  - `memories_created`: list[Memory] - A list of `Memory` objects created during processing.
  - `entities_created`: list[Entity] - A list of `Entity` objects created during processing.
  - `relationships_created`: list[Relationship] - A list of `Relationship` objects created during processing.
  - `errors`: list[str] - A list of error messages encountered during processing.
  - `processing_time_ms`: float | None - The time taken for processing in milliseconds.
- **Properties**:
  - `total_created`:\
    - **Description**: Calculates the total number of memories, entities, and relationships created.
    - **Inputs**: None
    - **Returns**: `int` - The sum of all created items.
