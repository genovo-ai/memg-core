## memg-core — Round Objectives (Single Source Brief)

### Why this round exists
- Remove historical baggage and ship a truly minimal, graph-first core that is easy to reason about, test, and ship.
- Stop relying on old modules “still working”; remove or isolate them so the core stands on its own.

### Non‑negotiables
- Core is graph-first (GraphRAG), vector is complementary (fallback/rerank only).
- Minimal types only in core: `note`, `document`, `task`.
- No domain baggage in core (no project/boards/error/solution catalogs, etc.).
- MCP is out of scope for this round; do not block on it, do not couple core to MCP.

### Scope of this round (do now)
- Rename and align: imports must be under `memg_core.*` only.
- Strip non-core models/fields already called out in docs:
  - Removed now: `Project` model, `project_id/project_name` fields from payloads and graph.
  - Keep `Memory`, `Entity`, `Relationship` minimal; `Task` is a `Memory` with optional `due_date` only.
- Retrieval defaults to GraphRAG pipeline:
  - Graph candidate discovery (Kuzu) → optional vector rerank (Qdrant) → neighbor append (graph).
  - If graph returns 0: vector-only fallback, then neighbor append.
- Indexing policy (deterministic, no AI in core):
  - `note`: embed `content`.
  - `document`: embed `summary` if present else `content`.
  - `task`: embed `content` (+ `title` if present).
  - Persist `index_text` in Qdrant payload.
- YAML is optional and advisory (not required to run). Three tiny registries may exist in-repo, but core must run without them.
- CI on main must pass: lint, tests; Docker build for MCP may run but is not a blocker for core work.

### Explicit removals/cleanups (this round)
- Remove/avoid all `memory_system.*` imports in core paths.
- Remove `Project` table and model from core.
- Eliminate software-development–specific helpers from core retrieval (keep only generic graph helpers).
- No MCP edits to be considered as core progress; MCP can catch up later.

### Deliverables
- A lean `memg_core` package where:
  - Minimal models exist (`Memory`, `Entity`, `Relationship`), and `MemoryType` includes only `note|document|task` for core usage.
  - GraphRAG search is the default path; vector-only is fallback.
  - Deterministic indexing policy is enforced; `index_text` stored in payloads.
  - No references to `project` remain in core code/data paths.
  - Tests are green locally and in CI.

### Acceptance criteria
- Imports: no `memory_system.*` in core source; package imports resolve from `memg_core.*`.
- Models: no `Project` in core; `Memory` has no project fields.
- Retrieval: graph-first pipeline present; neighbor append capped by sane defaults; vector-only fallback implemented.
- Indexing: `index_text` is set per type policy and used for embeddings.
- Tests: pass locally (and on CI main) without MCP; coverage stable or improved.

### Out of scope (later rounds)
- Rich domain catalogs (technology, error/solution, boards).
- Prompt/templates/validation pipelines.
- MCP features/tooling polish and container smoke.
- YAML-driven dynamic enums/types (kept optional; can be advanced in later rounds).

### Quick checklist (go/no-go)
- [ ] Remove remaining `memory_system.*` in core imports, if any.
- [ ] Ensure no project fields/tables remain in code or payloads.
- [ ] Verify GraphRAG default and vector fallback paths run end-to-end.
- [ ] Assert `index_text` policy in add paths and visible in Qdrant payload.
- [ ] Run `pytest -q` locally; ensure CI main is green.
