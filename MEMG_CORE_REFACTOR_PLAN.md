## MEMG Core Slim-Down: Cycles, Tickets, Parallel Work, and PR Plan

### Purpose
Create a truly lightweight memg-core while safely extracting advanced features (templates, prompts, AI pipelines, validation, conversations) to an external package or a local `_stash/extras/` backup during refactor.

### Branching & CI
- Branch: `dev-test` (no CI/actions) [[memory:5704734]]
- Default workflow: short cycles; frequent, small PRs to `dev-test`; fast feedback

### Success Metrics
- Type errors: 0
- Coverage: ≥ 80%
- Clear, minimal API for store/search
- Import time and dependency surface reduced

---

## Cycles and Tickets

### Cycle-0: Foundation and Baseline
- [ ] C0-T1: Create `dev-test` branch and disable CI [[memory:5704734]] (2 SP)
  - Create branch, push; ensure CI skip rules
- [ ] C0-T2: Capture baseline metrics (2 SP)
  - pytest -q, pyright, coverage; store under `artifacts/baseline/`

### Cycle-1: Safe Extraction to `_stash/extras`
- [ ] C1-T1: Move non-core modules to `_stash/extras` via `git mv` (5 SP)
  - processing: `unified_memory_processor.py`, `memory_processor.py`, `conversation_context.py`
  - templates: `templates/` (all)
  - models: `models/template_models.py`
  - prompts: entire `prompts/`
  - validation: `validation/` (all)
  - schemas tooling: `utils/schema_generator.py`, `utils/unified_schemas.py`
- [ ] C1-T2: Add import shims with DeprecationWarnings (3 SP)
  - Keep thin modules at original paths that re-export from `_stash/extras/`
- [ ] C1-T3: Verify post-move stability (2 SP)
  - Run tests; if breakages, selectively restore or extend shims; log each restore

### Cycle-2: Minimal Core Models and Retrieval
- [ ] C2-T1: Introduce `models/core_models.py` (5 SP)
  - Minimal `Memory`, `Entity` (and optional `Relationship`); remove task/project/template fields
- [ ] C2-T2: Slim `processing/memory_retriever.py` (3 SP)
  - Qdrant-only retrieval; no template/schema/prompt dependencies
- [ ] C2-T3: Remove dynamic SCHEMAS reliance from core (3 SP)
  - If any schema remains, keep a tiny static one or none

### Cycle-3: Prompt/Pipeline Purge and API Finalization
- [ ] C3-T1: Remove prompts and `PromptLoader` from core (3 SP)
  - Ensure no core references remain; extras/shims provide any needed functionality
- [ ] C3-T2: Finalize minimal core API (5 SP)
  - add_note/add_document/search; update README examples

### Cycle-4: Quality and Documentation
- [ ] C4-T1: Author MIGRATION.md (2 SP)
  - How to adopt the full MEMG extras package for templates/pipelines
- [ ] C4-T2: Raise coverage to 80%+ for core (5 SP)
- [ ] C4-T3: Eliminate type errors (pyright = 0) (3 SP)

### Cycle-5: Extras Package
- [ ] C5-T1: Create `memg-extras` package (8 SP)
  - Host templates, prompts, unified/legacy processors, validation
  - Optional: adjust shims to import from extras if installed

---

## What Stays vs Moves (Core Boundary)

### Keep in Core
- Minimal models: `Memory`, `Entity` (optional `Relationship`)
- Qdrant interface and minimal store/search APIs
- Embeddings utility
- No template system, no prompts, no processors, no conversation flows, no advanced validation

### Move to Extras (or `_stash/extras/` during refactor)
- `processing/unified_memory_processor.py`, `processing/memory_processor.py`, `processing/conversation_context.py`
- `templates/` (all) and `models/template_models.py`
- `prompts/` (all)
- `validation/` (all)
- `utils/schema_generator.py`, `utils/unified_schemas.py`

---

## Parallelization Guide (Who can do what in parallel?)

Parallel within Cycle-1
- P1: Move processing/ files to `_stash/extras/` (PR A)
- P2: Move templates/ and template models (PR B)
- P3: Move prompts/ (PR C)
- P4: Move validation/ and schema tools (PR D)
- P5: Add import shims (PR E) — can start once first moves land

Parallel within Cycle-2
- P6: Implement minimal `core_models.py` (PR F)
- P7: Refactor `memory_retriever` to Qdrant-only (PR G)
- P8: Remove SCHEMAS reliance from core (PR H)

Parallel within Cycle-3/4
- P9: Remove prompts/PromptLoader from core (PR I)
- P10: Finalize minimal API, README updates (PR J)
- P11: MIGRATION.md (PR K)
- P12: Add core-focused tests to reach 80%+ coverage (PR L)
- P13: Fix remaining type errors (PR M)

Cross-cycle parallel
- P14: Initialize `memg-extras` repo/package (PR N) — can start during C2, merged in C5

---

## Suggested PR Breakdown (to `dev-test`)

1. PR A-D: Directory moves to `_stash/extras/` (separate PRs ok); label as "safe extraction"
2. PR E: Import shims with DeprecationWarnings
3. PR F: Minimal `core_models.py` and replacements
4. PR G: Qdrant-only `memory_retriever` refactor
5. PR H: Remove dynamic SCHEMAS from core
6. PR I: Remove prompts + PromptLoader; verify core build
7. PR J: Minimal API and README
8. PR K: MIGRATION.md
9. PR L: Test additions for coverage
10. PR M: Type fixes to 0 errors
11. PR N: `memg-extras` initial publish (independent repo); adjust shims optionally

Each PR should:
- Be small and focused
- Include a short rollback note
- Run only minimal checks suitable for `dev-test`

---

## Acceptance Criteria per Cycle
- C0: `dev-test` exists, CI disabled; baseline metrics stored
- C1: Non-core code moved; tests still run via shims; no additional failures vs baseline
- C2: Core builds with minimal models and Qdrant-only retrieval; no template/prompt/schema deps in core paths
- C3: Minimal API available; no prompts/processors in core
- C4: ≥80% coverage and 0 type errors; migration docs ready
- C5: `memg-extras` package hosts extracted features

---

## Risk & Rollback
- Use `git mv` to preserve history
- `_stash/extras/` keeps all code accessible for quick restoration
- Import shims allow gradual migration without breaking imports immediately

---

## Commands & Snippets

Branch and baseline
```sh
git checkout -b dev-test
git push -u origin dev-test
# run baseline
pytest -q || true
pyright || true
pytest --maxfail=1 --disable-warnings --cov=. --cov-report=term-missing || true
```

Safe moves (examples)
```sh
git mv src/memory_system/processing/unified_memory_processor.py _stash/extras/
git mv src/memory_system/processing/memory_processor.py _stash/extras/
git mv src/memory_system/processing/conversation_context.py _stash/extras/
git mv src/memory_system/templates _stash/extras/templates
git mv src/memory_system/models/template_models.py _stash/extras/models/
git mv src/memory_system/prompts _stash/extras/prompts
git mv src/memory_system/validation _stash/extras/validation
git mv src/memory_system/utils/{schema_generator.py,unified_schemas.py} _stash/extras/utils/
```

Shim pattern (Python)
```python
# src/memory_system/processing/unified_memory_processor.py
import warnings
warnings.warn(
    "Deprecated: moved to _stash/extras/processing/unified_memory_processor.py",
    DeprecationWarning,
)
from _stash.extras.processing.unified_memory_processor import *  # noqa
```

---

## Notes for Contributors
- Target branch: `dev-test` [[memory:5704734]]
- Prefer small, independent PRs per the Parallelization Guide
- If a PR causes unexpected failures, revert or extend shims and proceed; we optimize for iteration speed
