"""YAML Translator: validates payloads using TypeRegistry and resolves anchor text.

STRICT YAML-FIRST: This module enforces the single-YAML-orchestrates-everything principle.
NO flexibility, NO migration support, NO fallbacks.

Uses TypeRegistry as SINGLE SOURCE OF TRUTH for all entity definitions.
All type building and validation delegated to TypeRegistry - zero redundancy.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

import yaml

from .exceptions import MemorySystemError
from .types import initialize_types_from_yaml


class YamlTranslatorError(MemorySystemError):
    """Error in YAML schema translation or validation."""

    pass


# EntitySpec REMOVED - TypeRegistry handles all entity specifications
# NO REDUNDANCY - all type definitions centralized in TypeRegistry


class YamlTranslator:
    """Translates YAML schema definitions to Pydantic models for strict validation."""

    def __init__(self, yaml_path: str | None = None) -> None:
        # Require explicit YAML path - no silent defaults
        if yaml_path:
            self.yaml_path = yaml_path
        else:
            env_path = os.getenv("MEMG_YAML_SCHEMA")
            if not env_path:
                raise YamlTranslatorError(
                    "YAML schema path required. Set MEMG_YAML_SCHEMA environment variable "
                    "or provide yaml_path parameter. No defaults allowed."
                )
            self.yaml_path = env_path

        self._schema: dict[str, Any] | None = None
        # NO model cache - TypeRegistry handles all caching

        # Initialize TypeRegistry from YAML - crash early if invalid
        try:
            initialize_types_from_yaml(self.yaml_path)
        except Exception as e:
            raise YamlTranslatorError(f"Failed to initialize TypeRegistry from YAML: {e}") from e

    @property
    def schema(self) -> dict[str, Any]:
        if self._schema is not None:
            return self._schema

        # Load schema from the required path - no fallbacks
        if not self.yaml_path:
            raise YamlTranslatorError(
                "YAML schema path not set. This should not happen after __init__."
            )

        self._schema = self._load_schema()
        return self._schema

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

    def get_anchor_field(self, entity_name: str) -> str:
        """Get the anchor field name for the given entity type from YAML schema."""
        if not entity_name:
            raise YamlTranslatorError("Empty entity name")
        name_l = entity_name.lower()
        emap = self._entities_map()
        spec_raw = emap.get(name_l)
        if not spec_raw:
            raise YamlTranslatorError(f"Entity '{entity_name}' not found in YAML schema")

        # Read anchor field from YAML schema - NO hardcoding
        anchor = spec_raw.get("anchor")
        if not anchor:
            raise YamlTranslatorError(
                f"Entity '{entity_name}' missing required 'anchor' field in YAML schema"
            )
        return str(anchor)

    def get_see_also_config(self, entity_name: str) -> dict[str, Any] | None:
        """Get the see_also configuration for the given entity type from YAML schema.

        Returns:
            Dict with keys: enabled, threshold, limit, target_types
            None if see_also is not configured for this entity
        """
        if not entity_name:
            raise YamlTranslatorError("Empty entity name")
        name_l = entity_name.lower()
        emap = self._entities_map()
        spec_raw = emap.get(name_l)
        if not spec_raw:
            raise YamlTranslatorError(f"Entity '{entity_name}' not found in YAML schema")

        see_also = spec_raw.get("see_also")
        if not see_also or not isinstance(see_also, dict):
            return None

        # Validate required fields
        if not see_also.get("enabled", False):
            return None

        return {
            "enabled": see_also.get("enabled", False),
            "threshold": float(see_also.get("threshold", 0.7)),
            "limit": int(see_also.get("limit", 3)),
            "target_types": list(see_also.get("target_types", [])),
        }

    def build_anchor_text(self, memory) -> str:
        """
        Builds anchor text for embedding from YAML-defined anchor field.
        NO hardcoded field names - reads anchor field from YAML schema.
        """
        mem_type = getattr(memory, "memory_type", None)
        if not mem_type:
            raise YamlTranslatorError(
                "Memory object missing 'memory_type' field", operation="build_anchor_text"
            )

        # Get anchor field from YAML schema
        anchor_field = self.get_anchor_field(mem_type)

        # Try to get anchor text from the specified field
        anchor_text = None

        # First check if it's a core field on the Memory object
        if hasattr(memory, anchor_field):
            anchor_text = getattr(memory, anchor_field, None)
        # Otherwise check in the payload
        elif hasattr(memory, "payload") and isinstance(memory.payload, dict):
            anchor_text = memory.payload.get(anchor_field)

        if isinstance(anchor_text, str):
            stripped_text = anchor_text.strip()
            if stripped_text:
                return stripped_text

        # Anchor field missing, empty, or invalid
        raise YamlTranslatorError(
            f"Anchor field '{anchor_field}' is missing, empty, or invalid for memory type '{mem_type}'",
            operation="build_anchor_text",
            context={
                "memory_type": mem_type,
                "anchor_field": anchor_field,
                "anchor_value": anchor_text,
            },
        )

    def _fields_contract(self, spec: dict[str, Any]) -> tuple[list[str], list[str]]:
        # supports either fields: {required:[...], optional:[...]} OR flat dict
        fields = spec.get("fields") or {}
        if "required" in fields or "optional" in fields:
            req = [str(x) for x in fields.get("required", [])]
            opt = [str(x) for x in fields.get("optional", [])]
            return req, opt

        # In the flat dict case, all fields defined in YAML are considered optional
        # because the canonical 'statement' is now a code-owned field on the Memory model.
        # Required fields from YAML are enforced at the Pydantic model level.
        keys = list(fields.keys())
        return [], keys

    def validate_memory_against_yaml(
        self, memory_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if not memory_type:
            raise YamlTranslatorError("memory_type is required")
        if payload is None:
            raise YamlTranslatorError("payload is required")

        # Strict validation - entity type MUST exist in YAML
        emap = self._entities_map()
        spec = emap.get(memory_type.lower())
        if not spec:
            raise YamlTranslatorError(
                f"Unknown entity type '{memory_type}'. All types must be defined in YAML schema.",
                context={"memory_type": memory_type, "available_types": list(emap.keys())},
            )

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

        # Get anchor field from YAML schema
        anchor_field = self.get_anchor_field(memory_type)

        # Extract anchor text from payload
        anchor_text = payload.get(anchor_field)
        if not anchor_text or not isinstance(anchor_text, str):
            raise YamlTranslatorError(
                f"Missing or invalid anchor field '{anchor_field}' in payload for memory type '{memory_type}'"
            )

        # Validate full payload against YAML schema
        validated_payload = self.validate_memory_against_yaml(memory_type, payload)

        # Construct Memory with YAML-defined payload only
        return Memory(
            memory_type=memory_type,
            payload=validated_payload,
            user_id=user_id,
        )

    def get_entity_model(self, entity_name: str):
        """Get Pydantic model from TypeRegistry - NO REDUNDANCY."""
        from .types import get_entity_model

        return get_entity_model(entity_name)


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


def get_see_also_config(entity_name: str) -> dict[str, Any] | None:
    """Module-level helper that uses the cached global translator."""
    return get_yaml_translator().get_see_also_config(entity_name)
