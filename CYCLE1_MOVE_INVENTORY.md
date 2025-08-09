# Cycle 1 Move Inventory: Files to Extract to `_stash/extras/`

## Summary
This document catalogs all files that need to be moved from the core library to `_stash/extras/` during Cycle 1 of the MEMG Core slim-down refactor.

**Total files to move**: 25 files + 7 directories
**Strategy**: Use `git mv` to preserve history, then add import shims

---

## Directory Structure to Create

```
_stash/extras/
├── processing/
│   ├── __init__.py
│   ├── unified_memory_processor.py
│   ├── memory_processor.py
│   └── conversation_context.py
├── templates/
│   ├── __init__.py
│   ├── base.py
│   ├── default.py
│   └── registry.py
├── models/
│   ├── __init__.py
│   └── template_models.py
├── prompts/
│   ├── conversation_processing/
│   │   ├── conversation_summarization.md
│   │   └── insight_extraction.md
│   ├── memory_extraction/
│   │   └── fact_extraction.txt
│   ├── memory_processing/
│   │   ├── document_summarization.md
│   │   ├── entity_extraction.md
│   │   └── type_classification.md
│   └── unified_analysis/
│       └── content_analysis.md
├── validation/
│   ├── __init__.py
│   ├── graph_validator.py
│   ├── pipeline_validator.py
│   ├── schema_validator.py
│   └── standalone_validator.py
└── utils/
    ├── __init__.py
    ├── schema_generator.py
    └── unified_schemas.py
```

---

## Move Commands (in order)

### 1. Processing Files (PR A)
```bash
# Create directory structure
mkdir -p _stash/extras/processing

# Move files (preserves git history)
git mv src/memory_system/processing/unified_memory_processor.py _stash/extras/processing/
git mv src/memory_system/processing/memory_processor.py _stash/extras/processing/
git mv src/memory_system/processing/conversation_context.py _stash/extras/processing/

# Copy __init__.py (will need modification)
cp src/memory_system/processing/__init__.py _stash/extras/processing/
```

### 2. Templates and Template Models (PR B)
```bash
# Create directory structure
mkdir -p _stash/extras/templates
mkdir -p _stash/extras/models

# Move entire templates directory
git mv src/memory_system/templates/* _stash/extras/templates/

# Move template models
git mv src/memory_system/models/template_models.py _stash/extras/models/

# Create __init__.py files
touch _stash/extras/models/__init__.py
```

### 3. Prompts (PR C)
```bash
# Move entire prompts directory (preserves subdirectory structure)
git mv src/memory_system/prompts _stash/extras/prompts
```

### 4. Validation (PR D)
```bash
# Move entire validation directory
git mv src/memory_system/validation _stash/extras/validation
```

### 5. Utils Schema Tools (PR D continued)
```bash
# Create utils directory
mkdir -p _stash/extras/utils

# Move specific schema-related utils
git mv src/memory_system/utils/schema_generator.py _stash/extras/utils/
git mv src/memory_system/utils/unified_schemas.py _stash/extras/utils/

# Create __init__.py
touch _stash/extras/utils/__init__.py
```

---

## Import Dependencies Analysis

### High-Risk Moves (Many Dependencies)
1. **`unified_memory_processor.py`** - Imported by sync_wrapper.py, possibly tests
2. **`memory_processor.py`** - Core processing logic, likely many imports
3. **`template_models.py`** - Used throughout the codebase for Entity/Relationship
4. **`validation/`** - Used by processors and possibly MCP tools

### Medium-Risk Moves
1. **`templates/`** - Used by template_models and processors
2. **`prompts/`** - Used by processors and utils/prompts.py
3. **`schema_generator.py`** - May be used by validation or processing

### Low-Risk Moves
1. **`conversation_context.py`** - Likely isolated feature
2. **`unified_schemas.py`** - Specific to unified processor

---

## Files That Stay in Core

### Keep in `src/memory_system/processing/`
- `memory_retriever.py` (will be simplified in Cycle 2)
- `__init__.py` (will be updated)

### Keep in `src/memory_system/models/`
- `core.py` (will be simplified in Cycle 2)
- `api.py` (API models stay)
- `extraction.py` (basic extraction stays)
- `__init__.py` (will be updated)

### Keep in `src/memory_system/utils/`
- `embeddings.py` (core functionality)
- `genai.py` (core functionality)
- `prompts.py` (will be simplified/removed in Cycle 3)
- `schemas.py` (core schemas stay)
- `README_LOCKED.md` (documentation)
- `__init__.py` (will be updated)

### Keep Everything Else
- `config.py`, `exceptions.py`, `logging_config.py`
- `kuzu_graph/`, `qdrant/` (core storage interfaces)
- `sync_wrapper.py`, `template_init.py`, `version.py`
- `api/` (API definitions stay)

---

## Import Shims to Create (PR E)

After moves, create shim files at original locations:

### `src/memory_system/processing/unified_memory_processor.py`
```python
import warnings
warnings.warn(
    "unified_memory_processor moved to _stash/extras/processing/. "
    "Use memg-extras package for advanced processing.",
    DeprecationWarning,
    stacklevel=2
)
from _stash.extras.processing.unified_memory_processor import *  # noqa
```

### `src/memory_system/processing/memory_processor.py`
```python
import warnings
warnings.warn(
    "memory_processor moved to _stash/extras/processing/. "
    "Use memg-extras package for advanced processing.",
    DeprecationWarning,
    stacklevel=2
)
from _stash.extras.processing.memory_processor import *  # noqa
```

### `src/memory_system/models/template_models.py`
```python
import warnings
warnings.warn(
    "template_models moved to _stash/extras/models/. "
    "Use memg-extras package for template-aware models.",
    DeprecationWarning,
    stacklevel=2
)
from _stash.extras.models.template_models import *  # noqa
```

### Similar shims for:
- `conversation_context.py`
- `validation/__init__.py` (re-exports from _stash/extras/validation/)
- `templates/__init__.py` (re-exports from _stash/extras/templates/)
- `utils/schema_generator.py`
- `utils/unified_schemas.py`

---

## Rollback Strategy

If any move causes critical failures:

1. **Quick restore**: `git mv _stash/extras/path/file.py src/memory_system/path/`
2. **Shim removal**: Delete the shim file
3. **Import fix**: Update any imports that were changed

Each PR should be small enough to rollback completely if needed.

---

## Testing Strategy

After each move:
1. Run basic import tests: `python -c "import memory_system"`
2. Run core tests: `pytest tests/test_basic.py -v`
3. Check for import errors in key files
4. If failures, either fix imports or create/extend shims

---

## Success Criteria for Cycle 1

- [ ] All 25 files moved to `_stash/extras/` with history preserved
- [ ] Import shims in place with deprecation warnings
- [ ] Basic tests still pass (may have warnings, but no errors)
- [ ] Core functionality accessible through shims
- [ ] No import errors when running `python -c "import memory_system"`

---

## Notes for Parallel Work

- PRs A-D can be done in parallel by different contributors
- PR E (shims) depends on A-D being merged first
- Each PR should be independent and rollback-safe
- Test after each merge to catch issues early
