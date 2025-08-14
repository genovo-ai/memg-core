"""YAML Translator: validates payloads and resolves anchor text for embeddings.
This module makes the core type-agnostic by reading entity definitions from a YAML registry.

Supported registry shapes (flexible to ease migration):
- entities as a dict: {"note": {...}, "document": {...}}
- or entities as a list: [{"name"|"type": "...", "anchor": "...", "fields": {...}}, ...]

Each entity spec should define:
- name/type: the entity type string used by Memory.memory_type
- anchor: the payload field considered the anchor (mapped to embedding text)
- fields: a dict with "required"/"optional" or a flat dict of field specs

If the YAML is missing or a type is unknown, we fallback to common names:
  statement > summary > content > description > title > text
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
from importlib.resources import files as pkg_files
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import yaml

from .exceptions import MemorySystemError
from .models import Memory


class YamlTranslatorError(MemorySystemError):
    pass


class EntitySpec(BaseModel):
    name: str
    description: str | None = None
    anchor: str = Field(default="statement")
    fields: dict[str, Any] | None = None  # flexible; may contain required/optional/etc.


class YamlTranslator:
    def __init__(self, yaml_path: str | None = None) -> None:
        # Prefer explicit arg, then env
        self.yaml_path = yaml_path or os.getenv("MEMG_YAML_SCHEMA")
        self._schema: dict[str, Any] | None = None

    @property
    def schema(self) -> dict[str, Any]:
        if self._schema is not None:
            return self._schema

        # If explicit path is present, use it (strict)
        if self.yaml_path:
            self._schema = self._load_schema()
            return self._schema

        # Fallback to packaged minimal schema (keeps module usable in tests/dev)
        try:
            fallback_path = str(pkg_files("memg_core.core._defaults") / "entities.min.yaml")
            self.yaml_path = fallback_path
            self._schema = self._load_schema()
            return self._schema
        except Exception as e:
            raise YamlTranslatorError("MEMG_YAML_SCHEMA not set and fallback schema failed") from e

    def _load_schema(self) -> dict[str, Any]:
        """Load schema from the current yaml_path."""
        if not self.yaml_path:
            raise YamlTranslatorError("YAML path is None")
        path = Path(self.yaml_path)
        if not path.exists():
            raise YamlTranslatorError(f"YAML schema not found at {path}")
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data:
                raise YamlTranslatorError("Empty YAML schema")
            if not isinstance(data, dict):
                raise YamlTranslatorError("YAML schema root must be a mapping")
            return data
        except yaml.YAMLError as e:
            raise YamlTranslatorError(f"Invalid YAML syntax: {e}") from e

    def _entities_map(self) -> dict[str, dict[str, Any]]:
        sch = self.schema
        ents = sch.get("entities")
        if not ents:
            return {}
        if isinstance(ents, dict):
            # Normalize keys to lower
            return {str(k).lower(): v for k, v in ents.items()}
        # list form
        out: dict[str, dict[str, Any]] = {}
        for item in ents:
            if not isinstance(item, dict):
                continue
            key = (item.get("name") or item.get("type") or "").lower()
            if key:
                out[key] = item
        return out

    def get_entity_spec(self, entity_name: str) -> EntitySpec:
        if not entity_name:
            raise YamlTranslatorError("Empty entity name")
        name_l = entity_name.lower()
        emap = self._entities_map()
        spec_raw = emap.get(name_l)
        if not spec_raw:
            raise YamlTranslatorError(f"Entity '{entity_name}' not found in YAML schema")
        # Normalize
        anchor = spec_raw.get("anchor") or "statement"
        # fields may be in different shapes; pass-through
        return EntitySpec(
            name=name_l,
            description=spec_raw.get("description"),
            anchor=anchor,
            fields=spec_raw.get("fields"),
        )

    def get_anchor_field(self, entity_name: str) -> str:
        try:
            return self.get_entity_spec(entity_name).anchor
        except YamlTranslatorError:
            # Fallback path for unknown types if strict schema not required
            return "statement"

    def build_anchor_text(self, memory: Memory) -> str:
        # Determine anchor field from YAML (preferred) with robust fallback
        mem_type = getattr(memory, "memory_type", None) or getattr(memory, "type", None)
        payload: dict[str, Any] = getattr(memory, "payload", {}) or {}
        anchor_field = None

        with contextlib.suppress(Exception):
            anchor_field = self.get_anchor_field(str(mem_type))

        candidates = []
        if anchor_field:
            candidates.append(payload.get(anchor_field))
        # reasonable fallbacks
        for k in ("statement", "summary", "content", "description", "title", "text"):
            if anchor_field != k:
                candidates.append(payload.get(k))

        # first non-empty string wins
        for c in candidates:
            if isinstance(c, str):
                c = c.strip()
                if c:
                    return c

        raise YamlTranslatorError(
            "Unable to resolve anchor text",
            operation="build_anchor_text",
            context={"memory_type": mem_type, "available_keys": list(payload.keys())},
        )

    def _fields_contract(self, spec: dict[str, Any]) -> tuple[list[str], list[str]]:
        # supports either fields: {required:[...], optional:[...]} OR flat dict
        fields = spec.get("fields") or {}
        if "required" in fields or "optional" in fields:
            req = [str(x) for x in fields.get("required", [])]
            opt = [str(x) for x in fields.get("optional", [])]
            return req, opt
        # flat dict case: treat all as optional except anchor
        anchor = spec.get("anchor") or "statement"
        keys = list(fields.keys())
        if anchor in keys:
            req = [anchor]
            opt = [k for k in keys if k != anchor]
        else:
            req = []
            opt = keys
        return req, opt

    def validate_memory_against_yaml(
        self, memory_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not memory_type:
            raise YamlTranslatorError("memory_type is required")
        if payload is None:
            raise YamlTranslatorError("payload is required")

        emap = self._entities_map()
        spec = emap.get(memory_type.lower())
        if not spec:
            # pass-through if unknown; caller may still index
            return dict(payload)

        req, _opt = self._fields_contract(spec)
        missing = [k for k in req if not payload.get(k)]
        if missing:
            raise YamlTranslatorError(
                f"Missing required fields: {missing}", context={"memory_type": memory_type}
            )

        # Strip system-reserved fields if present
        cleaned = dict(payload)
        for syskey in ("id", "user_id", "created_at", "updated_at", "vector"):
            cleaned.pop(syskey, None)
        return cleaned

    def create_memory_from_yaml(
        self, memory_type: str, payload: dict[str, Any], user_id: str
    ) -> Memory:
        validated = self.validate_memory_against_yaml(memory_type, payload)
        # Construct Memory; the model is type-agnostic
        return Memory(memory_type=memory_type, payload=validated, user_id=user_id)


@lru_cache(maxsize=1)
def get_yaml_translator() -> YamlTranslator:
    return YamlTranslator()


def build_anchor_text(memory: Memory) -> str:
    return get_yaml_translator().build_anchor_text(memory)


def create_memory_from_yaml(memory_type: str, payload: dict[str, Any], user_id: str) -> Memory:
    return get_yaml_translator().create_memory_from_yaml(memory_type, payload, user_id)
