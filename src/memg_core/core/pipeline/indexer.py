# memg_core/core/pipeline/indexer.py
"""Indexer: deterministic add-memory pipeline - single writer (refactored)
- Anchor text comes from YAML translator (unified: per-type anchor_field → anchor text).
- No dependency on deprecated core/indexing.py.
- Embedding is always computed from anchor text.
- Upserts to Qdrant, mirrors node to Kuzu.
"""

from __future__ import annotations

from datetime import UTC, datetime

from memg_core.core.exceptions import ProcessingError
from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory
from memg_core.utils import generate_hrid


def add_memory_index(
    memory: Memory,
    qdrant: QdrantInterface,
    kuzu: KuzuInterface,
    embedder: Embedder,
    collection: str | None = None,
) -> str:
    """Index a Memory into Qdrant (vector) and Kuzu (graph).

    Behavior:
      - Anchor text comes from YAML-defined anchor field.
      - Embedding is computed from the anchor text.
      - Qdrant upsert with payload from `Memory.to_qdrant_payload()`.
      - Kuzu upsert as node with `Memory.to_kuzu_node()`.

    Returns:
      Qdrant point ID (string), which should equal `memory.id`.
    """
    try:
        # Validate memory_type against TypeRegistry - crash if invalid
        from ..types import validate_entity_type

        if not validate_entity_type(memory.memory_type):
            raise ProcessingError(
                f"Invalid memory_type: {memory.memory_type}",
                operation="add_memory_index",
                context={"memory_id": memory.id, "memory_type": memory.memory_type},
            )

        # Get anchor text via YAML translator - NO hardcoded fields
        from ..yaml_translator import build_anchor_text

        anchor = build_anchor_text(memory)
        if not anchor:
            raise ProcessingError(
                "Empty anchor text from YAML-defined anchor field",
                operation="add_memory_index",
                context={
                    "memory_id": memory.id,
                    "memory_type": memory.memory_type,
                },
            )

        # Stamp created_at and updated_at timestamps.
        now = datetime.now(UTC)
        if memory.created_at is None:
            memory.created_at = now
        memory.updated_at = now

        # Ensure HRID exists (flows into both stores via payload/node)
        if not memory.hrid:
            try:
                memory.hrid = generate_hrid(memory.memory_type, qdrant)
            except Exception as gen_err:
                raise ProcessingError(
                    "Failed to generate HRID",
                    operation="add_memory_index",
                    context={"memory_type": memory.memory_type},
                    original_error=gen_err,
                )

        # Compute vector
        vector = embedder.get_embedding(anchor)

        # Ensure collection exists (vector size default handled by interface)
        qdrant.ensure_collection(collection=collection)

        # Build payload and upsert into Qdrant
        payload = memory.to_qdrant_payload()
        success, point_id = qdrant.add_point(
            vector=vector,
            payload=payload,
            point_id=getattr(memory, "id", None),
            collection=collection,
        )
        if not success:
            raise ProcessingError(
                "Failed to upsert memory into Qdrant",
                operation="add_memory_index",
                context={"memory_id": memory.id},
            )

        # Mirror node into Kuzu
        kuzu.add_node("Memory", memory.to_kuzu_node())

        return point_id

    except Exception as e:
        if isinstance(e, ProcessingError):
            raise
        raise ProcessingError(
            "Failed to index memory",
            operation="add_memory_index",
            context={
                "memory_id": memory.id,
                "memory_type": memory.memory_type,
            },
            original_error=e,
        )
