# `memg_core/core/indexing.py`

## Module Description
This module contains **DEPRECATED** indexing logic. Its functions have been superseded by the YAML translator module (`memg_core.core.yaml_translator`) and the main indexing pipeline (`memg_core.core.pipeline.indexer`). This module is retained for backward compatibility in tests but is slated for removal. **No new functionality or modifications should be added to this module.**

## Internal Dependencies
- None (Originally depended on `..models`, but functionality has been moved).

## Functions

### `build_index_text` (DEPRECATED)
- **Description**: This function previously built the index text for a memory. It has been replaced by `build_anchor_text` in `memg_core.core.yaml_translator`, which uses a more robust YAML-defined anchor field strategy.
- **Inputs**: (No longer relevant; function removed/superseded)
- **Returns**: (No longer relevant; function removed/superseded)
- **Schema**: (N/A - Deprecated)
- **Type Mixing**: (N/A - Deprecated)
