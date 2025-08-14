# `memg_core/core/indexing.py`

## Module Description
This module contains **DEPRECATED** indexing logic. Its functions have been superseded by the YAML translator module, which handles anchor text generation based on YAML-defined entity schemas. This module is retained for backward compatibility but is slated for removal.

## Internal Dependencies
- `..models`: `Memory` for the memory data model.

## Functions

### `build_index_text`
- **Description**: **DEPRECATED**. This function previously built the index text for a memory. It attempts to extract text from the `content` or `summary` fields within the memory's payload. This functionality has been replaced by `build_anchor_text` in `yaml_translator.py`, which uses a more robust YAML-defined anchor field strategy.
- **Inputs**:
  - `memory`: Memory - The Memory object for which to build index text.
- **Returns**: `str` - The extracted index text, or a fallback string if no relevant fields are found.
