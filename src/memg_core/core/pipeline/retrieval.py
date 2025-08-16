# memg_core/core/pipeline/retrieval.py
"""Unified retrieval pipeline with automatic mode selection and neighbor expansion.
- YAML-driven: uses YAML-defined anchor fields for text anchoring.
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


def _find_see_also_memories(
    primary_results: list[SearchResult],
    qdrant: QdrantInterface,
    embedder: Embedder,
    user_id: str,
) -> list[SearchResult]:
    """Find semantically related memories based on YAML see_also configuration.

    For each primary result, if it has see_also configuration:
    1. Extract anchor text from the primary result
    2. Search for similar memories in target_types
    3. Apply threshold and limit filters
    4. Return combined see_also results
    """
    from ..yaml_translator import get_see_also_config

    see_also_results: list[SearchResult] = []

    for primary_result in primary_results:
        memory = primary_result.memory

        # Get see_also config for this memory type
        see_also_config = get_see_also_config(memory.memory_type)
        if not see_also_config or not see_also_config.get("enabled"):
            continue

        threshold = see_also_config["threshold"]
        limit = see_also_config["limit"]
        target_types = see_also_config["target_types"]

        if not target_types:
            continue

        # Get anchor text from the primary memory
        from ..yaml_translator import build_anchor_text

        try:
            anchor_text = build_anchor_text(memory)
        except Exception as e:
            # Skip if we can't extract anchor text - log the specific issue for transparency
            # This could happen if memory lacks the anchor field or YAML schema issues
            from ..logging import get_logger

            logger = get_logger("retrieval")
            logger.debug(
                f"Skipping see_also for memory {memory.id}: failed to extract anchor text - {e}"
            )
            continue

        # Search for similar memories in target types using efficient OR filtering
        anchor_embedding = embedder.get_embedding(anchor_text)

        # Use Qdrant's MatchAny for efficient OR filtering on multiple types
        # This creates a single search across all target types at once
        filters = {"core.memory_type": target_types}

        # Single vector search across all target types
        similar_points = qdrant.search_points(
            vector=anchor_embedding,
            limit=limit * len(target_types) * 2,  # Get enough candidates for all types
            user_id=user_id,
            filters=filters,
        )

        # Group results by type to respect per-type limits
        results_by_type: dict[str, list] = {target_type: [] for target_type in target_types}

        for point in similar_points:
            score = float(point.get("score", 0.0))

            # Apply threshold filter
            if score < threshold:
                continue

            # Skip if it's the same memory as the primary result
            if point.get("id") == memory.id:
                continue

            # Get memory type from the point
            payload = point.get("payload", {})
            core = payload.get("core", {})
            entity = payload.get("entity", {})
            point_memory_type = core.get("memory_type", "")

            # Check if we've hit the limit for this type
            if len(results_by_type.get(point_memory_type, [])) >= limit:
                continue

            # Convert point to Memory object
            similar_memory = Memory(
                id=point.get("id") or "",
                user_id=core.get("user_id", ""),
                memory_type=point_memory_type,
                payload=dict(entity),
                created_at=_parse_datetime(core.get("created_at")),
                updated_at=_parse_datetime(core.get("updated_at")),
                hrid=core.get("hrid"),
            )

            # Add to see_also results with special source marking
            search_result = SearchResult(
                memory=similar_memory,
                score=score,
                distance=None,
                source=f"see_also_{point_memory_type}",
                metadata={
                    "see_also_source": memory.memory_type,
                    "see_also_anchor": anchor_text[:100],  # Truncate for brevity
                },
            )

            see_also_results.append(search_result)
            results_by_type[point_memory_type].append(search_result)

    return see_also_results


# Deterministic field projection for payloads - YAML-driven
def _project_payload(
    memory_type: str,
    payload: dict[str, Any] | None,
    *,
    include_details: str,
    projection: dict[str, list[str]] | None,
) -> dict[str, Any]:
    """
    Returns a pruned payload. The YAML-defined anchor field is always included.
    """
    payload = dict(payload or {})
    if not payload:
        return {}

    # Get anchor field from YAML schema - NO hardcoding
    from ..yaml_translator import get_yaml_translator

    try:
        anchor_field = get_yaml_translator().get_anchor_field(memory_type)
    except Exception as e:
        # No fallbacks - raise error if YAML lookup fails
        from ..exceptions import ProcessingError

        raise ProcessingError(
            f"Failed to get anchor field for memory type '{memory_type}' from YAML schema",
            operation="_project_payload",
            context={"memory_type": memory_type, "include_details": include_details},
            original_error=e,
        )

    if include_details == "none":
        if anchor_field in payload:
            return {anchor_field: payload[anchor_field]}
        return {}

    # self / default behavior with optional projection
    allowed: set[str] | None = None
    if projection:
        allowed = set(projection.get(memory_type, []))

    # Always include the YAML-defined anchor field
    if allowed is not None:
        allowed.add(anchor_field)

    if allowed is None:
        return payload

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
        "\nRETURN DISTINCT m as node\n"  # Changed to return full node object
        "ORDER BY coalesce(m.updated_at, m.created_at) DESC\n"
        "LIMIT $limit"
    )
    return cypher, params


def _rows_to_memories(rows: list[dict[str, Any]]) -> list[Memory]:
    out: list[Memory] = []
    for row in rows:
        # Handle both old format (m.field) and new format (node object)
        if "node" in row and hasattr(row["node"], "__dict__"):
            # New format: extract from node object
            node_data = row["node"].__dict__ if hasattr(row["node"], "__dict__") else {}
        elif "node" in row and isinstance(row["node"], dict):
            # New format: node is already a dict
            node_data = row["node"]
        else:
            # Old format: fields with m. prefix
            node_data = row

        # Core fields are extracted directly - NO entity-specific fields
        core_fields = {
            "id": node_data.get("id") or row.get("m.id") or row.get("id") or str(uuid4()),
            "user_id": node_data.get("user_id") or row.get("m.user_id") or row.get("user_id", ""),
            "memory_type": node_data.get("memory_type")
            or row.get("m.memory_type")
            or row.get("memory_type")
            or "memo",
            "created_at": _parse_datetime(
                node_data.get("created_at") or row.get("m.created_at") or row.get("created_at")
            ),
            "updated_at": _parse_datetime(
                node_data.get("updated_at") or row.get("m.updated_at") or row.get("updated_at")
            ),
            "hrid": node_data.get("hrid") or row.get("m.hrid") or row.get("hrid"),
        }

        # All other fields from the node/row are considered part of the payload
        # Exclude core field names and heavy data like vectors
        core_field_names = {
            "id",
            "user_id",
            "memory_type",
            "created_at",
            "updated_at",
            "hrid",
            "vector",
        }

        if "node" in row:
            # New format: all fields from node except core fields
            payload = {
                key: value for key, value in node_data.items() if key not in core_field_names
            }
        else:
            # Old format: fields with m. prefix
            payload = {
                key.replace("m.", ""): value
                for key, value in row.items()
                if key.replace("m.", "") not in core_field_names
            }

        out.append(Memory(payload=payload, **core_fields))
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
        f["core.memory_type"] = memo_type  # Fixed field name
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
        score = score_by_id.get(mem.id, 0.0)  # No arbitrary fallback scores
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
    # Use provided relation names or empty list - no hardcoded defaults
    rels = relation_names or []

    # If no relation names provided, skip neighbor expansion entirely
    if not rels:
        return seeds

    for seed in seeds[: min(5, len(seeds))]:
        mem = seed.memory
        if not mem.id:
            continue
        try:
            rows = kuzu.neighbors(
                node_label="Memory",
                node_id=mem.id,
                rel_types=rels,
                direction="any",
                limit=neighbor_limit,
                neighbor_label="Memory",
            )
        except DatabaseError:
            # If relationship tables don't exist, skip neighbors for this seed
            # This is common in minimal setups or fresh databases
            continue
        for row in rows:
            # Use generic payload reconstruction without hardcoded field names
            core_field_names = {
                "id",
                "user_id",
                "memory_type",
                "created_at",
                "updated_at",
                "hrid",
            }
            payload = {k: v for k, v in row.items() if k not in core_field_names}
            neighbor = Memory(
                id=row.get("id") or str(uuid4()),
                user_id=row["user_id"],  # CRASH if missing - no fallback
                memory_type=row["memory_type"],  # CRASH if missing - no fallback
                payload=payload,
                created_at=_parse_datetime(row.get("created_at")),
                updated_at=_parse_datetime(row.get("updated_at")),
                vector=None,
                hrid=row.get("hrid"),
            )
            expanded.append(
                SearchResult(
                    memory=neighbor,
                    score=seed.score * 0.9,  # No arbitrary minimum score
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
    include_see_also: bool = False,  # NEW: enable see_also functionality
) -> list[SearchResult]:
    """Unified retrieval with graph-first approach as mandated by policy.

    - Default mode is graph-first with optional vector rerank.
    - If `mode='vector'` explicitly → vector-first.
    - If `mode='hybrid'` → merge by id with stable ordering.
    """
    # ---------------- validation ----------------
    has_query = bool(query and query.strip())
    has_scope = bool(memo_type or (filters and len(filters) > 0) or modified_within_days)
    if not has_query and not has_scope:
        return []

    # decide mode - default to graph-first as per policy
    eff_mode = mode or "graph"

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
                            memory=m, score=0.0, distance=None, source="graph", metadata={}
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

                # Reconstruct the Memory object strictly from its stored parts
                # The payload is the `entity` dict. Core fields are in `core`.
                m = Memory(
                    id=r.get("id") or str(uuid4()),
                    user_id=core.get("user_id", ""),
                    memory_type=core["memory_type"],  # CRASH if missing - no fallback
                    payload=entity,  # All entity fields in payload
                    # NO hardcoded field assumptions - payload contains all entity data
                    created_at=_parse_datetime(core.get("created_at")),
                    updated_at=_parse_datetime(core.get("updated_at")),
                    hrid=core.get("hrid"),
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
                # Type-agnostic: use all entity fields as payload, no hardcoded assumptions
                m = Memory(
                    id=r.get("id") or str(uuid4()),
                    user_id=core.get("user_id", ""),
                    memory_type=core["memory_type"],  # CRASH if missing - no fallback
                    payload=dict(entity),  # All entity fields, no filtering
                    # NO hardcoded field assumptions - payload contains all entity data
                    created_at=_parse_datetime(core.get("created_at")),
                    updated_at=_parse_datetime(core.get("updated_at")),
                    vector=None,
                    hrid=core.get("hrid"),
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
                if sr is None or sr.score < 0.1:  # Lower threshold, no arbitrary cutoff
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
                # Use all entity fields as payload without hardcoded assumptions
                m = Memory(
                    id=r.get("id") or str(uuid4()),
                    user_id=core.get("user_id", ""),
                    memory_type=core["memory_type"],  # CRASH if missing - no fallback
                    payload=dict(entity),  # All entity fields, no filtering
                    # NO hardcoded field assumptions - payload contains all entity data
                    created_at=_parse_datetime(core.get("created_at")),
                    updated_at=_parse_datetime(core.get("updated_at")),
                    vector=None,
                    hrid=core.get("hrid"),
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
    # The neighbor payload is constructed generically, so this should be fine.
    results = _append_neighbors(results, kuzu, neighbor_cap, relation_names)

    # see_also functionality - find semantically related memories
    if include_see_also and results:
        see_also_memories = _find_see_also_memories(results, qdrant, embedder, user_id)
        results.extend(see_also_memories)

    # final order & clamp - use the unified sort function
    results.sort(key=_sort_key)
    return results[:limit]
