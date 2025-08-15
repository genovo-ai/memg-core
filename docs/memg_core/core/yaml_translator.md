# `memg_core/core/yaml_translator.py`

## Module Description
This module provides the core functionality for translating YAML entity definitions into the `Memory` data model, making the system type-agnostic. Core & generalized. It reads entity definitions from a YAML registry and supports flexible schema shapes (entities as a dictionary or a list). Key functionalities include validating payloads against the schema, resolving anchor text for embeddings with strict enforcement, and creating `Memory` objects. This module is now a required component; there are no fallbacks if a valid YAML schema is not provided or if anchor fields are missing.

## Internal Dependencies
- `..exceptions`: `MemorySystemError`, `YamlTranslatorError` for specific translator errors.
- `..models`: `Memory` for the core data model.

## External Dependencies
- `contextlib`: `contextlib.suppress` for error handling.
- `functools`: `lru_cache` for caching the YAML translator instance.
- `os`: For interacting with environment variables.
- `pathlib`: `Path` for handling file paths.
- `typing`: `Any`, `Literal`, `Union` for flexible type annotations.
- `pydantic`: `BaseModel`, `Field`, `create_model` for data validation and model definition.
- `yaml`: For loading YAML schema files.

## Classes

### `YamlTranslatorError`
- **Description**: A custom exception class specifically for errors that occur within the YAML translator module. It inherits from `MemorySystemError`.

### `EntitySpec`
- **Description**: A Pydantic BaseModel that defines the structure of an entity specification as parsed from the YAML schema.
- **Attributes**:
  - `name`: `str` - The name of the entity type (e.g., "note", "document").
  - `description`: `str | None` - A brief description of the entity type.
  - `anchor`: `str` - The name of the payload field to be used as anchor text. MUST be explicitly defined in YAML.
  - `fields`: `dict[str, Any] | None` - A flexible dictionary defining the schema and properties of each field.
- **Schema**:
  - Input: Initialized directly with keyword arguments.
  - Output: `EntitySpec` (Pydantic Model)
  - Type Mixing: Defined types, with `fields` allowing mixed types internally due to `Any`

### `YamlTranslator`
- **Description**: The main class responsible for loading, caching, and translating YAML entity definitions. It provides methods to retrieve entity specifications, determine anchor fields, build anchor text from `Memory` objects, and validate/create `Memory` objects based on the YAML schema. It enforces strict YAML schema compliance without fallbacks.
- **Attributes**:
  - `yaml_path`: `str | None` - The file path to the YAML schema.
  - `_schema`: `dict[str, Any] | None` - A cached dictionary representation of the loaded YAML schema.
  - `_model_cache`: `dict[str, Any]` - An instance-level cache for dynamically created Pydantic models.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `YamlTranslator` instance with an optional YAML schema file path. It prioritizes an explicitly provided path, then the `MEMG_YAML_SCHEMA` environment variable.
    - **Inputs**:
      - `yaml_path`: `str | None` = None - The path to the YAML schema file.
    - **Returns**: None
    - **Schema**:
      - Input: `yaml_path` (String or None)
      - Output: None
      - Type Mixing: Defined type

  - `schema` (property):
    - **Description**: Property that loads and caches the YAML schema from the `yaml_path`. It defaults to `config/core.minimal.yaml` if `MEMG_YAML_SCHEMA` is not set.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - The loaded YAML schema as a dictionary.
    - **Raises**: `memg_core.core.yaml_translator.YamlTranslatorError` - If `MEMG_YAML_SCHEMA` is not set and `core.minimal.yaml` is not found, the file is not found, or the YAML is invalid/empty.
    - **Schema**:
      - Input: None
      - Output: `dict[str, Any]` (Dictionary with Any type values)
      - Type Mixing: Mixed type (output `Any`)

  - `_load_schema` (private):
    - **Description**: Internal method to perform the actual loading of the YAML schema file from the specified path. It handles file existence, parsing, and potential YAML syntax errors.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - The loaded YAML schema.
    - **Raises**: `memg_core.core.yaml_translator.YamlTranslatorError` - For file system issues, invalid YAML syntax, or empty schema.
    - **Schema**:
      - Input: None
      - Output: `dict[str, Any]` (Dictionary with Any type values)
      - Type Mixing: Mixed type (output `Any`)

  - `_entities_map` (private):
    - **Description**: Normalizes the 'entities' section of the YAML schema into a consistent dictionary format, whether it's defined as a list or a dictionary.
    - **Inputs**: None
    - **Returns**: `dict[str, dict[str, Any]]` - A dictionary of entity specifications, keyed by their lowercase name.
    - **Schema**:
      - Input: None
      - Output: `dict[str, dict[str, Any]]` (Nested Dictionary with Any type values)
      - Type Mixing: Mixed type (output `Any`)

  - `get_entity_spec`:
    - **Description**: Retrieves the `EntitySpec` for a given entity name by looking it up in the normalized entity map from the YAML schema.
    - **Inputs**:
      - `entity_name`: `str` - The name of the entity type (e.g., "note", "document", "task").
    - **Returns**: `memg_core.core.yaml_translator.EntitySpec` - The Pydantic model representing the entity's specification.
    - **Raises**: `memg_core.core.yaml_translator.YamlTranslatorError` - If the specified entity name is empty or not found in the schema, or if no anchor field is defined.
    - **Schema**:
      - Input: `entity_name` (String)
      - Output: `EntitySpec` (Pydantic Model)
      - Type Mixing: Defined type

  - `get_anchor_field`:
    - **Description**: Returns the name of the anchor field for a given entity type, as defined in the YAML schema. This method strictly requires an anchor field to be defined.
    - **Inputs**:
      - `entity_name`: `str` - The name of the entity type.
    - **Returns**: `str` - The name of the anchor field.
    - **Raises**: `memg_core.core.yaml_translator.YamlTranslatorError` - If the entity type or its anchor field is not found.
    - **Schema**:
      - Input: `entity_name` (String)
      - Output: `str` (String)
      - Type Mixing: Defined type

  - `build_anchor_text`:
    - **Description**: Constructs the anchor text from a `Memory` object based *strictly* on the YAML-defined anchor field. No fallbacks are used. If the anchor field is missing, empty, or not a string, a `YamlTranslatorError` is raised.
    - **Inputs**:
      - `memory`: `Any` - The `Memory` object from which to build the anchor text.
    - **Returns**: `str` - The extracted and stripped anchor text.
    - **Raises**: `memg_core.core.yaml_translator.YamlTranslatorError` - If no valid anchor text can be resolved from the specified anchor field.
    - **Schema**:
      - Input: `memory` (Any type)
      - Output: `str` (String)
      - Type Mixing: Mixed type (input `Any`)

  - `_fields_contract` (private):
    - **Description**: Determines the required and optional fields for an entity based on its specification in the YAML schema. It supports both a flat dictionary of fields and a structured `{ "required": [...], "optional": [...] }` format.
    - **Inputs**:
        - `spec`: `dict[str, Any]` - The raw entity specification dictionary from the YAML schema.
    - **Returns**: `tuple[list[str], list[str]]` - A tuple containing two lists: required field names and optional field names.
    - **Schema**:
      - Input: `spec` (Dictionary with Any type values)
      - Output: `tuple[list[str], list[str]]` (Tuple of Lists of Strings)
      - Type Mixing: Mixed type (input `Any`)

  - `validate_memory_against_yaml`:
    - **Description**: Validates a memory payload against the fields defined in the YAML schema for a specific `memory_type`. If the entity type is not found in the schema, the payload is returned as-is. Otherwise, it checks for the presence of required fields and strips any system-reserved keys from the payload.
    - **Inputs**:
      - `memory_type`: `str` - The name of the memory type (entity name).
      - `payload`: `dict[str, Any]` - The raw payload dictionary to validate.
    - **Returns**: `dict[str, Any]` - The validated payload, with system-reserved keys removed.
    - **Raises**: `memg_core.core.yaml_translator.YamlTranslatorError` - If `memory_type` or `payload` are invalid, or if a required field is missing from the payload.
    - **Schema**:
      - Input: `memory_type` (String), `payload` (Dictionary with Any type values)
      - Output: `dict[str, Any]` (Dictionary with Any type values)
      - Type Mixing: Mixed type (input `Any`, output `Any`)

  - `create_memory_from_yaml`:
    - **Description**: Creates a `Memory` object from a given `memory_type`, `payload`, and `user_id` after validating the payload against the YAML schema.
    - **Inputs**:
      - `memory_type`: `str` - The name of the entity type.
      - `payload`: `dict[str, Any]` - The dictionary of field values for the entity.
      - `user_id`: `str` - The user ID for the memory.
    - **Returns**: `memg_core.core.models.Memory` - The newly created and populated `Memory` object.
    - **Schema**:
      - Input: `memory_type` (String), `payload` (Dictionary with Any type values), `user_id` (String)
      - Output: `Memory` (Pydantic Model)
      - Type Mixing: Mixed type (input `Any`)

  - `_python_type_for_yaml` (private):
    - **Description**: Maps YAML 'type' string to a Python type annotation used by Pydantic, supporting basic types and `Literal` for enums.
    - **Inputs**:
      - `yaml_type`: `str` - The YAML type string (e.g., "string", "float", "enum").
      - `field_def`: `dict[str, Any]` - The dictionary defining the field properties, especially `choices` for enums.
    - **Returns**: `type` - The corresponding Python type annotation.
    - **Schema**:
      - Input: `yaml_type` (String), `field_def` (Dictionary with Any type values)
      - Output: `type` (Python Type Object)
      - Type Mixing: Mixed type (input `Any`)

  - `get_entity_model`:
    - **Description**: Returns (and caches) a dynamic Pydantic model for the given entity type, generated from the YAML schema's field definitions. System-reserved fields are excluded.
    - **Inputs**:
      - `entity_name`: `str` - The name of the entity type.
    - **Returns**: `pydantic.BaseModel` - A dynamically created Pydantic model class.
    - **Schema**:
      - Input: `entity_name` (String)
      - Output: `BaseModel` (Pydantic BaseModel)
      - Type Mixing: Defined type

## Functions

### `get_yaml_translator`
- **Description**: A globally accessible, cached function that returns a singleton instance of `YamlTranslator`. This ensures that the YAML schema is loaded and parsed only once.
- **Inputs**: None
- **Returns**: `memg_core.core.yaml_translator.YamlTranslator` - The cached instance of the translator.
- **Schema**:
  - Input: None
  - Output: `YamlTranslator` (YamlTranslator Object)
  - Type Mixing: Defined type

### `build_anchor_text`
- **Description**: A convenience function that delegates to the `YamlTranslator` instance's `build_anchor_text` method. It is used to get the primary text for vector embedding from a `Memory` object based on its YAML definition.
- **Inputs**:
  - `memory`: `Any` - The `Memory` object.
- **Returns**: `str` - The anchor text.
- **Schema**:
  - Input: `memory` (Any type)
  - Output: `str` (String)
  - Type Mixing: Mixed type (input `Any`)

### `create_memory_from_yaml`
- **Description**: A convenience function that delegates to the `YamlTranslator` instance's `create_memory_from_yaml` method. It facilitates the creation of `Memory` objects, validating their payloads against the YAML schema.
- **Inputs**:
  - `memory_type`: `str` - The name of the entity type.
  - `payload`: `dict[str, Any]` - The raw payload dictionary.
  - `user_id`: `str` - The user ID for the memory.
- **Returns**: `memg_core.core.models.Memory` - The created `Memory` object.
- **Schema**:
  - Input: `memory_type` (String), `payload` (Dictionary with Any type values), `user_id` (String)
  - Output: `Memory` (Pydantic Model)
  - Type Mixing: Mixed type (input `Any`)

### `get_entity_model`
- **Description**: Module-level helper that uses the cached global translator to return a dynamic Pydantic model for the given entity type.
- **Inputs**:
  - `entity_name`: `str` - The name of the entity type.
- **Returns**: `pydantic.BaseModel` - A dynamically created Pydantic model class.
- **Schema**:
  - Input: `entity_name` (String)
  - Output: `BaseModel` (Pydantic BaseModel)
  - Type Mixing: Defined type
