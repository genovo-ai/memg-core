#!/usr/bin/env python3
"""YAML schema loader for entity/relationship catalogs and retrieval knobs.

Feature-flagged via MEMG_ENABLE_YAML_SCHEMA and MEMG_YAML_SCHEMA path.
Optional: code compiles without YAML; when present, we use shipped core registries by default.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import yaml


class EntityTypeDef(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None


class RelationshipTypeDef(BaseModel):
    name: str
    description: str | None = None
    directionality: str = Field(default="undirected")  # directed | undirected
    from_types: list[str] = Field(default_factory=list)
    to_types: list[str] = Field(default_factory=list)


class RetrievalPolicy(BaseModel):
    graph_first: bool = True
    neighbor_notes_limit: int = 5
    neighbor_docs_limit: int = 3


class IndexingPolicy(BaseModel):
    note_index_text: str = "content"
    document_index_text: str = "summary_or_content"
    task_index_text: str = "content_plus_title"


class YamlSchema(BaseModel):
    entity_types: list[EntityTypeDef] = Field(default_factory=list)
    relationship_types: list[RelationshipTypeDef] = Field(default_factory=list)
    retrieval: RetrievalPolicy = Field(default_factory=RetrievalPolicy)
    indexing: IndexingPolicy = Field(default_factory=IndexingPolicy)


def _resolve_yaml_path(explicit_path: str | None) -> str | None:
    if explicit_path and Path(explicit_path).exists():
        return explicit_path
    env_path = os.getenv("MEMG_YAML_SCHEMA")
    if env_path and Path(env_path).exists():
        return env_path
    # Default to core minimal registry if present
    core_default = Path.cwd() / "integration" / "config" / "core.minimal.yaml"
    return str(core_default) if core_default.exists() else None


@lru_cache(maxsize=4)
def load_yaml_schema(path: str | None = None) -> YamlSchema | None:
    """Load YAML schema if available; returns None when not configured.

    Caches results to avoid repeated disk I/O.
    """
    final_path = _resolve_yaml_path(path)
    if not final_path:
        return None
    with open(final_path, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}
    # Normalize keys
    return YamlSchema(**data)
