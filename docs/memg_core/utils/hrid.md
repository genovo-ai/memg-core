# `memg_core/utils/hrid.py`

## Module Description
This module provides a utility for generating and parsing Human-Readable IDs (HRIDs) for MEMG Core. The HRID format is `{TYPE_UPPER}_{AAA000}`, where `TYPE_UPPER` is an uppercase alphanumeric type name, `AAA` is a base-26 alphabetical component, and `000` is a numeric suffix. The module uses in-memory counters for generation, which are reset when the application restarts.

## Internal Dependencies
- None

## External Dependencies
- `re`: For regular expression matching of HRIDs.
- `typing`: For type hints (`Tuple`, `Any` implied).

## Functions

### `_alpha_to_idx` (private)
- **Description**: Converts a three-letter alphabetical string (e.g., "AAA") into its corresponding base-26 integer index.
- **Inputs**:
  - `alpha`: `str` - The alphabetical string to convert.
- **Returns**: `int` - The integer index.
- **Schema**:
  - Input: `alpha` (String)
  - Output: `int` (Integer)
  - Type Mixing: Defined type

### `_idx_to_alpha` (private)
- **Description**: Converts a base-26 integer index back into its three-letter alphabetical string representation.
- **Inputs**:
  - `idx`: `int` - The integer index.
- **Returns**: `str` - The three-letter alphabetical string.
- **Schema**:
  - Input: `idx` (Integer)
  - Output: `str` (String)
  - Type Mixing: Defined type

### `generate_hrid`
- **Description**: Generates the next sequential HRID for a given type name. It uses an in-memory counter that increments the numeric part and rolls over to the alphabetical part when the numeric part exceeds 999.
- **Inputs**:
  - `type_name`: `str` - The type name for the HRID (e.g., "TASK", "NOTE").
- **Returns**: `str` - The newly generated HRID.
- **Raises**: `ValueError` - If the HRID space is exhausted for the given type.
- **Schema**:
  - Input: `type_name` (String)
  - Output: `str` (String)
  - Type Mixing: Defined type

### `parse_hrid`
- **Description**: Parses a given HRID string into its constituent parts: type, alphabetical component, and numeric component.
- **Inputs**:
  - `hrid`: `str` - The HRID string to parse.
- **Returns**: `tuple[str, str, int]` - A tuple containing the type, alphabetical part, and numeric part.
- **Raises**: `ValueError` - If the HRID format is invalid.
- **Schema**:
  - Input: `hrid` (String)
  - Output: `tuple[str, str, int]` (Tuple of String, String, and Integer)
  - Type Mixing: Defined type

### `reset_counters`
- **Description**: Resets all in-memory HRID counters. This is primarily intended for use in testing environments to ensure a clean state between test runs.
- **Inputs**: None
- **Returns**: None
- **Schema**:
  - Input: None
  - Output: None
  - Type Mixing: Defined type

### `_type_key` (private)
- **Description**: Generates a deterministic numeric key for type names to enable cross-type ordering. It encodes up to the first 8 characters of the type name in base-37 (A–Z=1–26, 0–9=27–36).
- **Inputs**:
  - `t`: `str` - The type name to encode.
- **Returns**: `int` - The numeric key for the type.
- **Schema**:
  - Input: `t` (String)
  - Output: `int` (Integer)
  - Type Mixing: Defined type

### `hrid_to_index`
- **Description**: Converts an HRID into a single integer index for ordering across different types. It uses the type key in the upper bits and the intra-type ordering (alphabetical + numeric) in the lower bits.
- **Inputs**:
  - `hrid`: `str` - The HRID string to convert.
- **Returns**: `int` - The corresponding integer index that enables cross-type ordering.
- **Schema**:
  - Input: `hrid` (String)
  - Output: `int` (Integer)
  - Type Mixing: Defined type
