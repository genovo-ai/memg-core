"""Indexer: deterministic add-memory pipeline - single writer"""

from __future__ import annotations

from datetime import UTC, datetime

from ..exceptions import ProcessingError
from ..indexing import build_index_text
from ..interfaces.embedder import Embedder
from ..interfaces.kuzu import KuzuInterface
from ..interfaces.qdrant import QdrantInterface
from ..models import Memory


def add_memory_index(
    memory: Memory,
    qdrant: QdrantInterface,
    kuzu: KuzuInterface,
    embedder: Embedder,
    collection: str | None = None,
    index_text_override: str | None = None,
) -> str:
    """Add memory to both Qdrant and Kuzu stores - single writer pattern

    Args:
        memory: The memory to index
        qdrant: Qdrant interface instance
        kuzu: Kuzu interface instance
        embedder: Embedder interface instance
        collection: Optional Qdrant collection name
        index_text_override: Optional override for index text (bypasses build_index_text)

    Returns:
        The point ID of the indexed memory

    Raises:
        ProcessingError: If indexing fails
    """
    try:
        # Build index text based on memory type
        index_text = index_text_override or build_index_text(memory)

        # Generate embedding
        vector = embedder.get_embedding(index_text)

        # Prepare Qdrant payload
        payload = memory.to_qdrant_payload()
        payload["index_text"] = index_text
        payload.setdefault("created_at", datetime.now(UTC).isoformat())

        # Write to Qdrant
        success, point_id = qdrant.add_point(
            vector=vector,
            payload=payload,
            point_id=memory.id,
            collection=collection,
        )

        if not success:
            raise ProcessingError(
                "Failed to upsert memory into Qdrant",
                operation="add_memory_index",
                context={"memory_id": memory.id},
            )

        # Write to Kuzu
        kuzu.add_node("Memory", memory.to_kuzu_node())

        return point_id

    except Exception as e:
        if isinstance(e, ProcessingError):
            raise
        raise ProcessingError(
            "Failed to index memory",
            operation="add_memory_index",
            context={"memory_id": memory.id, "memory_type": memory.memory_type.value},
            original_error=e,
        )
