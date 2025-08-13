"""System info utilities for memory system"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..core.config import get_config
from ..core.interfaces.kuzu import KuzuInterface
from ..core.interfaces.qdrant import QdrantInterface


def get_system_info(
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
) -> dict[str, Any]:
    """Return a dictionary of core system information.

    Includes: configuration, storage stats, plugin availability
    """
    info: dict[str, Any] = {}
    config = get_config()

    # Core configuration
    info["config"] = {
        "template": config.memg.template_name,
        "vector_dimension": config.memg.vector_dimension,
        "score_threshold": config.memg.score_threshold,
        "batch_size": config.memg.batch_processing_size,
    }

    # Plugin status
    yaml_enabled = os.getenv("MEMG_ENABLE_YAML_SCHEMA", "false").lower() == "true"
    yaml_path = os.getenv("MEMG_YAML_SCHEMA")
    info["plugins"] = {
        "yaml_schema": {
            "enabled": yaml_enabled,
            "path": yaml_path if yaml_enabled else None,
            "loaded": yaml_enabled and yaml_path and Path(yaml_path).exists(),
        }
    }

    # Qdrant stats
    if qdrant:
        try:
            collection_info = qdrant.get_collection_info()
            info["qdrant"] = {
                "collection": qdrant.collection_name,
                "exists": collection_info.get("exists", False),
                "vectors_count": collection_info.get("vectors_count", 0),
                "points_count": collection_info.get("points_count", 0),
                "vector_size": collection_info.get("config", {}).get("vector_size"),
            }
        except Exception:
            info["qdrant"] = {"error": "Failed to get Qdrant stats"}
    else:
        # Create a temporary instance for stats
        try:
            qdr = QdrantInterface(collection_name=config.memg.qdrant_collection_name)
            collection_info = qdr.get_collection_info()
            info["qdrant"] = {
                "collection": qdr.collection_name,
                "exists": collection_info.get("exists", False),
                "vectors_count": collection_info.get("vectors_count", 0),
                "points_count": collection_info.get("points_count", 0),
                "vector_size": collection_info.get("config", {}).get("vector_size"),
            }
        except Exception:
            info["qdrant"] = {"error": "Qdrant not available"}

    # Kuzu availability
    try:
        if kuzu:
            info["kuzu"] = {"available": True, "path": config.memg.kuzu_database_path}
        else:
            # Test if we can create an instance
            KuzuInterface(db_path=config.memg.kuzu_database_path)  # Just test if it works
            info["kuzu"] = {"available": True, "path": config.memg.kuzu_database_path}
    except Exception:
        info["kuzu"] = {"available": False}

    # Graph settings
    info["graph"] = {
        "neighbor_limit": int(os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT", "5")),
    }

    return info
