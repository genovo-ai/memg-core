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
    """Get relation PREDICATES from YAML schema - FIXED: was using names instead of predicates"""
    try:
        from ..core.types import TypeRegistry

        registry = TypeRegistry.get_instance()
        return registry.get_valid_predicates()
    except RuntimeError:
        # TypeRegistry not initialized - fall back to direct YAML parsing
        schema = load_yaml_schema()
        if not schema:
            return None

        # Extract predicates from relations in entities (NEW YAML STRUCTURE)
        predicates = set()
        entities = schema.get("entities", [])
        for entity in entities:
            relations = entity.get("relations", [])
            for relation in relations:
                rel_predicates = relation.get("predicates", [])
                predicates.update(rel_predicates)

        return list(predicates) if predicates else None


def get_entity_anchor(entity_type: str) -> str | None:
    """Get anchor field for entity type from YAML schema"""
    try:
        from ..core.types import TypeRegistry

        # TODO: Add get_entity_anchor method to TypeRegistry
        # For now, fall back to direct parsing
        TypeRegistry.get_instance()  # Just validate it's initialized
    except RuntimeError:
        pass

    # Direct YAML parsing fallback
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

    # Get the value from the anchor field (no fallback logic)
    val = getattr(memory, anchor_field, None)
    if isinstance(val, str) and val.strip():
        return val

    # No fallback logic - if anchor field is missing/empty, return None
    # This enforces strict YAML schema compliance
    return None
