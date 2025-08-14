# memg_core/core/pipeline/retrieval.py
"""Unified retrieval pipeline with automatic mode selection and neighbor expansion.
- Anchor-first: uses `statement` as the only textual anchor.
- Modes: vector-first (Qdrant), graph-first (Kuzu), hybrid (merge).
- Filters: user_id, memo_type, modified_within_days, arbitrary filters.
- Deterministic ordering: score DESC, then hrid index ASC, then id ASC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from ...utils.hrid import hrid_to_index  # NEW
from ..exceptions import DatabaseError
from ..interfaces.embedder import Embedder
from ..interfaces.kuzu import KuzuInterface
from ..interfaces.qdrant import QdrantInterface
from ..models import Memory, SearchResult

# ----------------------------- helpers ---------------------------------


# NEW: deterministic field projection for payloads
def _project_payload(
    memory_type: str,
    payload: dict[str, Any] | None,
    *,
    include_details: str,
    projection: dict[str, list[str]] | None,
) -> dict[str, Any]:
    """
    Returns a pruned payload based on include_details and optional projection mapping.

    Policy (v1):
      - include_details="none": anchors only → keep just "statement" if present.
      - include_details="self": anchors + optional projection for anchors; always keep "statement" if present.
      - include_details other values are reserved for future; treated like "self".
      - Neighbors remain anchors-only regardless (we don't hydrate neighbor details in v1).
    """
    payload = dict(payload or {})
    if not payload:
        return {}

    # Always prefer having "statement" present if it exists
    has_stmt = "statement" in payload

    if include_details == "none":
        return {"statement": payload["statement"]} if has_stmt else {}

    # self / default behavior with optional projection
    allowed: set[str] | None = None
    if projection:
        allowed = set(projection.get(memory_type, []))
        # Always include statement when present
        if has_stmt:
            allowed.add("statement")

    if allowed is None:
        # No projection → return as-is
        return payload

    # With projection → prune to allowed keys
    return {k: v for k, v in payload.items() if k in allowed}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str:
    return (dt or _now()).isoformat()


def _cutoff(days: int | None) -> datetime | None:
    if days is None or days <= 0:
        return None
    return _now() - timedelta(days=days)


def _parse_datetime(date_str: Any) -> datetime:
    if isinstance(date_str, str):
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return _now()
    return _now()


def _sort_key(r: SearchResult) -> tuple:
    """Stable ordering: score DESC, then hrid index ASC, then id ASC."""
    mem = r.memory
    try:
        idx = hrid_to_index(getattr(mem, "hrid", "") or "ZZZ_ZZZ999")
    except Exception:
        idx = 26**3 * 1000 + 999  # worst case
    return (-float(r.score or 0.0), idx, mem.id or "")


# ----------------------------- Kuzu ------------------------------------


def _build_graph_query_for_memos(
    query: str | None,
    *,
    user_id: str | None,
    limit: int,
    relation_names: list[str] | None = None,
    memo_type: str | None = None,
    modified_within_days: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Graph-first: fetch Memo nodes by filters (no Entity matching).
    Returns m.* fields only; neighbors will be fetched separately.
    """
    params: dict[str, Any] = {"limit": limit}

    cypher = "MATCH (m:Memory)\nWHERE 1=1"
    if user_id:
        cypher += " AND m.user_id = $user_id"
        params["user_id"] = user_id
    if memo_type:
        cypher += " AND m.memory_type = $memo_type"
        params["memo_type"] = memo_type
    cut = _cutoff(modified_within_days)
    if cut is not None:
        cypher += " AND m.created_at >= $cutoff"
        params["cutoff"] = _iso(cut)

    cypher += (
        "\nRETURN DISTINCT "
        "m.id, m.user_id, m.memory_type, m.hrid, m.statement, m.tags, m.created_at, m.updated_at\n"
        "ORDER BY coalesce(m.updated_at, m.created_at) DESC\n"
        "LIMIT $limit"
    )
    return cypher, params


def _rows_to_memories(rows: list[dict[str, Any]]) -> list[Memory]:
    out: list[Memory] = []
    for row in rows:
        mtype = row.get("m.memory_type") or row.get("memory_type") or "memo"
        statement = row.get("m.statement") or row.get("statement") or ""
        created_at_raw = row.get("m.created_at") or row.get("created_at")
        # updated_at_raw = row.get("m.updated_at") or row.get("updated_at")
        tags_raw = row.get("m.tags") or row.get("tags") or []
        hrid = row.get("m.hrid") or row.get("hrid")  # NEW

        if isinstance(tags_raw, str):
            tags = [t for t in tags_raw.split(",") if t]
        else:
            tags = list(tags_raw)

        out.append(
            Memory(
                id=row.get("m.id") or row.get("id") or str(uuid4()),
                user_id=row.get("m.user_id") or row.get("user_id", ""),
                memory_type=mtype,
                payload={"statement": statement},
                tags=tags,
                confidence=0.8,
                is_valid=True,
                created_at=_parse_datetime(created_at_raw),
                supersedes=None,
                superseded_by=None,
                vector=None,
                hrid=hrid,
            )
        )
    return out


# ----------------------------- Qdrant ----------------------------------


def _qdrant_filters(
    user_id: str | None,
    memo_type: str | None,
    modified_within_days: int | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any]:
    f: dict[str, Any] = extra.copy() if extra else {}
    if user_id:
        f["core.user_id"] = user_id
    if memo_type:
        f["core.memory_type"] = memo_type
    cut = _cutoff(modified_within_days)
    if cut is not None:
        f["core.updated_at_from"] = _iso(cut)  # adapter layer should translate to a proper Range
    return f


# ----------------------------- Rerank/Neighbors ------------------------


def _rerank_with_vectors(
    query: str, candidates: list[Memory], qdrant: QdrantInterface, embedder: Embedder
) -> list[SearchResult]:
    qvec = embedder.get_embedding(query)
    vec_results = qdrant.search_points(vector=qvec, limit=max(10, len(candidates)))
    score_by_id = {r.get("id"): float(r.get("score", 0.0)) for r in vec_results}

    results: list[SearchResult] = []
    for mem in candidates:
        score = score_by_id.get(mem.id, 0.5)
        results.append(
            SearchResult(memory=mem, score=score, distance=None, source="graph_rerank", metadata={})
        )
    results.sort(key=_sort_key)
    return results


def _append_neighbors(
    seeds: list[SearchResult],
    kuzu: KuzuInterface,
    neighbor_limit: int,
    relation_names: list[str] | None,
) -> list[SearchResult]:
    expanded: list[SearchResult] = []
    # NEW: default whitelist used if none provided (anchors-only neighbors)
    rels = relation_names or ["RELATED_TO", "HAS_DOCUMENT", "REQUIRES"]

    for seed in seeds[: min(5, len(seeds))]:
        mem = seed.memory
        if not mem.id:
            continue
        rows = kuzu.neighbors(
            node_label="Memory",
            node_id=mem.id,
            rel_types=rels,
            direction="any",
            limit=neighbor_limit,
            neighbor_label="Memory",
        )
        for row in rows:
            statement = row.get("statement", "")
            neighbor = Memory(
                id=row.get("id") or str(uuid4()),
                user_id=row.get("user_id", ""),
                memory_type=row.get("memory_type", "memo"),
                payload={"statement": statement},
                confidence=0.8,
                is_valid=True,
                created_at=_parse_datetime(row.get("created_at")),
                supersedes=None,
                superseded_by=None,
                vector=None,
                tags=[],
                hrid=row.get("hrid"),  # NEW: if present
            )
            expanded.append(
                SearchResult(
                    memory=neighbor,
                    score=max(0.3, seed.score * 0.9),
                    distance=None,
                    source="graph_neighbor",
                    metadata={"from": mem.id},
                )
            )

    # merge by id keep max score
    by_id: dict[str, SearchResult] = {r.memory.id: r for r in seeds}
    for r in expanded:
        cur = by_id.get(r.memory.id)
        if cur is None or r.score > cur.score:
            by_id[r.memory.id] = r
    out = list(by_id.values())
    out.sort(key=_sort_key)
    return out


# ----------------------------- Entry Point -----------------------------


def graph_rag_search(
    query: str | None,
    user_id: str,
    limit: int,
    qdrant: QdrantInterface,
    kuzu: KuzuInterface,
    embedder: Embedder,
    filters: dict[str, Any] | None = None,
    relation_names: list[str] | None = None,
    neighbor_cap: int = 5,
    *,
    memo_type: str | None = None,
    modified_within_days: int | None = None,
    mode: str | None = None,  # 'vector' | 'graph' | 'hybrid'
    include_details: str = "none",  # NEW: "none" | "self" (neighbors remain anchors-only in v1)
    projection: dict[str, list[str]] | None = None,  # NEW: per-type field allow-list
) -> list[SearchResult]:
    """Unified retrieval with automatic mode selection.

    - If `query` is provided → vector-first.
    - If no `query` but `memo_type/filters/date` are provided → graph-first.
    - If both and `mode='hybrid'` → merge by id with stable ordering.
    """
    # ---------------- validation ----------------
    has_query = bool(query and query.strip())
    has_scope = bool(memo_type or (filters and len(filters) > 0) or modified_within_days)
    if not has_query and not has_scope:
        return []

    # decide mode
    eff_mode = mode or ("vector" if has_query else "graph")

    results: list[SearchResult] = []

    try:
        if eff_mode == "graph":
            cypher, params = _build_graph_query_for_memos(
                query,
                user_id=user_id,
                limit=limit,
                relation_names=relation_names,
                memo_type=memo_type,
                modified_within_days=modified_within_days,
            )
            rows = kuzu.query(cypher, params)
            candidates = _rows_to_memories(rows)
            if has_query and candidates:
                results = _rerank_with_vectors(query or "", candidates, qdrant, embedder)
            else:
                # score-less anchors with projection
                proj = []
                for m in candidates:
                    m.payload = _project_payload(
                        m.memory_type,
                        m.payload,
                        include_details=include_details,
                        projection=projection,
                    )
                    proj.append(
                        SearchResult(
                            memory=m, score=0.5, distance=None, source="graph", metadata={}
                        )
                    )
                results = proj
        elif eff_mode == "vector":
            qf = _qdrant_filters(user_id, memo_type, modified_within_days, filters)
            qvec = embedder.get_embedding(query or "")
            vec = qdrant.search_points(vector=qvec, limit=limit, user_id=user_id, filters=qf)
            for r in vec:
                payload = r.get("payload", {})
                core = payload.get("core", {})
                entity = payload.get("entity", {})
                statement = entity.get("statement") or core.get("statement") or ""
                m = Memory(
                    id=r.get("id") or str(uuid4()),
                    user_id=core.get("user_id", ""),
                    memory_type=core.get("memory_type", "memo"),
                    payload={
                        "statement": statement,
                        **{k: v for k, v in entity.items() if k != "statement"},
                    },
                    tags=core.get("tags", []),
                    confidence=core.get("confidence", 0.8),
                    is_valid=core.get("is_valid", True),
                    created_at=_parse_datetime(core.get("created_at")),
                    supersedes=core.get("supersedes"),
                    superseded_by=core.get("superseded_by"),
                    vector=None,
                    hrid=core.get("hrid"),  # NEW
                )
                # NEW: project anchor payload according to include_details/projection
                m.payload = _project_payload(
                    m.memory_type, m.payload, include_details=include_details, projection=projection
                )
                results.append(
                    SearchResult(
                        memory=m,
                        score=float(r.get("score", 0.0)),
                        distance=None,
                        source="qdrant",
                        metadata={},
                    )
                )
        else:  # hybrid
            cypher, params = _build_graph_query_for_memos(
                query,
                user_id=user_id,
                limit=limit,
                relation_names=relation_names,
                memo_type=memo_type,
                modified_within_days=modified_within_days,
            )
            rows = kuzu.query(cypher, params)
            candidates = _rows_to_memories(rows)
            qf = _qdrant_filters(user_id, memo_type, modified_within_days, filters)
            qvec = embedder.get_embedding(query or "")
            vec = qdrant.search_points(vector=qvec, limit=limit, user_id=user_id, filters=qf)

            vec_mems: list[SearchResult] = []
            for r in vec:
                payload = r.get("payload", {})
                core = payload.get("core", {})
                entity = payload.get("entity", {})
                statement = entity.get("statement") or core.get("statement") or ""
                m = Memory(
                    id=r.get("id") or str(uuid4()),
                    user_id=core.get("user_id", ""),
                    memory_type=core.get("memory_type", "memo"),
                    payload={
                        "statement": statement,
                        **{k: v for k, v in entity.items() if k != "statement"},
                    },
                    tags=core.get("tags", []),
                    confidence=core.get("confidence", 0.8),
                    is_valid=core.get("is_valid", True),
                    created_at=_parse_datetime(core.get("created_at")),
                    supersedes=core.get("supersedes"),
                    superseded_by=core.get("superseded_by"),
                    vector=None,
                    hrid=core.get("hrid"),  # NEW
                )
                m.payload = _project_payload(
                    m.memory_type, m.payload, include_details=include_details, projection=projection
                )
                vec_mems.append(
                    SearchResult(
                        memory=m,
                        score=float(r.get("score", 0.0)),
                        distance=None,
                        source="qdrant",
                        metadata={},
                    )
                )

            by_id: dict[str, SearchResult] = {r.memory.id: r for r in vec_mems}
            for m in candidates:
                m.payload = _project_payload(
                    m.memory_type, m.payload, include_details=include_details, projection=projection
                )
                sr = by_id.get(m.id)
                if sr is None or sr.score < 0.5:
                    by_id[m.id] = SearchResult(
                        memory=m, score=0.5, distance=None, source="graph", metadata={}
                    )
            results = list(by_id.values())

    except DatabaseError:
        if has_query:
            qf = _qdrant_filters(user_id, memo_type, modified_within_days, filters)
            qvec = embedder.get_embedding(query or "")
            vec = qdrant.search_points(vector=qvec, limit=limit, user_id=user_id, filters=qf)
            for r in vec:
                payload = r.get("payload", {})
                core = payload.get("core", {})
                entity = payload.get("entity", {})
                statement = entity.get("statement") or core.get("statement") or ""
                m = Memory(
                    id=r.get("id") or str(uuid4()),
                    user_id=core.get("user_id", ""),
                    memory_type=core.get("memory_type", "memo"),
                    payload={
                        "statement": statement,
                        **{k: v for k, v in entity.items() if k != "statement"},
                    },
                    tags=core.get("tags", []),
                    confidence=core.get("confidence", 0.8),
                    is_valid=core.get("is_valid", True),
                    created_at=_parse_datetime(core.get("created_at")),
                    supersedes=core.get("supersedes"),
                    superseded_by=core.get("superseded_by"),
                    vector=None,
                    hrid=core.get("hrid"),  # NEW
                )
                # NEW: project anchor payload according to include_details/projection
                m.payload = _project_payload(
                    m.memory_type, m.payload, include_details=include_details, projection=projection
                )
                results.append(
                    SearchResult(
                        memory=m,
                        score=float(r.get("score", 0.0)),
                        distance=None,
                        source="qdrant",
                        metadata={},
                    )
                )
        else:
            results = []

    # neighbors (anchors only)
    results = _append_neighbors(results, kuzu, neighbor_cap, relation_names)

    # final order & clamp
    def _sort_key(r: SearchResult):
        h = r.memory.hrid
        h_idx = hrid_to_index(h) if h else 9_999_999_999  # push missing HRIDs last
        return (-r.score, h_idx, r.memory.id)

    results.sort(key=_sort_key)
    return results[:limit]
