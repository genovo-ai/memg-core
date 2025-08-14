"""YAML to Memory translator - converts YAML entity definitions to current Memory model"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel
import yaml

from .exceptions import MemorySystemError
from .models import Memory


class YamlTranslatorError(MemorySystemError):
    """YAML translator specific errors"""

    pass


class EntitySpec(BaseModel):
    """Entity specification from YAML"""

    name: str
    description: str
    anchor: str
    fields: dict[str, Any]


class YamlTranslator:
    """Translates YAML entity definitions into current Memory model"""

    def __init__(self, yaml_path: str | None = None):
        self.yaml_path = yaml_path or os.getenv("MEMG_YAML_SCHEMA")
        self._schema: dict[str, Any] | None = None

    @property
    def schema(self) -> dict[str, Any]:
        """Load and cache YAML schema"""
        if self._schema is None:
            self._schema = self._load_schema()
        return self._schema

    def _load_schema(self) -> dict[str, Any]:
        """Load YAML schema from file"""
        if not self.yaml_path:
            raise YamlTranslatorError("No YAML schema path provided")

        path = Path(self.yaml_path)
        if not path.exists():
            raise YamlTranslatorError(f"YAML schema file not found: {self.yaml_path}")

        try:
            with open(path, encoding="utf-8") as f:
                schema = yaml.safe_load(f)
            if not schema:
                raise YamlTranslatorError("Empty YAML schema")
            return schema
        except yaml.YAMLError as e:
            raise YamlTranslatorError(f"Invalid YAML syntax: {e}") from e
        except Exception as e:
            raise YamlTranslatorError(f"Failed to load YAML schema: {e}") from e

    def get_entity_spec(self, entity_name: str) -> EntitySpec:
        """Get entity specification from YAML"""
        entities = self.schema.get("entities", [])
        for entity in entities:
            if entity.get("name") == entity_name:
                return EntitySpec(**entity)
        raise YamlTranslatorError(f"Entity '{entity_name}' not found in YAML schema")

    def get_anchor_field(self, entity_name: str) -> str:
        """Get anchor field for entity type"""
        spec = self.get_entity_spec(entity_name)
        return spec.anchor

    def build_anchor_text(self, memory: Memory) -> str:
        """Build anchor text from Memory using YAML definition"""
        entity_name = str(memory.memory_type)

        try:
            anchor_field = self.get_anchor_field(entity_name)
        except YamlTranslatorError:
            # Fallback for unknown types - try common fields
            if "content" in memory.payload:
                return str(memory.payload["content"])
            if "summary" in memory.payload:
                return str(memory.payload["summary"])
            raise YamlTranslatorError(
                f"Unknown entity type '{entity_name}' and no fallback text found"
            )

        # Get anchor field value from memory payload
        anchor_value = memory.payload.get(anchor_field)
        if anchor_value and isinstance(anchor_value, str) and anchor_value.strip():
            return anchor_value.strip()

        # Fallback strategies
        if anchor_field == "summary" and "content" in memory.payload:
            content_val = memory.payload.get("content")
            if content_val and isinstance(content_val, str) and content_val.strip():
                return content_val.strip()

        if "content" in memory.payload:
            content_val = memory.payload.get("content")
            if content_val and isinstance(content_val, str) and content_val.strip():
                return content_val.strip()

        raise YamlTranslatorError(f"No valid anchor text found for memory {memory.id}")

    def validate_memory_against_yaml(
        self, memory_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate memory payload against YAML entity specification"""
        try:
            spec = self.get_entity_spec(memory_type)
        except YamlTranslatorError:
            # If entity not in YAML, return payload as-is
            return payload

        validated = {}

        # Check each field in the spec
        for field_name, field_spec in spec.fields.items():
            if field_spec.get("system", False):
                # Skip system fields - they're managed by core
                continue

            is_required = field_spec.get("required", False)
            field_type = field_spec.get("type", "string")

            if field_name in payload:
                value = payload[field_name]

                # Validate enum types
                if field_type == "enum":
                    choices = field_spec.get("choices", [])
                    if choices and value not in choices:
                        raise YamlTranslatorError(
                            f"Invalid value '{value}' for enum field '{field_name}'. "
                            f"Must be one of: {choices}"
                        )

                validated[field_name] = value
            elif "default" in field_spec:
                validated[field_name] = field_spec["default"]
            elif is_required:
                raise YamlTranslatorError(
                    f"Required field '{field_name}' missing for entity '{memory_type}'"
                )

        return validated

    def create_memory_from_yaml(
        self, memory_type: str, payload: dict[str, Any], user_id: str
    ) -> Memory:
        """Create Memory object from YAML-validated payload"""
        # Validate payload against YAML spec
        validated_payload = self.validate_memory_against_yaml(memory_type, payload)

        # Extract core fields from payload (don't duplicate them)
        core_tags = validated_payload.pop("tags", [])
        core_confidence = validated_payload.pop("confidence", 0.8)

        # Build Memory object with core fields + validated payload
        return Memory(
            user_id=user_id,
            memory_type=memory_type,
            payload=validated_payload,  # All entity-specific fields
            tags=core_tags,
            confidence=core_confidence,
        )


# Global translator instance
@lru_cache(maxsize=1)
def get_yaml_translator() -> YamlTranslator:
    """Get cached YAML translator instance"""
    return YamlTranslator()


def build_anchor_text(memory: Memory) -> str:
    """Build anchor text for memory using YAML translator"""
    translator = get_yaml_translator()
    return translator.build_anchor_text(memory)


def create_memory_from_yaml(memory_type: str, payload: dict[str, Any], user_id: str) -> Memory:
    """Create Memory from YAML-defined type and payload"""
    translator = get_yaml_translator()
    return translator.create_memory_from_yaml(memory_type, payload, user_id)
