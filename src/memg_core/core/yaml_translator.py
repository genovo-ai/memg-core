"""YAML Translator: validates payloads and resolves anchor text for embeddings.
This module makes the core type-agnostic by reading entity definitions from a YAML registry.

Supported registry shapes (flexible to ease migration):
- entities as a dict: {"note": {...}, "document": {...}}
- or entities as a list: [{"name"|"type": "...", "anchor": "...", "fields": {...}}, ...]

Each entity spec should define:
- name/type: the entity type string used by Memory.memory_type
- anchor: the payload field considered the anchor (mapped to embedding text)
- fields: a dict with "required"/"optional" or a flat dict of field specs

YAML schema is required and must define all entity types with explicit anchor fields.
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel
import yaml

from .exceptions import MemorySystemError


class YamlTranslatorError(MemorySystemError):
    """Error in YAML schema translation or validation."""

    pass


class EntitySpec(BaseModel):
    """Specification for a YAML-defined entity type."""

    name: str
    description: str | None = None
    anchor: str  # NO DEFAULT - must be explicitly defined in YAML
    fields: dict[str, Any] | None = None  # flexible; may contain required/optional/etc.


class YamlTranslator:
    """Translates YAML schema definitions to Pydantic models for strict validation."""

    def __init__(self, yaml_path: str | None = None) -> None:
        # Prefer explicit arg, then env
        self.yaml_path = yaml_path or os.getenv("MEMG_YAML_SCHEMA")
        self._schema: dict[str, Any] | None = None
        self._model_cache: dict[str, Any] = {}  # Instance cache to avoid memory leaks

    @property
    def schema(self) -> dict[str, Any]:
        if self._schema is not None:
            return self._schema

        # If explicit path is present, use it (strict)
        if self.yaml_path:
            self._schema = self._load_schema()
            return self._schema

        # Default fallback to built-in core.minimal.yaml
        try:
            from pathlib import Path

            # Look for config/core.minimal.yaml relative to project root
            default_path = (
                Path(__file__).parent.parent.parent.parent / "config" / "core.minimal.yaml"
            )
            if default_path.exists():
                self.yaml_path = str(default_path)
                self._schema = self._load_schema()
                return self._schema
        except Exception as e:
            # Re-raise with context instead of silent failure
            raise YamlTranslatorError(
                f"Failed to load YAML schema from {self.yaml_path}: {e}"
            ) from e

        # No valid YAML schema found
        raise YamlTranslatorError(
            "No YAML schema found. Set MEMG_YAML_SCHEMA environment variable "
            "or ensure config/core.minimal.yaml exists"
        )

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
        anchor = spec_raw.get("anchor")
        if not anchor:
            raise YamlTranslatorError(
                f"No anchor field defined for entity type '{entity_name}' in YAML schema"
            )
        # fields may be in different shapes; pass-through
        return EntitySpec(
            name=name_l,
            description=spec_raw.get("description"),
            anchor=anchor,
            fields=spec_raw.get("fields"),
        )

    def get_anchor_field(self, entity_name: str) -> str:
        return self.get_entity_spec(entity_name).anchor

    def build_anchor_text(self, memory) -> str:
        # Determine anchor field from YAML schema
        mem_type = getattr(memory, "memory_type", None) or getattr(memory, "type", None)
        payload: dict[str, Any] = getattr(memory, "payload", {}) or {}
        anchor_field = None

        with contextlib.suppress(Exception):
            anchor_field = self.get_anchor_field(str(mem_type))

        # Use only the YAML-defined anchor field, no fallbacks
        if not anchor_field:
            raise YamlTranslatorError(f"No anchor field found for memory type '{mem_type}'")

        anchor_text = payload.get(anchor_field)
        if not anchor_text:
            raise YamlTranslatorError(
                f"Missing anchor field '{anchor_field}' for memory type '{mem_type}'"
            )

        if isinstance(anchor_text, str):
            anchor_text = anchor_text.strip()
            if anchor_text:
                return anchor_text

        raise YamlTranslatorError(
            f"Anchor field '{anchor_field}' is empty or invalid for memory type '{mem_type}'",
            operation="build_anchor_text",
            context={
                "memory_type": mem_type,
                "anchor_field": anchor_field,
                "available_keys": list(payload.keys()),
            },
        )

    def _fields_contract(self, spec: dict[str, Any]) -> tuple[list[str], list[str]]:
        # supports either fields: {required:[...], optional:[...]} OR flat dict
        fields = spec.get("fields") or {}
        if "required" in fields or "optional" in fields:
            req = [str(x) for x in fields.get("required", [])]
            opt = [str(x) for x in fields.get("optional", [])]
            return req, opt
        # flat dict case: treat all as optional except anchor
        anchor = spec.get("anchor")
        if not anchor:
            raise YamlTranslatorError("No anchor field defined for entity type in YAML schema")
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

    def create_memory_from_yaml(self, memory_type: str, payload: dict[str, Any], user_id: str):
        from .models import Memory  # local import to avoid cycles

        validated = self.validate_memory_against_yaml(memory_type, payload)
        # Construct Memory; the model is type-agnostic
        return Memory(memory_type=memory_type, payload=validated, user_id=user_id)

    def _python_type_for_yaml(self, yaml_type: str, field_def: dict[str, Any]):
        """Map YAML 'type' string to a Python type annotation used by Pydantic."""
        from datetime import datetime
        from typing import Literal

        yaml_type = str(yaml_type).lower()

        # Handle enum types
        if yaml_type == "enum":
            choices = field_def.get("choices", [])
            if choices:
                return Literal[tuple(choices)]
            return str

        # Standard type mapping
        mapping = {
            "string": str,
            "float": float,
            "bool": bool,
            "datetime": datetime,
            "tags": list[str],
            "vector": list[float],
        }
        return mapping.get(yaml_type, str)

    def get_entity_model(self, entity_name: str):
        """Return (and cache) a dynamic Pydantic model for the given entity type."""
        # Check cache first to avoid memory leaks
        if entity_name in self._model_cache:
            return self._model_cache[entity_name]

        from typing import Union

        from pydantic import Field, create_model  # local import to avoid global dependency

        spec = self.get_entity_spec(entity_name)
        if not spec.fields:
            # No field definitions – return minimal model
            return create_model(f"{spec.name.capitalize()}Entity")

        # Use Any for model_fields to avoid complex type annotations
        model_fields: dict[str, Any] = {}
        for field_name, field_def in spec.fields.items():
            # Skip system-reserved fields – these live on the core Memory object
            if field_def.get("system"):
                continue

            yaml_type = field_def.get("type", "string")
            required = bool(field_def.get("required", False))
            default = field_def.get("default")
            max_length = field_def.get("max_length")

            py_type = self._python_type_for_yaml(yaml_type, field_def)
            if not required:
                py_type = Union[py_type, type(None)]

            field_kwargs: dict[str, Any] = {}
            if max_length:
                field_kwargs["max_length"] = max_length

            # Handle required vs optional fields properly
            if required and default is None:
                # Required field with no default
                field_info = Field(..., **field_kwargs)
            elif default is not None:
                # Field with default value (optional)
                field_kwargs["default"] = default
                field_info = Field(**field_kwargs)
            else:
                # Optional field with no default (None)
                field_kwargs["default"] = None
                field_info = Field(**field_kwargs)

            model_fields[field_name] = (py_type, field_info)

        model_name = f"{spec.name.capitalize()}Entity"
        model = create_model(model_name, **model_fields)

        # Cache the model to avoid recreating it
        self._model_cache[entity_name] = model
        return model


@lru_cache(maxsize=1)
def get_yaml_translator() -> YamlTranslator:
    return YamlTranslator()


def build_anchor_text(memory) -> str:
    return get_yaml_translator().build_anchor_text(memory)


def create_memory_from_yaml(memory_type: str, payload: dict[str, Any], user_id: str):
    return get_yaml_translator().create_memory_from_yaml(memory_type, payload, user_id)


# Convenience shim


def get_entity_model(entity_name: str):
    """Module-level helper that uses the cached global translator."""
    return get_yaml_translator().get_entity_model(entity_name)
