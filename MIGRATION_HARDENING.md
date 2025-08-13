# MEMG-CORE Final Hardening - Migration Notes

## Summary

The final hardening has been completed with minimal changes to ensure core purity. **No public API signatures changed** - all changes are internal implementation details.

## Changes Made

### 1. Core Writer (indexer.py)
- Removed all plugin/YAML imports and environment checks
- Added optional `index_text_override` parameter for external control
- Core now uses only deterministic indexing

### 2. API Layer (public.py)
- Wrapped plugin imports in try/except ImportError
- Moved environment reading (neighbor_cap) to API layer
- Plugin support is now truly optional - works if missing

### 3. Retrieval Pipeline (retrieval.py)
- Added `neighbor_cap` parameter to avoid env reads
- Removed all `os.getenv()` calls from pipeline
- All configuration now passed as parameters

### 4. Kuzu Interface (kuzu.py)
- Changed RuntimeError to typed DatabaseError for missing KUZU_DB_PATH
- Normalized query result handling (qr → df → dict)

### 5. Indexing (indexing.py)
- Removed yaml_anchor_text parameter to pass CI checks
- Pure deterministic logic only

## CI Guardrails

Added `ci_guardrails.sh` script that enforces:
- Core cannot import from plugins/ or showcase/
- Retrieval pipeline cannot read environment variables
- Indexing cannot reference YAML

Run with: `./ci_guardrails.sh`

## Smoke Tests

Added `smoke_tests.py` with three minimal tests:
- A) Vector fallback when graph is empty
- B) Graph-first search with neighbor expansion
- C) Document indexing determinism

## No Breaking Changes

All public API functions maintain the same signatures:
- `add_note(text, user_id, title=None, tags=None)`
- `add_document(text, user_id, title=None, summary=None, tags=None)`
- `add_task(text, user_id, title=None, due_date=None, tags=None)`
- `search(query, user_id, limit=20, filters=None)`

Internal changes are transparent to users.
