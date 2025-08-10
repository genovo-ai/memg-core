#!/usr/bin/env python3
"""Indexer: deterministic add-memory pipeline used by application layer."""

from __future__ import annotations

from datetime import UTC, datetime

from memg_core.core_services.embeddings import GenAIEmbedder
from memg_core.database_services import KuzuInterface, QdrantInterface
from memg_core.models.core import Memory
from memg_core.policies import build_index_text


def add_memory_index(
    memory: Memory,
    *,
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
    embedder: GenAIEmbedder | None = None,
    collection: str | None = None,
) -> str:
    qdrant = qdrant or QdrantInterface()
    kuzu = kuzu or KuzuInterface()
    embedder = embedder or GenAIEmbedder()

    index_text = build_index_text(memory)
    vector = embedder.get_embedding(index_text)

    payload = memory.to_qdrant_payload()
    payload["index_text"] = index_text
    payload.setdefault("created_at", datetime.now(UTC).isoformat())

    success, point_id = qdrant.add_point(
        vector=vector,
        payload=payload,
        point_id=memory.id,
        collection=collection,
    )
    if not success:
        raise RuntimeError("Failed to upsert memory into Qdrant")

    kuzu.add_node("Memory", memory.to_kuzu_node())
    return point_id
