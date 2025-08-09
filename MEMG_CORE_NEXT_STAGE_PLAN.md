## MEMG Core — Next Stage Plan (Branch: dev-slim)

### Context
- Track remains on: `dev-slim`
- `memg-extras` is parked for now (no new work there)
- Core is lean, tests pass (39 pass, 6 skip), coverage ~52%
- Minimal CI active (Docker MCP build enabled; PyPI publishing disabled)

---

## Objectives (next 1–2 cycles)
- Finalize a minimal, friendly core API (store/search) without re-introducing weight
- Raise coverage toward 80% with focused, core-only tests
- Achieve type-clean state (pyright = 0)
- Tighten CI thresholds incrementally and validate Docker pipeline end-to-end
- Provide clear documentation and migration guidance

---

## Stage 1: Minimal Core API + Docs
- Goals:
  - Define a tiny public API surface for common operations without adding non-core features:
    - add_note(text, user_id, tags?, title?)
    - add_document(text, user_id, tags?, title?)
    - search(query, user_id?, limit?)
  - Update `README.md` with simplified examples (no templates/prompts/pipelines)
  - Author `MIGRATION.md` to explain what moved out of core and suggested paths forward

- Deliverables:
  - Public API section in README with 3 short examples
  - `MIGRATION.md` listing removed features and pointers
  - Unit tests covering the public API paths

- Acceptance Criteria:
  - API imports are stable and work in a clean venv
  - README examples run as-is
  - Tests green locally and in CI

- Estimate: 5–7 SP

---

## Stage 2: Coverage + Type-Safety
- Goals:
  - Increase coverage from ~52% → ≥70% this stage (target 80% in the next)
  - Add tests for:
    - `processing/memory_retriever.py` edge cases and branches
    - `qdrant/interface.py` and `kuzu_graph/interface.py` happy-paths with light mocks
    - `utils/genai.py` graceful fallbacks
  - Run `pyright` and drive type errors to 0

- Deliverables:
  - Added unit tests focusing on core paths
  - `pyright` included in dev workflow (local and CI informational step)

- Acceptance Criteria:
  - Coverage ≥70% (report verified in CI)
  - `pyright` shows 0 errors on src/

- Estimate: 6–8 SP

---

## Stage 3: CI Hardening + Release Readiness (lean)
- Goals:
  - CI: raise coverage threshold (50% → 70% → 80% over time)
  - Add Python matrix (3.11, 3.12) for core tests
  - Keep PyPI publishing disabled; ensure MCP Docker build/push succeeds on branch
  - Add a basic smoke test job that builds and runs the MCP container `/health`

- Deliverables:
  - Updated workflow with matrix and staged coverage thresholds
  - Lightweight container smoke check step

- Acceptance Criteria:
  - CI is fully green on `dev-slim`
  - MCP image builds consistently; health endpoint smoke passes

- Estimate: 4–6 SP

---

## Stage 4: Documentation Polish + Developer Experience
- Goals:
  - Ensure `README.md` is aligned with the lean core (only minimal features)
  - Provide quickstart and troubleshooting sections (env vars, data dirs)
  - Add concise design notes on “what belongs in core vs. extras”

- Deliverables:
  - Updated README (quickstart, API, examples, constraints)
  - `DESIGN_NOTES.md` (optional) with core principles

- Acceptance Criteria:
  - Docs are self-sufficient for a new user to add/search memories

- Estimate: 2–3 SP

---

## Parallelization Guide
- In parallel:
  - Stage 1 API + README can proceed alongside Stage 2 tests (as long as APIs are stable)
  - Stage 2 tests can be split by component (retriever, qdrant, kuzu, genai)
  - Stage 3 CI hardening can be developed in a separate PR and merged once tests stabilize

---

## Risk & Guardrails
- Avoid re-introducing templates/pipelines/validation into core
- Keep dependencies minimal; avoid heavy optional extras in core
- Maintain consistent lint/format via ruff and pre-commit
- Increment coverage thresholds gradually to avoid blocking PR flow

---

## Tracking & PR Suggestions (to `dev-slim`)
- PR S1-A: Minimal public API endpoints + README examples
- PR S2-A: Tests for retriever branches; S2-B: qdrant + kuzu interface unit tests
- PR S2-C: genai fallback tests; introduce `pyright` check (non-blocking initially)
- PR S3-A: CI matrix + increase coverage threshold to 70% (later to 80%)
- PR S3-B: Container smoke test job for MCP image
- PR S4-A: Documentation polish pass (README, optional DESIGN_NOTES)

---

## Current Baseline
- Tests: 39 passed, 6 skipped
- Coverage: ~52%
- CI: Minimal; Docker MCP build enabled; PyPI disabled
- Lint: pre-commit with ruff (format + lint); black/isort not required
