# `memg_core/core/config.py`

## Module Description
This module defines the core configuration settings for the MEMG memory system. It includes data classes for memory-specific settings (`MemGConfig`) and system-wide settings (`MemorySystemConfig`), along with functions to load configurations primarily from environment variables.

## Internal Dependencies
- None

## Classes

### `MemGConfig`
- **Description**: Dataclass holding core memory system configuration parameters such as similarity thresholds, processing settings, and database names. It includes validation logic upon initialization and methods for conversion to/from dictionaries and environment variables.
- **Attributes**:
  - `similarity_threshold`: float = 0.7 - Threshold for conflict detection.
  - `score_threshold`: float = 0.3 - Minimum score for search results.
  - `high_similarity_threshold`: float = 0.9 - Threshold for duplicate detection.
  - `max_summary_tokens`: int = 750 - Maximum tokens for document summarization.
  - `enable_ai_type_verification`: bool = True - Flag for AI-based type detection.
  - `enable_temporal_reasoning`: bool = False - Flag to enable temporal reasoning.
  - `vector_dimension`: int = 384 - Dimension of embedding vectors.
  - `batch_processing_size`: int = 50 - Batch size for bulk operations.
  - `template_name`: str = "default" - Name of the active template.
  - `qdrant_collection_name`: str = "memories" - Name of the Qdrant collection.
  - `kuzu_database_path`: str = "kuzu_db" - Path to the Kuzu database.
- **Methods**:
  - `__post_init__`:
    - **Description**: Validates the range of threshold parameters and `max_summary_tokens` after initialization.
    - **Inputs**: None
    - **Returns**: None
  - `to_dict`:
    - **Description**: Converts the `MemGConfig` instance into a dictionary.
    - **Inputs**: None
    - **Returns**: `dict[str, Any]` - Dictionary representation of the configuration.
  - `from_dict` (classmethod):
    - **Description**: Creates a `MemGConfig` instance from a dictionary.
    - **Inputs**:
      - `config_dict`: dict[str, Any] - Dictionary containing configuration parameters.
    - **Returns**: `MemGConfig` - A new `MemGConfig` object.
  - `from_env` (classmethod):
    - **Description**: Creates a `MemGConfig` instance by reading configuration values from environment variables. Provides default values if environment variables are not set.
    - **Inputs**: None
    - **Returns**: `MemGConfig` - A new `MemGConfig` object populated from environment variables.

### `MemorySystemConfig`
- **Description**: Dataclass representing system-wide configuration, including a nested `MemGConfig` instance, debug mode, logging level, and MCP server settings.
- **Attributes**:
  - `memg`: MemGConfig - An instance of `MemGConfig` for memory-specific settings.
  - `debug_mode`: bool = False - Flag for enabling debug mode.
  - `log_level`: str = "INFO" - Logging level for the system.
  - `mcp_port`: int = 8787 - Port number for the MCP server.
  - `mcp_host`: str = "0.0.0.0" - Host address for the MCP server.
- **Methods**:
  - `__post_init__`:
    - **Description**: Validates the `mcp_port` and `log_level` parameters after initialization.
    - **Inputs**: None
    - **Returns**: None
  - `from_env` (classmethod):
    - **Description**: Creates a `MemorySystemConfig` instance by reading system configuration values from environment variables. It also calls `MemGConfig.from_env` to populate nested memory configurations.
    - **Inputs**: None
    - **Returns**: `MemorySystemConfig` - A new `MemorySystemConfig` object populated from environment variables.

## Functions

### `get_config`
- **Description**: Retrieves the system configuration, prioritizing values set via environment variables.
- **Inputs**: None
- **Returns**: `MemorySystemConfig` - The current system configuration.
