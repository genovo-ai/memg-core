## MEMG Core — Counter Offer (GraphRAG-first, Minimal Core)

### Premise & Non‑Negotiables
- Graph is first-class: search defaults to GraphRAG (graph candidates → optional vector rerank → neighbor append).
- Keep branch: `dev-slim`. No extras work in this cycle.
- Software-development domain lives outside core. Current strict enums can remain for this iteration; we will slim next.

---

## Minimal Types (Now) and Near-Term Slimming
- MemoryType: NOTE, DOCUMENT, TASK (CONVERSATION out of core).
- TaskStatus (core): {todo, done}. Optional `due_date`. No priorities/story points.
- RelationshipType (core): {RELATES_TO, MENTIONED_IN}. No strength/importance enums.
- EntityType:
  - Keep current enum this iteration (to avoid churn and keep demos/tests stable).
  - Document SD-flavored values as provisional; plan to move to extras and/or allow free-form type in next iteration.

---

## Deterministic Indexing & Display Policy (Per Type)
- NOTE
  - index_text (embed): `content`
  - display (primary): `content`
  - display (appendix): `content` (trim if very long)
- DOCUMENT
  - index_text (embed): `summary` if present; else `content`
  - display (primary landed): full `content`
  - display (appendix): `summary` + `id` (no full content)
- TASK
  - index_text (embed): `content` (+ title if present)
  - display (primary): `content` (+ `due_date` if set)
  - display (appendix): `content` (trim if long)

Notes:
- Store `index_text` explicitly in Qdrant payload for reproducibility.
- Keep `summary` in payload when available; for notes, summary may be first N chars (no AI in core).

---

## Search Pipeline (Default = GraphRAG)
1) Graph candidate discovery (Kuzu)
   - MATCH (m:Memory)-[:MENTIONS]->(e:Entity) WHERE e.name ILIKE query
   - Optional filters: `user_id`, `days_back` (created_at cutoff), `tags`, `entity_types`
   - 0–1 hop expansion for neighborhood context if needed
2) Optional vector rerank (Qdrant)
   - Embed candidates’ index_text and query; rerank top-K for tie-breaking only
3) Neighbor append (Kuzu)
   - For each top result, find memories sharing entities (MENTIONS) with the seed memory
   - Append up to: notes_limit (e.g., 5) as full text; docs_limit (e.g., 3) as summary + id
   - Always apply `user_id` filter; dedupe by memory id; ignore cycles for now
4) Fallback
   - If graph returns 0 candidates: vector search (Qdrant) → neighbor append via graph

API shape (intent):
- `search(query, user_id?, limit?, filters?)` → GraphRAG by default
- `graph_search(query, entity_types?, user_id?, limit?)` → low-level primitive (already exists)
- Optional internal `search_vector(...)` not exposed publicly

---

## Listing & Filtering (Graph-Native)
- `list_memories_by_type(memory_type, after_date?, user_id?)` via Kuzu
- `list_tasks(after_date?, user_id?)` thin wrapper over the above (where memory_type='TASK')
- Similar helpers for notes/docs if needed

---

## IDs & Fetch Semantics
- Expose both `memory_id` and `entity_id` in responses.
- Allow downstream agents to fetch by id; core may later offer `fetch_by_id(kind, id)` as a thin helper.

---

## YAML Types & Strategy (Feature-Flagged, Next Iteration)
- Keep core static defaults now. Add optional YAML loader later (feature flag) to define:
  - entity/relationship catalogs (or aliases),
  - indexing/display policy per type,
  - retrieval pipeline knobs (graph-first, rerank, neighbor limits).
- Default YAML stays domain-agnostic; memg (full) can supply SD catalogs separately.

---

## CI, Tests, and Quality
- Tests cover graph paths (not vector-only). Container smoke should include graph init.
- Coverage path: ~52% → 70% → 80%.
- Type safety target: `pyright = 0` in Stage 2.

---

## Stepwise Rollout
Stage A (now):
- Document indexing/display policy in repo.
- Keep GraphRAG as default pipeline (call graph first; rerank optional; append neighbors).
- Add listing helpers (by type/date).

Stage B:
- Add tests for neighbor append and listing flows; raise coverage to ≥70%.
- Run `pyright` and fix to 0 errors.

Stage C (optional):
- Introduce YAML types/strategy loader behind feature flag; memg provides richer YAML in its repo.

---

## Acceptance Criteria
- `search` is GraphRAG by default; returns primary results + appendices per policy.
- Listing helpers work with user/date filters via Kuzu.
- Graph remains mandatory; vector-only is fallback.
- Minimal types honored; SD domain is not required in core.

---

## Example Response (abbreviated)
```
{
  "results": [
    {
      "memory": {"id": "m1", "type": "NOTE", "content": "..."},
      "score": 0.83,
      "appendix": {
        "notes": [{"id": "n2", "content": "..."}],
        "docs":  [{"id": "d3", "title": "...", "summary": "..."}]
      }
    },
    {
      "memory": {"id": "d5", "type": "DOCUMENT", "content": "full content (landed)"},
      "score": 0.79,
      "appendix": {
        "notes": [{"id": "n6", "content": "..."}],
        "docs":  [{"id": "d7", "title": "...", "summary": "..."}]
      }
    }
  ]
}
```
