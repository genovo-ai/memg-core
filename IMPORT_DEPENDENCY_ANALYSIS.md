# Import Dependency Analysis for Cycle 1 Moves

## Critical Dependencies Found

### 1. **UnifiedMemoryProcessor** (High Risk)
**Imported by:**
- `src/memory_system/sync_wrapper.py:17`

**Dependencies:**
- Uses `template_models` (TemplateAwareEntity, TemplateAwareRelationship)
- Uses `validation.PipelineValidator`
- Uses various core utilities (genai, embeddings, schemas)

**Risk**: Medium - Only one import, but sync_wrapper is a core API file

### 2. **MemoryProcessor** (High Risk)
**Imported by:**
- `src/memory_system/processing/__init__.py:3`
- Likely imported by tests and other processors

**Dependencies:**
- Uses `template_models` (TemplateAwareEntity, TemplateAwareRelationship)
- Uses `validation.PipelineValidator`
- Uses `utils.prompts.prompt_loader` (multiple locations)

**Risk**: High - Core processing functionality, widely imported

### 3. **TemplateModels** (CRITICAL Risk)
**Imported by:**
- `src/memory_system/models/__init__.py:34-35` (re-exported as Entity/Relationship)
- `src/memory_system/processing/unified_memory_processor.py:17-18`
- `src/memory_system/processing/memory_processor.py:17-18`

**Dependencies:**
- Uses `templates.registry.get_template_registry`

**Risk**: CRITICAL - These are re-exported in models/__init__.py as the main Entity/Relationship classes

### 4. **Validation Module** (Medium Risk)
**Imported by:**
- `src/memory_system/processing/unified_memory_processor.py:28`
- `src/memory_system/processing/memory_processor.py:27`

**Risk**: Medium - Only used by processors we're also moving

### 5. **Templates Module** (High Risk)
**Imported by:**
- `src/memory_system/processing/memory_retriever.py:14` (get_template_registry)
- `src/memory_system/models/template_models.py:12` (get_template_registry)
- `src/memory_system/utils/schemas.py:11` (get_template_registry)
- `src/memory_system/template_init.py:8` (get_template_registry, initialize_template_system)
- `src/memory_system/utils/schema_generator.py:8` (MemoryTemplate)

**Risk**: High - Used by multiple core files including memory_retriever (staying in core)

### 6. **Prompts Usage** (Medium Risk)
**Imported by:**
- `src/memory_system/processing/conversation_context.py:16`
- `src/memory_system/processing/memory_processor.py:379,442,646`
- `src/memory_system/utils/__init__.py:5` (re-exported)

**Risk**: Medium - Used by files we're moving, but also re-exported in utils

---

## Move Order Strategy (Risk-Based)

### Phase 1: Low-Risk Moves (Can be done in parallel)
1. **Prompts directory** - Self-contained, only used by files we're moving
2. **Conversation Context** - Appears isolated, only imports prompts

### Phase 2: Medium-Risk Moves (Requires shims)
3. **Validation directory** - Only used by processors we're moving
4. **Schema tools** (schema_generator.py, unified_schemas.py) - Specific utilities

### Phase 3: High-Risk Moves (Critical shims needed)
5. **Template system** - Many dependencies, need comprehensive shims
6. **Memory Processor** - Core functionality, widely used
7. **Unified Memory Processor** - Less widely used but imported by sync_wrapper

### Phase 4: Critical Move (Most dangerous)
8. **Template Models** - These are re-exported as main Entity/Relationship classes

---

## Required Shims by Priority

### CRITICAL Shims (Must work perfectly)
```python
# src/memory_system/models/template_models.py
import warnings
warnings.warn(
    "template_models moved to _stash/extras/models/. Use memg-extras package.",
    DeprecationWarning, stacklevel=2
)
from _stash.extras.models.template_models import *  # noqa
```

### HIGH Priority Shims
```python
# src/memory_system/processing/memory_processor.py
import warnings
warnings.warn(
    "memory_processor moved to _stash/extras/processing/. Use memg-extras package.",
    DeprecationWarning, stacklevel=2
)
from _stash.extras.processing.memory_processor import *  # noqa

# src/memory_system/templates/__init__.py
import warnings
warnings.warn(
    "templates moved to _stash/extras/templates/. Use memg-extras package.",
    DeprecationWarning, stacklevel=2
)
from _stash.extras.templates import *  # noqa
```

### MEDIUM Priority Shims
```python
# src/memory_system/processing/unified_memory_processor.py
# src/memory_system/validation/__init__.py
# Similar pattern for other modules
```

---

## Files That Will Break Without Shims

### Immediate Breakage (Without shims)
- `sync_wrapper.py` - imports UnifiedMemoryProcessor
- `models/__init__.py` - re-exports TemplateAwareEntity/Relationship
- `memory_retriever.py` - imports get_template_registry
- `template_init.py` - imports template registry functions
- `utils/schemas.py` - imports get_template_registry

### Tests That Will Break
- Any test importing Entity/Relationship (uses template_models)
- Any test importing MemoryProcessor or UnifiedMemoryProcessor
- Integration tests using template functionality

---

## Recommended Move Sequence

### Step 1: Prepare Infrastructure
```bash
# Create _stash/extras directory structure
mkdir -p _stash/extras/{processing,templates,models,prompts,validation,utils}
```

### Step 2: Move Low-Risk Files First
```bash
# Move prompts (self-contained)
git mv src/memory_system/prompts _stash/extras/prompts

# Move conversation_context (only uses prompts)
git mv src/memory_system/processing/conversation_context.py _stash/extras/processing/
```

### Step 3: Move Medium-Risk Files
```bash
# Move validation (only used by processors we're moving)
git mv src/memory_system/validation _stash/extras/validation

# Move schema tools
git mv src/memory_system/utils/schema_generator.py _stash/extras/utils/
git mv src/memory_system/utils/unified_schemas.py _stash/extras/utils/
```

### Step 4: Create Shims for High-Risk Files
```bash
# Create shims BEFORE moving the actual files
# This ensures imports don't break during the transition
```

### Step 5: Move High-Risk Files (with shims in place)
```bash
# Move templates
git mv src/memory_system/templates _stash/extras/templates

# Move processors
git mv src/memory_system/processing/memory_processor.py _stash/extras/processing/
git mv src/memory_system/processing/unified_memory_processor.py _stash/extras/processing/
```

### Step 6: Move Critical Files (with comprehensive shims)
```bash
# Move template_models (most dangerous)
git mv src/memory_system/models/template_models.py _stash/extras/models/
```

---

## Testing Strategy After Each Move

1. **Basic Import Test**: `python -c "import memory_system"`
2. **Core API Test**: `python -c "from memory_system import Memory, Entity"`
3. **Sync Wrapper Test**: `python -c "from memory_system.sync_wrapper import SyncMemorySystem"`
4. **Run Basic Tests**: `pytest tests/test_basic.py -v`

If any test fails, either:
- Add/fix the shim
- Temporarily revert the move
- Fix the import in the failing code

---

## Success Criteria

- [ ] All imports work with deprecation warnings
- [ ] No import errors in core functionality
- [ ] Basic tests pass (may have warnings)
- [ ] Entity/Relationship still available from models
- [ ] SyncMemorySystem still works (key API)

This analysis shows that while the moves are feasible, the template_models.py move is the most critical and needs the most careful handling.
