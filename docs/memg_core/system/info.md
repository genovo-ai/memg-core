# `memg_core/system/info.py`

## Module Description
This module provides utility functions for retrieving core system information about the MEMG memory system. It gathers details related to configuration, storage statistics (Qdrant and Kuzu), and the status of optional plugins like the YAML schema loader. This information is crucial for health checks and operational insights.

## Internal Dependencies
- `..core.config`: `get_config` for retrieving system-wide configuration.
- `..core.interfaces.kuzu`: `KuzuInterface` for checking Kuzu database availability.
- `..core.interfaces.qdrant`: `QdrantInterface` for retrieving Qdrant collection information.

## Functions

### `get_system_info`
- **Description**: Gathers and returns a comprehensive dictionary of system information for MEMG. This includes details from the core configuration, the status and statistics of the Qdrant and Kuzu storage interfaces, and the enablement and loading status of the YAML schema plugin.
- **Inputs**:
  - `qdrant`: QdrantInterface | None = None - An optional instance of `QdrantInterface`. If not provided, a temporary instance will be created to fetch stats.
  - `kuzu`: KuzuInterface | None = None - An optional instance of `KuzuInterface`. If not provided, a temporary instance will be created to test availability.
- **Returns**: `dict[str, Any]` - A dictionary containing various system information:
  - `config`: Core configuration settings.
  - `plugins`: Status of plugins, specifically `yaml_schema` (enabled, path, loaded).
  - `qdrant`: Qdrant collection statistics (collection name, existence, vector/point counts, vector size) or an error message if unavailable.
  - `kuzu`: Kuzu database availability and path, or an error message.
  - `graph`: Graph-specific settings, such as `neighbor_limit`.
