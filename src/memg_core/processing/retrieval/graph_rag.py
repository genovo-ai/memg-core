#!/usr/bin/env python3
"""Graph-first retrieval pipeline with vector rerank and neighbor append.

If graph returns 0 candidates, fall back to vector search and then neighbor append.
"""

from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Any

from memg_core.core_services.embeddings import GenAIEmbedder
from memg_core.database_services import KuzuInterface, QdrantInterface
from memg_core.models.core import Memory, MemoryType, SearchResult


def _build_graph_query(
    base_query: str, user_id: str | None, limit: int, entity_types: list[str] | None = None
) -> tuple[str, dict[str, Any]]:
    cypher = """
    MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
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
    results: list[Memory] = []
    for row in rows:
        raw_memory_type = row.get("m.memory_type", row.get("memory_type", "note"))
        try:
            memory_type = MemoryType(raw_memory_type)
        except Exception:
            memory_type = MemoryType.NOTE
        created_at_raw = row.get("m.created_at", row.get("created_at"))
        if created_at_raw:
            try:
                created_dt = datetime.fromisoformat(created_at_raw)
            except Exception:
                created_dt = datetime.now(UTC)
        else:
            created_dt = datetime.now(UTC)
        results.append(
            Memory(
                id=row.get("m.id") or row.get("id"),
                user_id=row.get("m.user_id") or row.get("user_id", ""),
                content=row.get("m.content") or row.get("content", ""),
                memory_type=memory_type,
                summary=row.get("m.summary"),
                title=row.get("m.title"),
                source=row.get("m.source", "user"),
                tags=(row.get("m.tags", "").split(",") if row.get("m.tags") else []),
                confidence=float(row.get("m.confidence", 0.8)),
                is_valid=True,
                created_at=created_dt,
            )
        )
    return results


def _rerank_with_vectors(
    query: str,
    candidates: list[Memory],
    qdrant: QdrantInterface,
    embedder: GenAIEmbedder,
) -> list[SearchResult]:
    # For simplicity, use Qdrant search over query embedding and map payloads to candidate ids when possible.
    qvec = embedder.get_embedding(query)
    vec_results = qdrant.search_points(vector=qvec, limit=max(10, len(candidates)))
    # Map scores to candidate ids when id matches
    score_by_id = {r.get("id"): float(r.get("score", 0.0)) for r in vec_results}
    results: list[SearchResult] = []
    for mem in candidates:
        score = score_by_id.get(mem.id, 0.5)  # default mid score if not found
        results.append(SearchResult(memory=mem, score=score, source="graph_rerank", metadata={}))
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def _append_neighbors(
    seeds: list[SearchResult],
    kuzu: KuzuInterface,
    neighbor_limit_default: int,
) -> list[SearchResult]:
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
            limit=neighbor_limit_default,
            neighbor_label="Memory",
        )
        for row in neighbors:
            try:
                mtype = MemoryType(row.get("memory_type", "note"))
            except Exception:
                mtype = MemoryType.NOTE
            neighbor_memory = Memory(
                id=row.get("id"),
                user_id=row.get("user_id", ""),
                content=row.get("content", ""),
                memory_type=mtype,
                title=row.get("title"),
                created_at=datetime.fromisoformat(row.get("created_at"))
                if row.get("created_at")
                else datetime.now(UTC),
            )
            expanded.append(
                SearchResult(
                    memory=neighbor_memory,
                    score=max(0.3, seed.score * 0.9),
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


async def graph_rag_search(
    query: str,
    user_id: str,
    *,
    limit: int = 10,
    filters: dict | None = None,
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
    embedder: GenAIEmbedder | None = None,
) -> list[SearchResult]:
    qdrant = qdrant or QdrantInterface()
    kuzu = kuzu or KuzuInterface()
    embedder = embedder or GenAIEmbedder()

    # 1) Graph candidate discovery
    cypher, params = _build_graph_query(query, user_id=user_id, limit=limit)
    rows = kuzu.query(cypher, params)
    candidates = _rows_to_memories(rows)

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
            try:
                mtype = MemoryType(payload.get("memory_type", "note"))
            except Exception:
                mtype = MemoryType.NOTE
            mem = Memory(
                id=r.get("id"),
                user_id=payload.get("user_id", ""),
                content=payload.get("content", ""),
                memory_type=mtype,
                summary=payload.get("summary"),
                title=payload.get("title"),
                source=payload.get("source", "user"),
                tags=payload.get("tags", []),
                confidence=payload.get("confidence", 0.8),
                is_valid=payload.get("is_valid", True),
                created_at=datetime.fromisoformat(payload.get("created_at"))
                if payload.get("created_at")
                else datetime.now(UTC),
            )
            results.append(
                SearchResult(
                    memory=mem,
                    score=float(r.get("score", 0.0)),
                    source="vector_fallback",
                    metadata={},
                )
            )

    # 3) Neighbor append
    neighbor_cap = int(os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT", "5"))
    results = _append_neighbors(results, kuzu, neighbor_cap)

    # Sort and clamp
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
