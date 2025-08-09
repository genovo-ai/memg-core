## MEMG Core — Proposed Minimal Flows and Types (for review)

### Purpose
Define a lean, graph-first core that is free from software_development domain baggage. Keep only the minimal, broadly useful primitives and flows. This document is a proposal for us to evaluate together before any code changes.

---

## Core Principles
- Graph is first-class (Kuzu) with vector search as a complement (Qdrant), not the other way around.
- Minimal types only; avoid domain-specific catalogs (e.g., TECHNOLOGY, COMPONENT, ERROR).
- Small, friendly public API for adding and searching memories.
- No templates, prompts, complex processors, or enterprise/task-board semantics in core.

---

## Proposed Minimal Types

### MemoryType
- NOTE
- DOCUMENT
- TASK

Notes:
- Remove CONVERSATION from core.

### TaskStatus (simple todo list)
- todo
- done

Notes:
- Optional `due_date` allowed.
- No priorities, story points, sprint/board concepts in core.

### Entity (generic)
- Keep `name: str` and `type: str` but avoid enforcing a domain enum in core.
- Encourage generic usage (e.g., "concept", "topic", or free-form) in core docs.

Notes:
- Extras can reintroduce domain catalogs (technology, component, error, etc.).

### RelationshipType (minimal)
- RELATES_TO
- MENTIONED_IN (optional)

Notes:
- Remove RelationshipStrength and other non-essential enums from core.

---

## Proposed Minimal Models (shape)

- Memory
  - id, user_id, content, memory_type
  - title?, tags?, created_at
  - (Optional) due_date only when `memory_type == TASK`

- Entity
  - id, user_id, name, type (free-form string in core)

- Relationship
  - source_id, target_id, relationship_type

Notes:
- No `Project` in core.
- No task board or software_development fields.

---

## Proposed Public API (core)

High-level functions (sync or async wrappers) that map to current interfaces:

- add_note(text, user_id, title? = None, tags? = []) -> Memory
- add_document(text, user_id, title? = None, tags? = []) -> Memory
- add_task(text, user_id, due_date? = None) -> Memory  (TASK)
- complete_task(task_id, user_id) -> Memory  (mark status = done)
- search(query, user_id? = None, limit = 20) -> list[SearchResult]
- graph_search(entity_name, types? = None, user_id? = None, limit = 20) -> list[SearchResult]

Notes:
- `graph_search` is generic; no specialized software_development helpers in core.
- Implementations should remain thin wrappers around existing storage/retrieval.

---

## Retrieval Flows (kept minimal)

1) Vector search (Qdrant)
- Embed query -> filter by user_id (optional) -> search points -> map to results.

2) Graph search (Kuzu)
- Generic pattern: MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
  - Filter by entity name substring (case-insensitive)
  - Optional type constraints via `types?` parameter (strings)
  - Return mapped `SearchResult` objects

Notes:
- Keep both flows; expose both through public API.
- No software_development-specific entity type lists in core.

---

## Configuration (essentials only)
- Qdrant connection settings
- Kuzu database path
- Embedding provider settings (env-based)
- Basic thresholds (score, limits)

Notes:
- Avoid template/prompt/validation knobs in core config.

---

## Out of Scope (for extras)
- Software development domain types and flows (technology, component, error/solution, project, boards)
- Templates and dynamic schema generation
- Validation layers and complex processors
- Task board semantics (priority, story points, epics, sprints)

---

## Test Strategy (to reach ≥70% then 80%)
- Unit tests for public API functions (add_note/add_document/add_task/complete_task/search/graph_search).
- Focused tests for `memory_retriever` branches.
- Light mocks for `kuzu_graph/interface.py` and `qdrant/interface.py`.
- Embedding fallback tests (`utils/genai.py`).

---

## Open Questions (for review)
1) Entity `type`: free-form string vs. small generic enum (e.g., {"concept"})? Proposal: free-form in core.
2) Keep `MENTIONED_IN` or rely only on `RELATES_TO`? Proposal: keep both, still minimal.
3) Do we support `due_date` for TASK in core or keep tasks purely status-based? Proposal: allow `due_date` as the single optional field.
4) Should `search` merge vector and graph results, or return them separately? Proposal: keep them separate for clarity (search vs graph_search).

---

## Review Checklist
- Does this keep graph as a first-class citizen (not vector-only)?
- Are core types minimal and domain-agnostic?
- Is the public API small, friendly, and stable?
- Does configuration remain lean?
- Are all software_development-specific items excluded from core?
