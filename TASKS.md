# MEMG Core – Prioritized Task Backlog (Jira-style)

Note: Before executing, pull latest changes and re-run lint/tests to incorporate any incoming fixes from recent commits.

## P0 – Critical

- [MEMG-1] Remove all mem0 references and fix config usage
  - Priority: P0 / Critical
  - Description: Replace any mentions of MEM0 with MEMG. In code, fix `config.mem0` usage to `config.memg` in `MemoryRetriever._should_filter_invalid_memories()`. Update docstrings that say "MEM0-style" to neutral wording.
  - Acceptance Criteria:
    - No textual references to "mem0" in repo (code/docs).
    - `MemoryRetriever._should_filter_invalid_memories()` uses `config.memg.enable_temporal_reasoning`.
  - Labels: bug, config, cleanup

- [MEMG-2] Ensure graph_search is present in released memg-core and MCP image
  - Priority: P0 / Critical
  - Description: Publish updated `memg-core` containing `MemoryRetriever.graph_search`. Bump integration `memg-core` dependency and MCP Docker image to that version to remove "no attribute graph_search" errors in clients.
  - Acceptance Criteria:
    - `pip install memg-core==<new>` exposes `graph_search`.
    - MCP container returns results for `graph_search` tool (no attribute errors).
  - Labels: release, mcp, search, graph

- [MEMG-3] Fix Qdrant add_point return handling and Unified processor response type
  - Priority: P0 / Critical
  - Description: `add_point` returns `(bool, point_id)`. Unpack and check the boolean. In `UnifiedMemoryProcessor.process_memory`, return `final_type` as `MemoryType` (enum) not string.
  - Acceptance Criteria:
    - No type errors in `ProcessingResponse.final_type`.
    - Proper error handling if Qdrant upsert fails.
  - Labels: bug, storage, types

- [MEMG-4] Implement created_at range filter for days_back in QdrantInterface
  - Priority: P0 / Critical
  - Description: Replace equality filter on `created_at` with `Range(gte=timestamp)` using Qdrant filter API.
  - Acceptance Criteria:
    - `search_memories` with `days_back` returns time-scoped results appropriately.
  - Labels: search, db, bug

## P1 – High

- [MEMG-5] Fix GraphValidator to use uppercase entity types
  - Priority: P1 / High
  - Description: Validator queries currently use lowercase types (e.g., 'technology'). Update to uppercase string values (e.g., 'TECHNOLOGY').
  - Acceptance Criteria:
    - `validate_graph` reports non-zero counts after extractions.
  - Labels: validation, graph

- [MEMG-6] Align aliasing in graph search conversion
  - Priority: P1 / High
  - Description: Kuzu query aliases `e.confidence as entity_confidence` but converter reads `"e.confidence"`. Use the alias in conversion or standardize on a consistent key.
  - Acceptance Criteria:
    - Confidence values populate `SearchResult.score` from graph.
  - Labels: graph, search

- [MEMG-7] Remove category-based filter using non-existent field
  - Priority: P1 / High
  - Description: `get_memories_by_category` checks `result.memory.category` which is not in `Memory`. Replace with tags/entity-based filtering or remove method.
  - Acceptance Criteria:
    - No attribute errors; method either removed or implemented with supported fields.
  - Labels: api, cleanup

- [MEMG-8] Standardize port to 8787 across code and docs
  - Priority: P1 / High
  - Description: Ensure README(s), Docker, scripts, and examples consistently use 8787 (or update everything to 8788, but be consistent).
  - Acceptance Criteria:
    - All docs and health endpoints reference the same port; health checks pass.
  - Labels: docs, devops

- [MEMG-9] Add required env vars to env.example and docs
  - Priority: P1 / High
  - Description: Add `QDRANT_STORAGE_PATH` and `KUZU_DB_PATH` (required by interfaces) to `env.example` and README.
  - Acceptance Criteria:
    - Local runs do not crash due to missing storage envs.
  - Labels: docs, config

- [MEMG-10] Align FastMCP versions across core, integration, and Dockerfile
  - Priority: P1 / High
  - Description: Core uses `fastmcp>=2.10.x` while Dockerfile/integration target `>=0.2.0`. Align to the validated version.
  - Acceptance Criteria:
    - MCP starts reliably; CI green on MCP-related tests.
  - Labels: devops, dependencies

- [MEMG-11] Packaging/versioning: single source of truth
  - Priority: P1 / High
  - Description: `pyproject.toml` version (1.0.0) differs from `src/memory_system/version.py` (0.1.0). Adopt setuptools_scm or derive from a single file.
  - Acceptance Criteria:
    - `__version__` matches published package version; CI sanity check added.
  - Labels: packaging, release

- [MEMG-12] Fix tests referencing non-existent modules/tools
  - Priority: P1 / High
  - Description: Update tests that import `memory_system.mcp_server` (server resides under `integration/mcp/`). Remove/gate tests referencing `scripts.migrate_entity_types` or unexposed tools.
  - Acceptance Criteria:
    - `pytest -q` runs without import errors; non-applicable tests skipped or updated.
  - Labels: tests, stability

## P2 – Medium

- [MEMG-13] Align Qdrant collection default to env/docs
  - Priority: P2 / Medium
  - Description: Default collection is `memory_collection` in code; env/docs use `memories`. Use `memories` everywhere for consistency.
  - Acceptance Criteria:
    - New deployments use `memories` by default unless overridden.
  - Labels: db, consistency

- [MEMG-14] Consolidate embedding dimension env variables
  - Priority: P2 / Medium
  - Description: Use one variable (`MEMG_VECTOR_DIMENSION`) and remove `EMBEDDING_DIMENSION_LEN`.
  - Acceptance Criteria:
    - Single source of truth for vector dimension; reflected in code and docs.
  - Labels: config, cleanup

- [MEMG-15] Expose optional retriever methods as MCP tools or fix docs
  - Priority: P2 / Medium
  - Description: Either expose `search_by_technology`, `search_by_component`, `find_error_solutions` as tools, or update docs/tests to only reference the 6 core tools.
  - Acceptance Criteria:
    - Tool surface matches documentation/tests.
  - Labels: api, docs

- [MEMG-16] Docker Compose: use `.env` instead of `env.example`
  - Priority: P2 / Medium
  - Description: `dockerfiles/docker-compose.yml` points to `../env.example`. Switch to `../.env` to pick up real secrets.
  - Acceptance Criteria:
    - Compose uses user-configured `.env`; quickstart works end-to-end.
  - Labels: devops

- [MEMG-17] Documentation polish (root & integration READMEs)
  - Priority: P2 / Medium
  - Description: Unify image names, add required envs, correct run commands, include SyncMemorySystem example, template notes.
  - Acceptance Criteria:
    - Docs are consistent and newcomer-friendly; quickstart verified.
  - Labels: docs

- [MEMG-18] Template vs enum alignment (or update test expectations)
  - Priority: P2 / Medium
  - Description: Default template entity set vs `EntityType` enum/test expectations diverge. Decide on canonical set or adjust tests to allow template-based variance.
  - Acceptance Criteria:
    - Tests pass consistently with chosen approach.
  - Labels: templates, tests

- [MEMG-19] Lint/typing configuration alignment
  - Priority: P2 / Medium
  - Description: MyPy targets py310 while project requires 3.11+; numerous Pylint E1101 on Pydantic fields. Adjust configs or per-file suppressions.
  - Acceptance Criteria:
    - CI quality gates stable; minimal false positives.
  - Labels: ci, lint, types

## P3 – Low

- [MEMG-20] Add Qdrant `get_point`/`update_point` helpers
  - Priority: P3 / Low
  - Description: For `invalidate_memory` and future updates, add helpers to fetch/update a point payload cleanly.
  - Acceptance Criteria:
    - Round-trip update of memory validity flag possible through interface.
  - Labels: db, enhancement

- [MEMG-21] CONTRIBUTING.md with test/publish instructions
  - Priority: P3 / Low
  - Description: Add contributor guide covering local runs (mock GenAI), running CI suite, release process, and MCP image build.
  - Acceptance Criteria:
    - Contributors can onboard without support pings.
  - Labels: docs, community

- [MEMG-22] Replace "MEM0-style" verbiage in docstrings
  - Priority: P3 / Low
  - Description: Use neutral language (e.g., "conversation message-pair style") in `conversation_context` and related modules.
  - Acceptance Criteria:
    - Docstrings mention MEMG or neutral phrasing only.
  - Labels: cleanup, docs

- [MEMG-23] Workflow sanity & artifact improvements
  - Priority: P3 / Low
  - Description: Review `.github/workflows/workflow.yml`:
    - Confirm publish-to-pypi precedes MCP image build (ok).
    - Add step to ensure MCP image uses the just-published memg-core tag.
    - Consider gates (fail CI on ruff/pylint) per release branch policy.
  - Acceptance Criteria:
    - MCP image verified to include latest `memg-core` at build time.
  - Labels: ci, devops

- [MEMG-24] Remove stale `lint.log` or regenerate during CI
  - Priority: P3 / Low
  - Description: `lint.log` appears stale and can confuse contributors.
  - Acceptance Criteria:
    - Either removed from repo or generated dynamically in CI artifacts.
  - Labels: cleanup, ci

---

## Preparation checklist (do first)
- [ ] Pull latest commits from `main`/`dev` and rerun: ruff, pylint, mypy, pytest.
- [ ] Verify whether any of the P0/P1 issues have already been addressed upstream.
- [ ] Confirm port standard (8787) and env variable policy team-wide.
- [ ] Align MCP image build to depend on the just-published `memg-core` version.
