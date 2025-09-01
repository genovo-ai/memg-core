"""YAML Translator: validates payloads using TypeRegistry and resolves anchor text.

STRICT YAML-FIRST: This module enforces the single-YAML-orchestrates-everything principle.
NO flexibility, NO migration support, NO fallbacks.

Uses TypeRegistry as SINGLE SOURCE OF TRUTH for all entity definitions.
All type building and validation delegated to TypeRegistry - zero redundancy.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .exceptions import MemorySystemError
from .types import initialize_types_from_yaml


class YamlTranslatorError(MemorySystemError):
    """Error in YAML schema translation or validation.

    Attributes:
        message: Error message.
        operation: Operation that caused the error.
        context: Additional context information.
        original_error: Original exception that was wrapped.
    """

    pass


class YamlTranslator:
    """Translates YAML schema definitions to Pydantic models for strict validation.

    Attributes:
        yaml_path: Path to YAML schema file.
        _schema: Cached schema dictionary.
    """

    def __init__(self, yaml_path: str | None = None) -> None:
        """Initialize YamlTranslator with YAML schema path.

        Args:
            yaml_path: Path to YAML schema file. If None, uses MEMG_YAML_SCHEMA env var.

        Raises:
            YamlTranslatorError: If YAML path not provided or TypeRegistry initialization fails.
        """
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

    def get_entity_types(self) -> list[str]:
        """Get list of available entity types from YAML schema."""
        return list(self._entities_map().keys())

    # ================== RELATIONSHIP PARSING (TARGET-FIRST FORMAT) ==================

    def _get_relations_mapping_for_entity(
        self, entity_name: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Return raw relations mapping for an entity in target-first schema format.

        The expected YAML shape under an entity is:
            relations:
              target_entity_name:
                - name: ...
                  description: ...
                  predicate: PREDICATE_NAME
                  directed: true|false

        Returns an empty dict when no relations are defined.
        """
        entity_spec = self._resolve_entity_with_inheritance(entity_name)
        relations_section = entity_spec.get("relations")
        if not relations_section or not isinstance(relations_section, dict):
            return {}

        # Normalize keys to lower for targets; keep items as-is
        normalized: dict[str, list[dict[str, Any]]] = {}
        for target_name, items in relations_section.items():
            if not isinstance(items, list):
                # Skip invalid shapes silently at this layer; validation is higher-level
                continue
            normalized[str(target_name).lower()] = [i for i in items if isinstance(i, dict)]
        return normalized

    def get_relations_for_source(self, entity_name: str) -> list[dict[str, Any]]:
        """Get normalized relation specs for a source entity in target-first schema.

        Returns list of dicts with keys:
            - source (str)
            - target (str)
            - name (str | None)
            - description (str | None)
            - predicate (str)
            - directed (bool)
        """
        if not entity_name:
            raise YamlTranslatorError("Empty entity name")

        source_l = entity_name.lower()
        relations_map = self._get_relations_mapping_for_entity(source_l)
        if not relations_map:
            return []

        out: list[dict[str, Any]] = []
        for target_l, items in relations_map.items():
            for item in items:
                predicate = item.get("predicate")
                if not predicate or not isinstance(predicate, str):
                    # Skip invalid entries - strict behavior can be added later
                    continue
                directed = bool(item.get("directed", True))
                out.append(
                    {
                        "source": source_l,
                        "target": target_l,
                        "name": item.get("name"),
                        "description": item.get("description"),
                        "predicate": predicate.upper(),
                        "directed": directed,
                    }
                )
        return out

    @staticmethod
    def relationship_table_name(
        source: str, predicate: str, target: str, *, directed: bool = True
    ) -> str:
        """Generate relationship table name.

        For now, table name does not encode direction; direction affects creation/query semantics.
        Canonicalization for undirected pairs can be added here later if decided.
        """
        return f"{str(source).upper()}_{str(predicate).upper()}_{str(target).upper()}"

    def get_labels_for_predicates(
        self,
        source_type: str,
        predicates: list[str] | None,
        neighbor_label: str | None = None,
    ) -> list[str]:
        """Expand predicate names to concrete relationship labels for a given source.

        Args:
            source_type: Source entity type name
            predicates: List of predicate names to include (case-insensitive). If None, include all.
            neighbor_label: Optional target entity type filter (case-insensitive)

        Returns:
            List of concrete relationship labels (table names) matching the filter.
        """
        if not source_type:
            raise YamlTranslatorError("Empty source_type")

        preds_u = set(p.upper() for p in predicates) if predicates else None
        neighbor_l = neighbor_label.lower() if neighbor_label else None

        labels: list[str] = []
        for spec in self.get_relations_for_source(source_type):
            if preds_u is not None and spec["predicate"].upper() not in preds_u:
                continue
            if neighbor_l is not None and spec["target"].lower() != neighbor_l:
                continue
            labels.append(
                self.relationship_table_name(
                    source=spec["source"],
                    predicate=spec["predicate"],
                    target=spec["target"],
                    directed=spec["directed"],
                )
            )
        return labels

    def debug_relation_map(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Return a nested relation map for debugging/printing.

        Structure:
        {
          source: {
            target: [ {name, predicate, directed, description} ... ]
          }
        }
        """
        out: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for source in self.get_entity_types():
            specs = self.get_relations_for_source(source)
            if not specs:
                continue
            if source not in out:
                out[source] = {}
            for spec in specs:
                target = spec["target"]
                out[source].setdefault(target, [])
                out[source][target].append(
                    {
                        "name": spec.get("name"),
                        "predicate": spec.get("predicate"),
                        "directed": spec.get("directed", True),
                        "description": spec.get("description"),
                    }
                )
        return out

    def get_anchor_field(self, entity_name: str) -> str:
        """Get the anchor field name for the given entity type from YAML schema.

        Now reads from vector.anchored_to instead of separate anchor field.

        Args:
            entity_name: Name of the entity type.

        Returns:
            str: Anchor field name.

        Raises:
            YamlTranslatorError: If anchor field not found.
        """
        if not entity_name:
            raise YamlTranslatorError("Empty entity name")

        # Get entity spec with inheritance resolution
        entity_spec = self._resolve_entity_with_inheritance(entity_name)

        # Look for vector field with anchored_to
        fields = entity_spec.get("fields", {})
        for _field_name, field_def in fields.items():
            if isinstance(field_def, dict) and field_def.get("type") == "vector":
                anchored_to = field_def.get("anchored_to")
                if anchored_to:
                    return str(anchored_to)

        raise YamlTranslatorError(
            f"Entity '{entity_name}' has no vector field with 'anchored_to' property"
        )

    def _resolve_entity_with_inheritance(self, entity_name: str) -> dict[str, Any]:
        """Resolve entity specification with full inheritance chain."""
        name_l = entity_name.lower()
        emap = self._entities_map()
        spec_raw = emap.get(name_l)
        if not spec_raw:
            raise YamlTranslatorError(f"Entity '{entity_name}' not found in YAML schema")

        # If no parent, return as-is
        parent_name = spec_raw.get("parent")
        if not parent_name:
            return spec_raw

        # Recursively resolve parent and merge fields
        parent_spec = self._resolve_entity_with_inheritance(parent_name)

        # Merge parent fields with child fields (child overrides parent)
        merged_fields = parent_spec.get("fields", {}).copy()
        merged_fields.update(spec_raw.get("fields", {}))

        # Create merged spec
        merged_spec = spec_raw.copy()
        merged_spec["fields"] = merged_fields

        return merged_spec

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
        """Build anchor text for embedding from YAML-defined anchor field.

        NO hardcoded field names - reads anchor field from YAML schema.

        Args:
            memory: Memory object containing payload data.

        Returns:
            str: Anchor text for embedding.

        Raises:
            YamlTranslatorError: If anchor field is missing or invalid.
        """
        mem_type = getattr(memory, "memory_type", None)
        if not mem_type:
            raise YamlTranslatorError(
                "Memory object missing 'memory_type' field",
                operation="build_anchor_text",
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
            f"Anchor field '{anchor_field}' is missing, empty, or invalid "
            f"for memory type '{mem_type}'",
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

        # Parse individual field definitions for required flag
        required_fields = []
        optional_fields = []

        for field_name, field_def in fields.items():
            if isinstance(field_def, dict) and field_def.get("required", False):
                # Skip system fields - they're handled by the system
                if not field_def.get("system", False):
                    required_fields.append(field_name)
                else:
                    optional_fields.append(field_name)
            else:
                optional_fields.append(field_name)

        return required_fields, optional_fields

    def _validate_enum_fields(self, memory_type: str, payload: dict[str, Any]) -> None:
        """Validate enum fields against YAML schema choices.

        Args:
            memory_type: Entity type from YAML schema.
            payload: Memory data to validate.

        Raises:
            YamlTranslatorError: If enum field has invalid value.
        """
        emap = self._entities_map()
        spec = emap.get(memory_type.lower())
        if not spec:
            return  # Entity validation happens elsewhere

        # Get field definitions for this entity type
        fields = spec.get("fields", {})

        # Check each field in the payload
        for field_name, field_value in payload.items():
            if field_name in fields:
                field_def = fields[field_name]

                # Check if this is an enum field
                if field_def.get("type") == "enum":
                    choices = field_def.get("choices", [])

                    # Validate the value against choices
                    if field_value is not None and field_value not in choices:
                        raise YamlTranslatorError(
                            f"Invalid {field_name} value '{field_value}'. Valid choices: {choices}",
                            context={
                                "memory_type": memory_type,
                                "field_name": field_name,
                                "invalid_value": field_value,
                                "valid_choices": choices,
                            },
                        )

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
                context={
                    "memory_type": memory_type,
                    "available_types": list(emap.keys()),
                },
            )

        req, _opt = self._fields_contract(spec)
        missing = [k for k in req if not payload.get(k)]
        if missing:
            raise YamlTranslatorError(
                f"Missing required fields: {missing}",
                context={"memory_type": memory_type},
            )

        # Validate enum fields against YAML schema choices
        self._validate_enum_fields(memory_type, payload)

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
                f"Missing or invalid anchor field '{anchor_field}' in payload "
                f"for memory type '{memory_type}'"
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
