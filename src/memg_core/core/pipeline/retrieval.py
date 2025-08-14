"""Graph-first retrieval pipeline with vector rerank and neighbor append"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..exceptions import DatabaseError
from ..interfaces.embedder import Embedder
from ..interfaces.kuzu import KuzuInterface
from ..interfaces.qdrant import QdrantInterface
from ..models import Memory, SearchResult


def _parse_datetime(date_str: Any) -> datetime:
    """Parse a datetime string or return current time if None or invalid."""
    if date_str and isinstance(date_str, str):
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            # Fall back to current time for invalid dates
            return datetime.now(UTC)
    return datetime.now(UTC)


def _build_graph_query(
    base_query: str,
    user_id: str | None,
    limit: int,
    entity_types: list[str] | None = None,
    relation_names: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build graph query for entity-based search"""
    # Use provided relation names or default to MENTIONS
    rel_alternatives = "|".join(relation_names or ["MENTIONS"])

    cypher = f"""
    MATCH (m:Memory)-[r:{rel_alternatives}]->(e:Entity)
    WHERE toLower(e.name) CONTAINS toLower($q)
    """
    params: dict[str, Any] = {"q": base_query, "limit": limit}

    if entity_types:
        type_conditions = " OR ".join([f"e.type = '{t}'" for t in entity_types])
        cypher += f" AND ({type_conditions})"

    if user_id:
        cypher += " AND m.user_id = $user_id"
        params["user_id"] = user_id

    cypher += """
    RETURN DISTINCT m.id, m.user_id, m.content, m.title, m.memory_type,
           m.created_at, m.summary, m.source, m.tags, m.confidence
    ORDER BY m.created_at DESC
    LIMIT $limit
    """
    return cypher, params


def _rows_to_memories(rows: list[dict[str, Any]]) -> list[Memory]:
    """Convert graph query rows to Memory objects"""
    results: list[Memory] = []
    for row in rows:
        memory_type = row.get("m.memory_type", row.get("memory_type", "note"))

        created_at_raw = row.get("m.created_at", row.get("created_at"))
        try:
            created_dt = (
                datetime.fromisoformat(created_at_raw) if created_at_raw else datetime.now(UTC)
            )
        except (ValueError, TypeError):
            # Fall back to current time for invalid dates
            created_dt = datetime.now(UTC)

        # Build minimal payload from available Kuzu fields
        payload = {}
        if row.get("m.title") or row.get("title"):
            payload["title"] = row.get("m.title") or row.get("title", "")

        # Add task-specific fields if available (stored in Kuzu for relationship purposes)
        if memory_type == "task":
            if row.get("m.task_status") or row.get("task_status"):
                payload["task_status"] = row.get("m.task_status") or row.get("task_status", "")
            if row.get("m.assignee") or row.get("assignee"):
                payload["assignee"] = row.get("m.assignee") or row.get("assignee", "")
            if row.get("m.due_date") or row.get("due_date"):
                payload["due_date"] = row.get("m.due_date") or row.get("due_date", "")

        results.append(
            Memory(
                id=row.get("m.id") or row.get("id") or str(uuid4()),
                user_id=row.get("m.user_id") or row.get("user_id", ""),
                memory_type=memory_type,
                payload=payload,
                tags=(row.get("m.tags", "").split(",") if row.get("m.tags") else []),
                confidence=float(row.get("m.confidence", 0.8)),
                is_valid=bool(row.get("m.is_valid", True)),
                created_at=created_dt,
                supersedes=row.get("m.supersedes") or None,
                superseded_by=row.get("m.superseded_by") or None,
            )
        )
    return results


def _rerank_with_vectors(
    query: str,
    candidates: list[Memory],
    qdrant: QdrantInterface,
    embedder: Embedder,
) -> list[SearchResult]:
    """Rerank graph results using vector similarity"""
    qvec = embedder.get_embedding(query)
    vec_results = qdrant.search_points(vector=qvec, limit=max(10, len(candidates)))

    # Map scores to candidate ids
    score_by_id = {r.get("id"): float(r.get("score", 0.0)) for r in vec_results}

    results: list[SearchResult] = []
    for mem in candidates:
        score = score_by_id.get(mem.id, 0.5)  # default mid score if not found
        results.append(
            SearchResult(memory=mem, score=score, distance=None, source="graph_rerank", metadata={})
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results


def _append_neighbors(
    seeds: list[SearchResult],
    kuzu: KuzuInterface,
    neighbor_limit: int,
) -> list[SearchResult]:
    """Append graph neighbors to results"""
    expanded: list[SearchResult] = []

    for seed in seeds[: min(5, len(seeds))]:
        mem = seed.memory
        if not mem.id:
            continue

        neighbors = kuzu.neighbors(
            node_label="Memory",
            node_id=mem.id,
            rel_types=None,
            direction="any",
            limit=neighbor_limit,
            neighbor_label="Memory",
        )

        for row in neighbors:
            mtype = row.get("memory_type", "note")

            # Build minimal payload for neighbor
            neighbor_payload = {}
            if row.get("title"):
                neighbor_payload["title"] = row.get("title", "")

            neighbor_memory = Memory(
                id=row.get("id") or str(uuid4()),
                user_id=row.get("user_id", ""),
                memory_type=mtype,
                payload=neighbor_payload,
                confidence=0.8,
                is_valid=True,
                created_at=_parse_datetime(row.get("created_at")),
                supersedes=None,
                superseded_by=None,
                tags=[],
            )

            expanded.append(
                SearchResult(
                    memory=neighbor_memory,
                    score=max(0.3, seed.score * 0.9),
                    distance=None,
                    source="graph_neighbor",
                    metadata={"from": mem.id},
                )
            )

    # Merge by id, keep highest score
    by_id: dict[str, SearchResult] = {r.memory.id: r for r in seeds}
    for r in expanded:
        if not r.memory.id:
            continue
        if r.memory.id in by_id:
            if r.score > by_id[r.memory.id].score:
                by_id[r.memory.id] = r
        else:
            by_id[r.memory.id] = r

    return list(by_id.values())


def graph_rag_search(
    query: str,
    user_id: str,
    limit: int,
    qdrant: QdrantInterface,
    kuzu: KuzuInterface,
    embedder: Embedder,
    filters: dict[str, Any] | None = None,
    relation_names: list[str] | None = None,
    neighbor_cap: int = 5,
) -> list[SearchResult]:
    """Graph-first retrieval with vector rerank and neighbor append

    Args:
        query: Search query
        user_id: User ID for filtering
        limit: Maximum results to return
        qdrant: Qdrant interface instance
        kuzu: Kuzu interface instance
        embedder: Embedder interface instance
        filters: Optional filters for vector search
        relation_names: Optional list of relation types (defaults to ["MENTIONS"])
        neighbor_cap: Maximum neighbors per result (default: 5)

    Returns:
        List of search results sorted by score
    """
    # 1) Graph candidate discovery
    try:
        cypher, params = _build_graph_query(
            query, user_id=user_id, limit=limit, relation_names=relation_names
        )
        rows = kuzu.query(cypher, params)
        candidates = _rows_to_memories(rows)
    except DatabaseError:
        # If graph query fails (e.g., Entity table doesn't exist), skip to vector search
        candidates = []

    # 2) Optional vector rerank if we have candidates
    results: list[SearchResult]
    if candidates:
        results = _rerank_with_vectors(query, candidates, qdrant, embedder)
    else:
        # 4) Fallback: vector-only
        qvec = embedder.get_embedding(query)
        vec = qdrant.search_points(vector=qvec, limit=limit, user_id=user_id, filters=filters or {})
        results = []
        for r in vec:
            payload = r.get("payload", {})
            core_data = payload.get("core", {})
            entity_data = payload.get("entity", {})

            mtype = core_data.get("memory_type", "note")

            mem = Memory(
                id=r.get("id") or str(uuid4()),
                user_id=core_data.get("user_id", ""),
                memory_type=mtype,
                payload=entity_data,  # All entity-specific fields
                tags=core_data.get("tags", []),
                confidence=core_data.get("confidence", 0.8),
                is_valid=core_data.get("is_valid", True),
                created_at=(
                    datetime.fromisoformat(core_data.get("created_at"))
                    if core_data.get("created_at")
                    else datetime.now(UTC)
                ),
                supersedes=core_data.get("supersedes"),
                superseded_by=core_data.get("superseded_by"),
            )
            results.append(
                SearchResult(
                    memory=mem,
                    score=float(r.get("score", 0.0)),
                    distance=None,
                    source="vector_fallback",
                    metadata={},
                )
            )

    # 3) Neighbor append
    results = _append_neighbors(results, kuzu, neighbor_cap)

    # Sort and clamp
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
