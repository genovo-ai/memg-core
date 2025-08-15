# YAML Schema Enforcement Plan

This document outlines the necessary changes to make the `memg-core` system strictly loyal to the YAML schema. The guiding principle is: **The YAML registry is the single source of truth for all entity types, fields, and validation rules. The Python code must be completely type-agnostic and must not contain any hardcoded field names or fallback logic.**

---

## 1. `src/memg_core/core/models.py`

### Problem
The `Memory.__getattr__` method currently contains a fallback to the legacy `statement` field. This violates the principle of strict YAML enforcement by creating an invisible backward-compatibility layer that can hide schema errors. Hardcoded property methods were also present and have been removed, but this `__getattr__` fallback remains a critical issue.

### The Fix
The `__getattr__` method will be simplified to perform a direct lookup in the `payload` dictionary *only*. If a field is not a standard `Memory` attribute and is not in the `payload`, it will raise an `AttributeError`. This forces all field access to be explicitly defined by the YAML schema.

### Rationale
This change makes the `Memory` model a pure, type-agnostic container. There will be no "magic" that makes old data work. If the data doesn't conform to the current YAML schema, it is invalid. This enforces data integrity and makes behavior predictable.

---

## 2. `src/memg_core/api/public.py`

### Problem
The public API currently exposes type-specific helper functions: `add_note`, `add_document`, and `add_task`. These functions have hardcoded parameter names (`text`, `summary`, `body`) and manually construct the payload dictionary. This hardcodes a specific set of entities into the core library, violating the type-agnostic principle.

### The Fix
1.  The specific helper functions (`add_note`, `add_document`, `add_task`) will be **removed**.
2.  The generic `add_memory` function will be the **sole entry point for creating memories**.
3.  Its implementation will be hardened to immediately use the `YamlTranslator.get_entity_model()` to validate the incoming `payload` against a dynamically generated Pydantic model. If validation fails, it will raise a `ValidationError` immediately.

### Rationale
This change forces all clients of the library (including the MCP server) to be aware of the YAML schema. They can no longer rely on hardcoded helpers. They MUST construct a valid payload dictionary, making the public API truly generic and loyal to the YAML registry.

---

## 3. `mcp/mcp_server.py`

### Problem
This is the most significant offender.
1.  The `MemgCoreBridge` class contains a large `if/elif/else` block that hardcodes logic for different `memory_type` strings.
2.  The MCP tools (`add_note_tool`, `add_document_tool`, `add_task_tool`) have hardcoded, type-specific parameters (`text`, `summary`). This mirrors the flawed design of the old public API.
3.  The search result formatting manually accesses `.content` and `.title`, which are no longer guaranteed to exist.

### The Fix
1.  The `MemgCoreBridge` class will be **completely removed**. It is an unnecessary layer of hardcoded logic.
2.  The specific `add_note_tool`, `add_document_tool`, and `add_task_tool` will be **removed**.
3.  A **single, generic `mcp_gmem_add_memory` tool** will be implemented. It will accept `memory_type: str`, `user_id: str`, and `payload: dict`.
4.  The docstring for this generic tool will be **dynamically generated**. It will load the YAML schema at startup and present the required fields and types for *all* defined entities, providing a live, accurate guide for any client.
5.  The search tool's response formatting will be made generic, accessing only core `Memory` fields and the raw `payload` dictionary, without assuming any specific keys exist.

### Rationale
This makes the MCP server a thin, generic wrapper around the public API. It will have no knowledge of specific memory types. It will be completely driven by the YAML schema, and any changes to the YAML will be automatically reflected in the tool's documentation for API consumers.

---

## 4. `src/memg_core/core/pipeline/retrieval.py`

### Problem
The retrieval pipeline, especially `_rows_to_memories`, is still riddled with logic that assumes the existence of a `statement` field and other specific entity fields from the database query result. The `_get_anchor_text_from_payload` function also has a fallback.

### The Fix
1.  The fallback logic in `_get_anchor_text_from_payload` will be removed.
2.  The `_rows_to_memories` function will be rewritten to be completely generic. It will iterate through the columns in a Kuzu query result and populate the `payload` dictionary with any column that is not a known core `Memory` field (like `id`, `user_id`, `created_at`).
3.  All other logic within the pipeline that needs anchor text will be modified to strictly call `build_anchor_text(memory)`, which relies on the YAML translator. There will be no more direct access to a `statement` field.

### Rationale
This ensures that the retrieval pipeline is as type-agnostic as the indexing pipeline. It constructs `Memory` objects from raw database data without making assumptions about the schema, ensuring that the data integrity is preserved from storage to retrieval.

---

## 5. `tests/`

### Problem
Many tests currently create `Memory` objects with hardcoded `payload` dictionaries that may not align with the strict enforcement of the YAML schema. They often rely on the fallback mechanisms that are being removed.

### The Fix
All unit, integration, and e2e tests will be reviewed and updated to:
1.  Use the public `add_memory` API to create test data, ensuring it passes the same validation as production code.
2.  Where direct `Memory` instantiation is necessary, the payloads will be updated to be 100% compliant with the `core.minimal.yaml` schema.
3.  Assertions will be updated to use the dynamic `__getattr__` access on `Memory` objects, rather than assuming specific keys in the `payload` dictionary.

### Rationale
This brings the test suite in line with the new, stricter reality of the codebase, ensuring that our tests accurately reflect the enforced YAML compliance and will fail if any future changes violate the schema.
