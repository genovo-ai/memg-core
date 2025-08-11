#!/usr/bin/env python3
"""Deterministic indexing policy for memg-core.

Selects the `index_text` used for embeddings and persists it in vector payloads.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from memg_core.models.core import Memory, MemoryType


def _safe_join_title_and_content(title: str | None, content: str) -> str:
    if title and title.strip():
        return f"{title.strip()}. {content}".strip()
    return content


def build_index_text(memory: Memory) -> str:
    """Return the deterministic index_text for a memory based on its type.

    YAML-aware behavior (when MEMG_ENABLE_YAML_SCHEMA=true and MEMG_YAML_SCHEMA points to a file):
    - If an entity with name == memory.memory_type.value exists and defines an 'anchor' field,
      we use that field value (falling back to content if empty/missing).

    Default behavior (no YAML):
    - note: content
    - document: summary if present else content
    - task: content (+ title if present)
    """
    # Only attempt YAML loading if explicitly enabled
    if os.getenv("MEMG_ENABLE_YAML_SCHEMA", "false").lower() == "true":
        schema_path = os.getenv("MEMG_YAML_SCHEMA")
        if schema_path:
            if not Path(schema_path).exists():
                raise FileNotFoundError(f"YAML schema file not found: {schema_path}")

            with open(schema_path, encoding="utf-8") as f:
                data: dict[str, Any] = yaml.safe_load(f) or {}

            entities = data.get("entities", [])
            target = memory.memory_type.value
            for ent in entities:
                if str(ent.get("name", "")).lower() == target:
                    anchor_field = ent.get("anchor")
                    if isinstance(anchor_field, str) and anchor_field:
                        # Pull attribute from memory if available
                        val = getattr(memory, anchor_field, None)
                        if isinstance(val, str) and val.strip():
                            return val
                        # Document-specific: if anchor is summary but empty, fallback to content
                        if anchor_field != "content" and hasattr(memory, "content"):
                            content_val = getattr(memory, "content", "")
                            if isinstance(content_val, str) and content_val.strip():
                                return content_val
                    break

    # Defaults without YAML
    if memory.memory_type == MemoryType.NOTE:
        return memory.content
    if memory.memory_type == MemoryType.DOCUMENT:
        return memory.summary if (memory.summary and memory.summary.strip()) else memory.content
    if memory.memory_type == MemoryType.TASK:
        return _safe_join_title_and_content(memory.title, memory.content)
    # Fallback for unknown types: use content
    return memory.content
