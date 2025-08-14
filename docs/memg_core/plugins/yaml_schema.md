# `memg_core/plugins/yaml_schema.py`

## Module Description
This module is responsible for loading the YAML schema that defines entity and relationship catalogs for the MEMG memory system. **IMPORTANT:** While currently residing in `plugins`, this module's functionality is being integrated directly into the `core` as a required component, meaning the YAML schema will no longer be optional. It provides utilities for resolving the schema path, loading the schema, and extracting relation names and entity anchor fields. [[memory:6216549]] [[memory:6216620]]

## Internal Dependencies
- None

## External Dependencies
- `functools`: `lru_cache` for caching the loaded YAML schema.
- `os`: For interacting with environment variables, specifically to find the `MEMG_YAML_SCHEMA` path and check `MEMG_ENABLE_YAML_SCHEMA`.
- `pathlib`: `Path` for handling file path existence checks.
- `typing`: `Any` for flexible type annotations.
- `yaml`: For parsing YAML files (`yaml.safe_load`).

## Functions

### `_resolve_yaml_path` (private)
- **Description**: Resolves the full path to the YAML schema file by checking the `MEMG_YAML_SCHEMA` environment variable and verifying its existence. This function is an internal helper.
- **Inputs**: None
- **Returns**: `str | None` - The absolute path to the YAML schema file if found and exists, otherwise `None`.

### `load_yaml_schema`
- **Description**: Loads the YAML schema that defines the memory system's entities and relationships. It uses `lru_cache` to ensure the schema is loaded only once. It checks if YAML schema is enabled via `MEMG_ENABLE_YAML_SCHEMA` environment variable and resolves the schema path. If the schema cannot be loaded (e.g., file not found, invalid YAML), it returns `None`.
- **Inputs**: None
- **Returns**: `dict[str, Any] | None` - The loaded YAML schema as a dictionary, or `None` if not enabled or an error occurs during loading.

### `get_relation_names`
- **Description**: Extracts and returns a list of all relationship names (converted to uppercase) defined in the loaded YAML schema. If the schema is not loaded or no relations are defined, it returns `None`.
- **Inputs**: None
- **Returns**: `list[str] | None` - A list of uppercase relation names, or `None`.

### `get_entity_anchor`
- **Description**: Retrieves the `anchor` field name for a specified `entity_type` from the YAML schema. The `anchor` field is the designated field within an entity's payload whose value should be used for generating embeddings.
- **Inputs**:
  - `entity_type`: str - The name of the entity type (e.g., "note", "document"). Case-insensitive.
- **Returns**: `str | None` - The name of the anchor field as a string if found and valid, otherwise `None`.

### `build_index_text_with_yaml`
- **Description**: Constructs the indexable text for a given `memory` object by looking up its `memory_type` in the YAML schema and extracting the value from the defined `anchor` field. It includes a fallback mechanism for document types to use `content` if the `summary` (anchor) is empty.
- **Inputs**:
  - `memory`: Any - The memory object (expected to have `memory_type` and a `payload` or direct attributes like `content`).
- **Returns**: `str | None` - The extracted index text (anchor text) if available and valid, otherwise `None`.
