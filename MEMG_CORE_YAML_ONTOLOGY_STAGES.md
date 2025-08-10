## YAML Ontology — Staged Core Plan (Graph-first)

This plan keeps the core lean, graph-first, and YAML-optional. We will include three small, generic core registries in-repo (not placeholders, not over-specific), and keep any additional examples out of core. Test-only YAML fixtures remain under `tests/fixtures/`. Legacy behaviors can be removed once green.

### Scope and principles
- **GraphRAG is core**: embedding search with optional filtering, then graph expansion with limits.
- **Single source of truth**: the YAML Registry compiles into an effective-config driving writes, storage checks, and retrieval.
- **Optional YAML (no synthetic fallbacks)**: code compiles without YAML. At runtime, we use one of the three core registries by default (configurable via env), or return clear errors when registry-dependent features are invoked without a loaded registry. We do not synthesize placeholder defaults.
- **No redundancy**: one retrieval pipeline; one write path; no duplicate codepaths.
- **Core only**: examples and integrations live in the `memg` repo later.

---

### Stage 0 — Core invariants (YAML-independent)
- **Coding tasks**
  - ID generation and storage: stable UUIDs for memories and vector points.
  - Embedding generation from anchor text (default: content) and automatic vector upsert.
  - Include filterable metadata in payload by default: `user_id`, `memory_type`, `tags`, `project_id`, `created_at`.
  - Provide direct fetch-by-id and payload-only filtering.
  - Graph neighbor access for hop/expansion.
- **Implemented**
  - Qdrant: metadata/range filters in search; `get_point(point_id)`; `filter_points(...)`.
  - Kuzu: `neighbors(node_label, node_id, rel_types, direction, limit)`.
  - Retriever: `get_memory_by_id(...)` uses Qdrant; category retrieval via `filter_points`.
- **Expected outcome**
  - Robust core works without YAML; embeddings are generated; vectors and metadata are stored; filtered vector search and graph neighbor access are available.
- **Exit criteria**
  - Add/search basic memories end-to-end; filter by tags/project/date; fetch-by-id; neighbor listing returns results.

---

### Core registries to ship (generic, minimal)
- `integration/config/core.minimal.yaml`: `note`, `document`, `task`; relations: `has_note`, `has_document`, `association`. Includes vector defaults and basic retrieval knobs.
- `integration/config/core.software_dev.yaml`: extends minimal with `bug`, `solution`; relation: `bug_solution` with `SOLVES` predicate.
- `integration/config/core.knowledge.yaml`: general-purpose `concept`, `document`, `note`; relations: `mentions`, `derived_from`, `association`.

Notes:
- These are reference registries (not placeholders). They are small, generic, and avoid overkill. Additional domain registries belong in the `memg` repo later.

---

### Stage 1 — Registry loader and effective-config
- **Coding tasks**
  - Extend `src/memory_system/utils/yaml_schema.py` to load/validate a `Registry` (versioned) and compile an effective-config:
    - Entities: `anchor_field`, `embedding_field`, `vector_dim`, `required_fields`, `enum_fields`.
    - Relations: `name`, `directed`, `predicates`, `source`, `target`, `constraints`.
    - Policies: `id_policy`, vector defaults (metric, normalize, dim), timestamps.
    - Retrieval knobs: defaults, per-relation neighbor caps, depth, direction.
  - Expose the effective-config via a cached accessor. Feature-flag via `MEMG_YAML_SCHEMA` or path argument; default to loading `integration/config/core.minimal.yaml` if not set.
  - `get_memory_schema` returns core enums plus YAML echo when loaded.
- **Tests**
  - Unit tests for: version check, anchor validity (exists and string), enum choices, vector defaults, id policy normalization.
  - Fixture YAML under `tests/fixtures/registry.v1.yaml` (minimal). Also validate the three core registries parse and compile.
- **Validation/Health**
  - `get_system_info` includes: `registry_loaded`, `version`, `id_policy`, vector defaults, retrieval knobs.
- **Expected outcome**
  - Reliable, normalized effective-config available app-wide; YAML optional and advisory.
- **Exit criteria**
  - All loader tests pass; schema echo stable; no changes to runtime behavior yet.

### Stage 2 — Storage alignment (graph-first)
- **Coding tasks**
  - Kuzu graph:
    - Map entities to node labels; relations to edge types based on registry names.
    - Light check: labels/edge types exist or can be created by the integration layer.
  - Qdrant:
    - Ensure per-entity collections with `dim`/`metric` from effective-config.
    - Startup verify; log actionable errors on mismatch.
- **Status**
  - Qdrant interface supports metadata filters, direct get, and payload-only filtering (done). Per-entity collections to be wired once registries are active.
- **Tests**
  - Mocked checks asserting collection dims/metrics derived from YAML.
  - Graph label/type mapping unit tests.
- **Validation/Health**
  - Health output includes: per-entity vector dims/metrics, and graph label/edge readiness.
- **Expected outcome**
  - Storage surfaces aligned with registry; failures are explicit and early.
- **Exit criteria**
  - Health reports consistent dims/metrics; graph label/type mapping validated.

### Stage 3 — Write-path enforcement
- **Coding tasks**
  - `integration/sync_wrapper.py`:
    - Entities: generate id per policy; timestamps; validate required fields and enum values.
    - Compute `index_text` from the entity’s `anchor_field` for all anchored types (e.g., Note, Document, Task) without embedding logic duplication; embed anchor text and upsert vector + payload (with filterable metadata).
    - Edges: enforce `source`/`target` types, allowed `predicates`, directionality, and minimal constraints (e.g., `unique_per_predicate`).
- **Tests**
  - Unit tests for enum enforcement, required field validation, id/timestamps generation, `index_text` derivation.
  - Edge tests for predicate/type/direction checks and unique-per-predicate behavior.
- **Validation/Health**
  - Health shows last enforcement results count and strictness mode (advisory vs strict).
- **Expected outcome**
  - All writes normalized and policy-compliant; `index_text` consistently set from anchor.
- **Exit criteria**
  - Write-path tests pass; end-to-end write + read sanity checks stable.

### Stage 4 — Retrieval core (GraphRAG minimal viable)
- **Coding tasks**
  - `src/memory_system/processing/memory_retriever.py`:
    - Vector search: embedding similarity on per-entity collections with optional filter predicates (current interface supports filters and fetch-by-id).
    - Graph expansion: use `neighbors(...)`; apply per-relation `max_neighbors`, direction, and depth from YAML; clamp request overrides to YAML maxima.
    - Combined pipeline: vector → expand → rank; single codepath; no duplicated implementations.
  - Expose active retrieval params via `get_system_info`.
- **Tests**
  - Unit: neighbor limit application, direction handling, clamp behavior, vector+filter query composition.
  - E2E: small fixture graph; verify: search hits, limited expansions, stable ranking contract.
- **Validation/Health**
  - Health and/or metrics report: average expansion fan-out, clamped rates, default top_k.
- **Expected outcome**
  - Deterministic GraphRAG with YAML-driven limits and filters; consistent ranking.
- **Exit criteria**
  - Retrieval tests pass; e2e demonstrates combined vector+graph behavior with limits.

### Stage 5 — Minimal graph query interface (read-only)
- **Coding tasks**
  - Safe cypher-like subset that maps to Kuzu queries; read-only; request-time limits and timeouts.
  - Whitelist entities/relations from registry; deny writes and dangerous constructs.
- **Tests**
  - Parser/validator tests for allowed patterns; execution tests on fixture graph; timeout tests.
- **Validation/Health**
  - Health indicates read-only query interface enabled and max limits.
- **Expected outcome**
  - Minimal, safe graph query surface without expanding core complexity.
- **Exit criteria**
  - Query tests pass; no write capability; limits enforced.

### Stage 6 — Health, system info, and strict mode
- **Coding tasks**
  - Startup diff: registry vs. stores (dims/metrics/labels/edges); emit warnings or errors by mode.
  - Strict mode toggle (env/flag): advisory → enforced for loader, writes, and retrieval knobs.
- **Tests**
  - Mode switching tests; ensure advisory logs vs. strict failures.
- **Validation/Health**
  - Health shows strictness, last diff summary, and first error cause when strict.
- **Expected outcome**
  - Operational clarity; easy progression from advisory to strict.
- **Exit criteria**
  - Mode behavior verified across loader/write/retrieval.

### Stage 7 — Tests and core registries
- **Coding tasks**
  - Keep test fixtures minimal and synthetic under `tests/fixtures/`.
  - Maintain the three core registries under `integration/config/`. Additional examples will live in the `memg` repo.
- **Tests**
  - Ensure coverage for: loader, write path, retrieval, graph query subset, health.
- **Validation/Health**
  - CI/`pytest -q` green locally; consistent outputs in `get_system_info`.
- **Expected outcome**
  - High-signal tests without polluting core with examples.
- **Exit criteria**
  - All tests green; only the three core registries present in core; no additional example types.

### Stage 8 — Cleanup and de-duplication
- **Coding tasks**
  - Remove legacy hardcoded behaviors superseded by registry-driven logic (e.g., ad-hoc `index_text` routing, retrieval defaults not sourced from YAML).
  - Ensure single retrieval pipeline and single write path remain.
- **Tests**
  - Back-compat not required; ensure green after removal.
- **Validation/Health**
  - Health free of deprecation warnings.
- **Expected outcome**
  - Lean core, one clear implementation path.
- **Exit criteria**
  - No dead code; tests green; docs updated.

### Stage 9 — Docs and handoff to `memg` repo
- **Coding tasks**
  - Document extension points and boundaries (what belongs in core vs. memg repo).
  - Provide guidance for building example registries and integrations in `memg`.
- **Tests**
  - None beyond docs links validity if applicable.
- **Validation/Health**
  - N/A.
- **Expected outcome**
  - Clear path for scaling examples/integrations outside core.
- **Exit criteria**
  - Docs merged; consumers can proceed in `memg`.

---

### Milestone acceptance for “core-first” (graph build + retrieval)
- Stages 1–4 complete; 5 optional; 6 advisory mode acceptable initially.
- End-to-end: write entities/edges → vector search + graph expansion → results ranked.
- YAML off: defaults work; YAML on: enforcement and limits applied.
