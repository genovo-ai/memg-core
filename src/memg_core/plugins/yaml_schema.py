"""YAML schema loader for entity/relationship catalogs - optional plugin"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

import yaml


def _resolve_yaml_path() -> str | None:
    """Resolve YAML schema path from environment"""
    schema_path = os.getenv("MEMG_YAML_SCHEMA")
    if schema_path and Path(schema_path).exists():
        return schema_path
    return None


@lru_cache(maxsize=1)
def load_yaml_schema() -> dict[str, Any] | None:
    """Load YAML schema if enabled and available"""
    if os.getenv("MEMG_ENABLE_YAML_SCHEMA", "false").lower() != "true":
        return None

    path = _resolve_yaml_path()
    if not path:
        return None

    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def get_relation_names() -> list[str] | None:
    """Get relation names from YAML schema if available"""
    schema = load_yaml_schema()
    if not schema:
        return None

    relations = schema.get("relations", [])
    names = [str(r.get("name")).upper() for r in relations if r.get("name")]
    return names if names else None


def get_entity_anchor(entity_type: str) -> str | None:
    """Get anchor field for entity type from YAML schema"""
    schema = load_yaml_schema()
    if not schema:
        return None

    entities = schema.get("entities", [])
    for ent in entities:
        if str(ent.get("name", "")).lower() == entity_type.lower():
            anchor = ent.get("anchor")
            if isinstance(anchor, str) and anchor:
                return anchor
            break
    return None


def build_index_text_with_yaml(memory: Any) -> str | None:
    """Build index text using YAML schema anchor field"""
    schema = load_yaml_schema()
    if not schema:
        return None

    # Check if memory type has an anchor field defined
    anchor_field = get_entity_anchor(memory.memory_type.value)
    if not anchor_field:
        return None

    # Get the value from the anchor field
    val = getattr(memory, anchor_field, None)
    if isinstance(val, str) and val.strip():
        return val

    # For document type, fallback to content if summary is empty
    if anchor_field == "summary" and hasattr(memory, "content"):
        content_val = getattr(memory, "content", "")
        if isinstance(content_val, str) and content_val.strip():
            return content_val

    return None
