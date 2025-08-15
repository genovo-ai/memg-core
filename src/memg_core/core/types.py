"""
Centralized type registry for MEMG Core.

SINGLE SOURCE OF TRUTH for all YAML-derived types.
One YAML orchestrates everything - this module enforces that principle.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, create_model
import yaml


class TypeRegistry:
    """
    Singleton registry for all YAML-derived types.

    CRITICAL: Initialize once from YAML, use everywhere.
    NO defaults, NO fallbacks - crash early if YAML incomplete.
    """

    _instance: Optional["TypeRegistry"] = None
    _initialized: bool = False

    def __init__(self):
        self._entity_types: type[Enum] | None = None
        self._relation_predicates: type[Enum] | None = None
        self._pydantic_models: dict[str, type[BaseModel]] = {}
        self._yaml_schema: dict[str, Any] | None = None

    @classmethod
    def get_instance(cls) -> "TypeRegistry":
        """Get singleton instance - crashes if not initialized."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize_from_yaml(cls, yaml_path: str) -> "TypeRegistry":
        """
        One-time initialization from YAML.

        CRASHES IMMEDIATELY if YAML is incomplete or missing required fields.
        This is INTENTIONAL - no defaults, no fallbacks.
        """
        instance = cls.get_instance()

        if cls._initialized:
            return instance

        # Load and validate YAML structure
        try:
            with open(yaml_path) as f:
                raw_yaml = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load YAML from {yaml_path}: {e}")

        # Validate required top-level structure - crash if missing
        if "entities" not in raw_yaml:
            raise ValueError("YAML missing required 'entities' section")

        if not raw_yaml["entities"]:
            raise ValueError("YAML 'entities' section is empty")

        instance._yaml_schema = raw_yaml
        instance._build_entity_types()
        instance._build_relation_predicates()
        instance._build_pydantic_models()

        cls._initialized = True
        return instance

    def _build_entity_types(self):
        """Build EntityType enum dynamically from YAML entities."""
        if self._yaml_schema is None:
            raise RuntimeError("YAML schema not loaded")
        entities = self._yaml_schema["entities"]

        # Extract entity names - crash if any entity missing 'name'
        entity_names = []
        for entity in entities:
            if "name" not in entity:
                raise ValueError(f"Entity missing required 'name' field: {entity}")
            entity_names.append((entity["name"].upper(), entity["name"]))

        if not entity_names:
            raise ValueError("No valid entity names found in YAML")

        # Create dynamic enum
        self._entity_types = Enum("EntityType", entity_names)

    def _build_relation_predicates(self):
        """Build RelationPredicate enum dynamically from YAML relations."""
        if self._yaml_schema is None:
            raise RuntimeError("YAML schema not loaded")
        entities = self._yaml_schema["entities"]
        predicates = set()

        # Extract all predicates from all entity relations
        for entity in entities:
            relations = entity.get("relations", [])
            for relation in relations:
                if "predicates" not in relation:
                    raise ValueError(
                        f"Relation missing 'predicates' field in entity {entity['name']}: {relation}"
                    )

                relation_predicates = relation["predicates"]
                if not relation_predicates:
                    raise ValueError(
                        f"Empty 'predicates' list in relation {relation.get('name', 'unnamed')}"
                    )

                predicates.update(relation_predicates)

        if not predicates:
            raise ValueError(
                "YAML schema must define at least one relation with predicates. No defaults allowed."
            )

        # Create dynamic enum
        predicate_items = [(p, p) for p in sorted(predicates)]
        self._relation_predicates = Enum("RelationPredicate", predicate_items)

    def _build_pydantic_models(self):
        """Build Pydantic models dynamically from YAML entities."""
        if self._yaml_schema is None:
            raise RuntimeError("YAML schema not loaded")
        entities = self._yaml_schema["entities"]

        for entity in entities:
            entity_name = entity["name"]

            # Validate required fields - crash if missing
            if "fields" not in entity:
                raise ValueError(f"Entity '{entity_name}' missing required 'fields' section")

            if "anchor" not in entity:
                raise ValueError(f"Entity '{entity_name}' missing required 'anchor' field")

            # Build Pydantic model fields
            model_fields = {}

            for field_name, field_def in entity["fields"].items():
                if "type" not in field_def:
                    raise ValueError(
                        f"Field '{field_name}' in entity '{entity_name}' missing 'type'"
                    )

                field_type = field_def["type"]
                required = field_def.get("required", False)

                # NO DEFAULTS ALLOWED - if required=True and no value provided, it MUST crash
                if required:
                    model_fields[field_name] = (
                        self._get_python_type(field_type, field_def),
                        Field(...),
                    )
                else:
                    model_fields[field_name] = (
                        self._get_python_type(field_type, field_def),
                        Field(default=None),
                    )

            # Create dynamic Pydantic model
            model_name = f"{entity_name.capitalize()}Entity"
            model = create_model(model_name, **model_fields)
            self._pydantic_models[entity_name] = model

    def _get_python_type(self, yaml_type: str, field_def: dict[str, Any]) -> Any:
        """Convert YAML type to Python type - crash on unknown types."""
        from datetime import datetime
        from typing import Literal

        yaml_type = yaml_type.lower()

        if yaml_type == "string":
            return str
        if yaml_type == "datetime":
            return datetime
        if yaml_type == "enum":
            choices = field_def.get("choices")
            if not choices:
                raise ValueError(f"Enum field missing 'choices': {field_def}")
            return Literal[tuple(choices)]
        if yaml_type == "vector":
            return list[float]

        raise ValueError(f"Unknown YAML type: {yaml_type}")

    # Public accessors - crash if not initialized

    def get_entity_type_enum(self) -> type[Enum]:
        """Get EntityType enum - crashes if not initialized."""
        if self._entity_types is None:
            raise RuntimeError("TypeRegistry not initialized - call initialize_from_yaml() first")
        return self._entity_types

    def get_relation_predicate_enum(self) -> type[Enum]:
        """Get RelationPredicate enum - crashes if not initialized."""
        if self._relation_predicates is None:
            raise RuntimeError("TypeRegistry not initialized - call initialize_from_yaml() first")
        return self._relation_predicates

    def get_entity_model(self, entity_name: str) -> type[BaseModel]:
        """Get Pydantic model for entity - crashes if not found."""
        if entity_name not in self._pydantic_models:
            raise ValueError(f"No Pydantic model found for entity: {entity_name}")
        return self._pydantic_models[entity_name]

    def get_valid_entity_names(self) -> list[str]:
        """Get list of valid entity names from YAML."""
        if self._entity_types is None:
            raise RuntimeError("TypeRegistry not initialized")
        return [e.value for e in self._entity_types]

    def get_valid_predicates(self) -> list[str]:
        """Get list of valid relation predicates from YAML."""
        if self._relation_predicates is None:
            raise RuntimeError("TypeRegistry not initialized")
        return [p.value for p in self._relation_predicates]

    def validate_entity_type(self, entity_type: str) -> bool:
        """Validate entity type against YAML schema."""
        valid_names = self.get_valid_entity_names()
        return entity_type in valid_names

    def validate_relation_predicate(self, predicate: str) -> bool:
        """Validate relation predicate against YAML schema."""
        valid_predicates = self.get_valid_predicates()
        return predicate in valid_predicates


# Global convenience functions - use these throughout the codebase


def get_entity_type_enum() -> type[Enum]:
    """Get EntityType enum from global registry."""
    return TypeRegistry.get_instance().get_entity_type_enum()


def get_relation_predicate_enum() -> type[Enum]:
    """Get RelationPredicate enum from global registry."""
    return TypeRegistry.get_instance().get_relation_predicate_enum()


def get_entity_model(entity_name: str) -> type[BaseModel]:
    """Get Pydantic model for entity from global registry."""
    return TypeRegistry.get_instance().get_entity_model(entity_name)


def validate_entity_type(entity_type: str) -> bool:
    """Validate entity type against global registry."""
    return TypeRegistry.get_instance().validate_entity_type(entity_type)


def validate_relation_predicate(predicate: str) -> bool:
    """Validate relation predicate against global registry."""
    return TypeRegistry.get_instance().validate_relation_predicate(predicate)


def initialize_types_from_yaml(yaml_path: str) -> None:
    """Initialize global type registry from YAML - call once at startup."""
    TypeRegistry.initialize_from_yaml(yaml_path)
