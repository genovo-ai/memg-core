# `memg_core/core/yaml_translator.py`

## Module Description
This module provides the core functionality for translating YAML entity definitions into the `Memory` data model, making the system type-agnostic. Core & generalized. Accepts any conforming YAML schema via env path today; accepting an injected schema object is planned for a later cycle. It reads entity definitions from a YAML registry and supports flexible schema shapes (entities as a dictionary or a list). Key functionalities include validating payloads against the schema, resolving anchor text for embeddings with robust fallbacks, and creating `Memory` objects. If a YAML schema is not present, it falls back to using common field names like `statement` or `summary` for anchor text.

## Internal Dependencies
- `..exceptions`: `MemorySystemError`, `YamlTranslatorError` for specific translator errors.
- `..models`: `Memory` for the core data model.

## External Dependencies
- `functools`: `lru_cache` for caching the YAML translator instance.
- `os`: For interacting with environment variables.
- `pathlib`: `Path` for handling file paths.
- `typing`: `Any` for flexible type annotations.
- `pydantic`: `BaseModel`, `Field` for data validation and model definition.
- `yaml`: For loading YAML schema files.

## Classes

### `YamlTranslatorError`
- **Description**: A custom exception class specifically for errors that occur within the YAML translator module. It inherits from `MemorySystemError`.

### `EntitySpec`
- **Description**: A Pydantic BaseModel that defines the structure of an entity specification as parsed from the YAML schema.
- **Attributes**:
  - `name`: str - The name of the entity type (e.g., "note", "document").
  - `description`: str | None - A brief description of the entity type.
  - `anchor`: str - The name of the payload field to be used as anchor text. Defaults to "statement".
  - `fields`: dict[str, Any] | None - A flexible dictionary defining the schema and properties of each field.

### `YamlTranslator`
- **Description**: The main class responsible for loading, caching, and translating YAML entity definitions. It provides methods to retrieve entity specifications, determine anchor fields, build anchor text from `Memory` objects, and validate/create `Memory` objects based on the YAML schema. It can handle various YAML structures and provides fallbacks when a schema is missing or incomplete.
- **Attributes**:
  - `yaml_path`: str | None - The file path to the YAML schema.
  - `_schema`: dict[str, Any] | None - A cached dictionary representation of the loaded YAML schema.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `YamlTranslator` instance with an optional YAML schema file path. It prioritizes an explicitly provided path, then the `MEMG_YAML_SCHEMA` environment variable.
    - **Inputs**:
      - `yaml_path`: str | None = None - The path to the YAML schema file.
    - **Returns**: None
  - `schema` (property):
    - **Description**: Property that loads and caches the YAML schema from the `yaml_path`.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - The loaded YAML schema as a dictionary.
    - **Raises**: `YamlTranslatorError` - If `MEMG_YAML_SCHEMA` is not set, the file is not found, or the YAML is invalid/empty.
  - `_load_schema` (private):
    - **Description**: Internal method to perform the actual loading of the YAML schema file from the specified path. It handles file existence, parsing, and potential YAML syntax errors.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - The loaded YAML schema.
    - **Raises**: `YamlTranslatorError` - For file system issues, invalid YAML syntax, or empty schema.
  - `_entities_map` (private):
    - **Description**: Normalizes the 'entities' section of the YAML schema into a consistent dictionary format, whether it's defined as a list or a dictionary.
    - **Inputs**: None
    - **Returns**: `dict[str, dict[str, Any]]` - A dictionary of entity specifications, keyed by their lowercase name.
  - `get_entity_spec`:
    - **Description**: Retrieves the `EntitySpec` for a given entity name by looking it up in the normalized entity map from the YAML schema.
    - **Inputs**:
      - `entity_name`: str - The name of the entity type (e.g., "note", "document", "task").
    - **Returns**: `EntitySpec` - The Pydantic model representing the entity's specification.
    - **Raises**: `YamlTranslatorError` - If the specified entity name is empty or not found in the schema.
  - `get_anchor_field`:
    - **Description**: Returns the name of the anchor field for a given entity type. If the type is not found in the YAML schema, it falls back to "statement".
    - **Inputs**:
      - `entity_name`: str - The name of the entity type.
    - **Returns**: `str` - The name of the anchor field.
  - `build_anchor_text`:
    - **Description**: Constructs the anchor text from a `Memory` object. It first attempts to use the anchor field defined in the YAML schema, but includes a robust fallback mechanism that checks a list of common fields (`statement`, `summary`, `content`, etc.) to find the first non-empty string.
    - **Inputs**:
      - `memory`: Memory - The `Memory` object from which to build the anchor text.
    - **Returns**: `str` - The extracted and stripped anchor text.
    - **Raises**: `YamlTranslatorError` - If no valid anchor text can be resolved from any of the candidate fields.
  - `_fields_contract` (private):
    - **Description**: Determines the required and optional fields for an entity based on its specification in the YAML schema. It supports both a flat dictionary of fields and a structured `{ "required": [...], "optional": [...] }` format.
    - **Inputs**:
        - `spec`: dict[str, Any] - The raw entity specification dictionary from the YAML schema.
    - **Returns**: `tuple[list[str], list[str]]` - A tuple containing two lists: required field names and optional field names.
  - `validate_memory_against_yaml`:
    - **Description**: Validates a memory payload against the fields defined in the YAML schema for a specific `memory_type`. If the entity type is not found in the schema, the payload is returned as-is. Otherwise, it checks for the presence of required fields and strips any system-reserved keys from the payload.
    - **Inputs**:
      - `memory_type`: str - The name of the memory type (entity name).
      - `payload`: dict[str, Any] - The raw payload dictionary to validate.
    - **Returns**: `dict[str, Any]` - The validated payload, with system-reserved keys removed.
    - **Raises**: `YamlTranslatorError` - If a required field is missing from the payload.
  - `create_memory_from_yaml`:
    - **Description**: Creates a `Memory` object from a given `memory_type`, `payload`, and `user_id` after validating the payload against the YAML schema.
    - **Inputs**:
      - `memory_type`: str - The name of the entity type.
      - `payload`: dict[str, Any] - The dictionary of field values for the entity.
      - `user_id`: str - The user ID for the memory.
    - **Returns**: `Memory` - The newly created and populated `Memory` object.

## Functions

### `get_yaml_translator`
- **Description**: A globally accessible, cached function that returns a singleton instance of `YamlTranslator`. This ensures that the YAML schema is loaded and parsed only once.
- **Inputs**: None
- **Returns**: `YamlTranslator` - The cached instance of the translator.

### `build_anchor_text`
- **Description**: A convenience function that delegates to the `YamlTranslator` instance's `build_anchor_text` method. It is used to get the primary text for vector embedding from a `Memory` object based on its YAML definition.
- **Inputs**:
  - `memory`: Memory - The `Memory` object.
- **Returns**: `str` - The anchor text.

### `create_memory_from_yaml`
- **Description**: A convenience function that delegates to the `YamlTranslator` instance's `create_memory_from_yaml` method. It facilitates the creation of `Memory` objects, validating their payloads against the YAML schema.
- **Inputs**:
  - `memory_type`: str - The name of the entity type.
  - `payload`: dict[str, Any] - The raw payload dictionary.
  - `user_id`: str - The user ID for the memory.
- **Returns**: `Memory` - The created `Memory` object.
