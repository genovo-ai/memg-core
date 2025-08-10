#!/usr/bin/env python3
"""System info utilities for memg-core."""

from __future__ import annotations

import os
from typing import Any

from ..kuzu_graph.interface import KuzuInterface
from ..qdrant.interface import QdrantInterface
from .yaml_schema import _resolve_yaml_path, load_yaml_schema  # type: ignore


def get_system_info(qdrant: QdrantInterface | None = None) -> dict[str, Any]:
    """Return a dictionary of core system information.

    Includes: active registry path/presence, qdrant stats, graph flag, neighbor caps.
    """
    info: dict[str, Any] = {}

    # Registry
    active_path = _resolve_yaml_path(None)
    schema = load_yaml_schema(active_path) if active_path else None
    info["registry"] = {
        "path": active_path,
        "loaded": bool(schema is not None),
        "retrieval": (
            {
                "graph_first": getattr(getattr(schema, "retrieval", None), "graph_first", True),
                "neighbor_notes_limit": getattr(
                    getattr(schema, "retrieval", None), "neighbor_notes_limit", None
                ),
                "neighbor_docs_limit": getattr(
                    getattr(schema, "retrieval", None), "neighbor_docs_limit", None
                ),
            }
            if schema
            else None
        ),
    }

    # Qdrant stats
    qdr = qdrant or QdrantInterface()
    info["qdrant"] = qdr.get_stats()
    info["qdrant"]["collection"] = qdr.collection_name

    # Graph flag and neighbor caps
    info["graph_enabled"] = os.getenv("MEMG_ENABLE_GRAPH_SEARCH", "true").lower() == "true"
    info["neighbor_cap_default"] = int(os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT", "5"))

    # Kuzu availability
    try:
        _ = KuzuInterface  # reference only
        info["kuzu_available"] = True
    except Exception:
        info["kuzu_available"] = False

    return info
