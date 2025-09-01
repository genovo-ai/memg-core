"""Centralized type registry for MEMG Core.

SINGLE SOURCE OF TRUTH for all YAML-derived types.
One YAML orchestrates everything - this module enforces that principle.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, create_model
import yaml


class TypeRegistry:
    """Singleton registry for all YAML-derived types.

    CRITICAL: Initialize once from YAML, use everywhere.
    NO defaults, NO fallbacks - crash early if YAML incomplete.

    Attributes:
        _instance: Singleton instance.
        _initialized: Whether registry has been initialized.
        _entity_types: EntityType enum.
        _relation_predicates: RelationPredicate enum.
        _pydantic_models: Dictionary of Pydantic models.
        _yaml_schema: Raw YAML schema.
    """

    _instance: Optional["TypeRegistry"] = None
    _initialized: bool = False

    def __init__(self) -> None:
        self._entity_types: type[Enum] | None = None
        self._relation_predicates: type[Enum] | None = None
        self._pydantic_models: dict[str, type[BaseModel]] = {}
        self._yaml_schema: dict[str, Any] | None = None

    @classmethod
    def get_instance(cls) -> "TypeRegistry":
        """Get singleton instance - crashes if not initialized.

        Returns:
            TypeRegistry: Singleton instance.

        Raises:
            RuntimeError: If instance not created.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize_from_yaml(cls, yaml_path: str) -> "TypeRegistry":
        """One-time initialization from YAML.

        CRASHES IMMEDIATELY if YAML is incomplete or missing required fields.
        This is INTENTIONAL - no defaults, no fallbacks.

        Args:
            yaml_path: Path to YAML schema file.

        Returns:
            TypeRegistry: Initialized singleton instance.

        Raises:
            RuntimeError: If YAML loading fails.
            ValueError: If YAML structure is invalid.
        """
        instance = cls.get_instance()

        if cls._initialized:
            return instance

        # Load and validate YAML structure
        try:
            with open(yaml_path, encoding="utf-8") as f:
                raw_yaml = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load YAML from {yaml_path}: {e}") from e

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

    def _build_entity_types(self) -> None:
        """Build EntityType enum dynamically from YAML entities."""
        if self._yaml_schema is None:
            raise RuntimeError("YAML schema not loaded")
        schema = self._yaml_schema
        if not isinstance(schema, dict):
            raise RuntimeError("YAML schema must be a dict")
        schema_dict: dict[str, Any] = schema
        entities_obj = schema_dict.get("entities")
        if not isinstance(entities_obj, list):
            raise ValueError("YAML 'entities' section must be a list")
        entities = entities_obj

        # Extract entity names - crash if any entity missing 'name'
        entity_names = []
        for entity in entities:
            if "name" not in entity:
                raise ValueError(f"Entity missing required 'name' field: {entity}")
            entity_names.append((entity["name"].upper(), entity["name"]))

        if not entity_names:
            raise ValueError("No valid entity names found in YAML")

        # Create dynamic enum - use type ignore for mypy since this is runtime dynamic
        self._entity_types = Enum("EntityType", entity_names)  # type: ignore[misc]

    def _build_relation_predicates(self) -> None:
        """Build RelationPredicate enum dynamically from YAML relations.

        Supports both legacy list format and new target-first mapping format.
        Legacy format example under an entity:
            relations:
              - name: ...
                predicates: [FIXES]
                source: solution
                target: bug

        New format example under an entity:
            relations:
              bug:
                - name: solution_fixes_bug
                  predicate: FIXES
                  directed: true
        """
        if self._yaml_schema is None:
            raise RuntimeError("YAML schema not loaded")
        schema = self._yaml_schema
        if not isinstance(schema, dict):
            raise RuntimeError("YAML schema must be a dict")
        schema_dict: dict[str, Any] = schema
        entities_obj = schema_dict.get("entities")
        if not isinstance(entities_obj, list):
            raise ValueError("YAML 'entities' section must be a list")
        entities = entities_obj
        predicates = set()

        # Extract all predicates from all entity relations (supports 2 formats)
        for entity in entities:
            entity_name = entity.get("name", "<unknown>")
            relations_section = entity.get("relations")

            if relations_section is None:
                continue

            # New target-first format: mapping target -> list[relation]
            if isinstance(relations_section, dict):
                if not relations_section:
                    continue
                for _target, items in relations_section.items():
                    if not isinstance(items, list):
                        raise ValueError(
                            f"Invalid relations format for entity {entity_name}: "
                            "expected list under target"
                        )
                    for item in items:
                        if not isinstance(item, dict):
                            raise ValueError(
                                f"Invalid relation item in entity {entity_name}: {item}"
                            )
                        if "predicate" not in item:
                            raise ValueError(
                                f"Relation missing 'predicate' field in entity "
                                f"{entity_name}: {item}"
                            )
                        pred = item["predicate"]
                        if not isinstance(pred, str) or not pred:
                            raise ValueError(
                                f"Invalid 'predicate' value in entity {entity_name}: {item}"
                            )
                        predicates.add(pred.upper())

            # Legacy list format: list of relation dicts with 'predicates' list
            elif isinstance(relations_section, list):
                for relation in relations_section:
                    if "predicates" not in relation:
                        raise ValueError(
                            f"Relation missing 'predicates' field in entity "
                            f"{entity_name}: {relation}"
                        )

                    relation_predicates = relation["predicates"]
                    if not relation_predicates:
                        raise ValueError(
                            f"Empty 'predicates' list in relation {relation.get('name', 'unnamed')}"
                        )

                    for p in relation_predicates:
                        if not isinstance(p, str) or not p:
                            raise ValueError(
                                f"Invalid predicate value in entity "
                                f"{entity_name}: {relation_predicates}"
                            )
                        predicates.add(p.upper())

            else:
                raise ValueError(
                    f"Invalid 'relations' type for entity {entity_name}: "
                    f"{type(relations_section).__name__}"
                )

        if not predicates:
            raise ValueError(
                "YAML schema must define at least one relation with predicates. "
                "No defaults allowed."
            )

        # Create dynamic enum - use type ignore for mypy since this is runtime dynamic
        predicate_items = [(p, p) for p in sorted(predicates)]
        self._relation_predicates = Enum("RelationPredicate", predicate_items)  # type: ignore[misc]

    def _build_pydantic_models(self) -> None:
        """Build Pydantic models dynamically from YAML entities with inheritance support."""
        if self._yaml_schema is None:
            raise RuntimeError("YAML schema not loaded")
        schema = self._yaml_schema
        if not isinstance(schema, dict):
            raise RuntimeError("YAML schema must be a dict")
        schema_dict: dict[str, Any] = schema
        entities_obj = schema_dict.get("entities")
        if not isinstance(entities_obj, list):
            raise ValueError("YAML 'entities' section must be a list")
        entities = entities_obj

        # Build entity lookup for inheritance resolution
        entity_lookup = {entity["name"]: entity for entity in entities}

        for entity in entities:
            entity_name = entity["name"]

            # Validate required fields - crash if missing
            if "fields" not in entity:
                raise ValueError(f"Entity '{entity_name}' missing required 'fields' section")

            # Build Pydantic model fields with inheritance
            model_fields = self._resolve_entity_fields(entity, entity_lookup)

            # Create dynamic Pydantic model
            model_name = f"{entity_name.capitalize()}Entity"
            model = create_model(model_name, **model_fields)
            self._pydantic_models[entity_name] = model

    def _resolve_entity_fields(
        self, entity: dict[str, Any], entity_lookup: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Resolve entity fields with inheritance - parent fields first, then child fields."""
        model_fields = {}

        # If entity has a parent, resolve parent fields first
        parent_name = entity.get("parent")
        if parent_name:
            if parent_name not in entity_lookup:
                raise ValueError(
                    f"Entity '{entity['name']}' references unknown parent '{parent_name}'"
                )
            parent_entity = entity_lookup[parent_name]
            # Recursively resolve parent fields (supports multi-level inheritance)
            parent_fields = self._resolve_entity_fields(parent_entity, entity_lookup)
            model_fields.update(parent_fields)

        # Add/override with current entity's fields
        for field_name, field_def in entity["fields"].items():
            if "type" not in field_def:
                raise ValueError(
                    f"Field '{field_name}' in entity '{entity['name']}' missing 'type'"
                )

            field_type = field_def["type"]
            required = field_def.get("required", False)
            default_value = field_def.get("default")

            # Handle field requirements and defaults
            if required:
                model_fields[field_name] = (
                    self._get_python_type(field_type, field_def),
                    Field(...),
                )
            elif default_value is not None:
                # Use YAML-defined default
                model_fields[field_name] = (
                    self._get_python_type(field_type, field_def),
                    Field(default=default_value),
                )
            else:
                # Optional field with None default
                model_fields[field_name] = (
                    self._get_python_type(field_type, field_def),
                    Field(default=None),
                )

        return model_fields

    def _get_python_type(self, yaml_type: str, field_def: dict[str, Any]) -> Any:
        """Convert YAML type to Python type - crash on unknown types."""
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
        """Get EntityType enum - crashes if not initialized.

        Returns:
            type[Enum]: EntityType enum class.

        Raises:
            RuntimeError: If TypeRegistry not initialized.
        """
        if self._entity_types is None:
            raise RuntimeError("TypeRegistry not initialized - call initialize_from_yaml() first")
        return self._entity_types

    def get_relation_predicate_enum(self) -> type[Enum]:
        """Get RelationPredicate enum - crashes if not initialized."""
        if self._relation_predicates is None:
            raise RuntimeError("TypeRegistry not initialized - call initialize_from_yaml() first")
        return self._relation_predicates

    def get_entity_model(self, entity_name: str) -> type[BaseModel]:
        """Get Pydantic model for entity - crashes if not found.

        Args:
            entity_name: Name of the entity.

        Returns:
            type[BaseModel]: Pydantic model class.

        Raises:
            ValueError: If entity model not found.
        """
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
        """Validate entity type against YAML schema.

        Args:
            entity_type: Entity type to validate.

        Returns:
            bool: True if entity type is valid.
        """
        valid_names = self.get_valid_entity_names()
        return entity_type in valid_names

    def validate_relation_predicate(self, predicate: str) -> bool:
        """Validate relation predicate against YAML schema.

        Args:
            predicate: Relation predicate to validate.

        Returns:
            bool: True if predicate is valid.
        """
        valid_predicates = self.get_valid_predicates()
        return predicate in valid_predicates


# Global convenience functions - use these throughout the codebase


def get_entity_type_enum() -> type[Enum]:
    """Get EntityType enum from global registry.

    Returns:
        type[Enum]: EntityType enum class.
    """
    return TypeRegistry.get_instance().get_entity_type_enum()


def get_relation_predicate_enum() -> type[Enum]:
    """Get RelationPredicate enum from global registry.

    Returns:
        type[Enum]: RelationPredicate enum class.
    """
    return TypeRegistry.get_instance().get_relation_predicate_enum()


def get_entity_model(entity_name: str) -> type[BaseModel]:
    """Get Pydantic model for entity from global registry.

    Args:
        entity_name: Name of the entity.

    Returns:
        type[BaseModel]: Pydantic model class.
    """
    return TypeRegistry.get_instance().get_entity_model(entity_name)


def validate_entity_type(entity_type: str) -> bool:
    """Validate entity type against global registry.

    Args:
        entity_type: Entity type to validate.

    Returns:
        bool: True if entity type is valid.
    """
    return TypeRegistry.get_instance().validate_entity_type(entity_type)


def validate_relation_predicate(predicate: str) -> bool:
    """Validate relation predicate against global registry.

    Args:
        predicate: Relation predicate to validate.

    Returns:
        bool: True if predicate is valid.
    """
    return TypeRegistry.get_instance().validate_relation_predicate(predicate)


def initialize_types_from_yaml(yaml_path: str) -> None:
    """Initialize global type registry from YAML - call once at startup.

    Args:
        yaml_path: Path to YAML schema file.
    """
    TypeRegistry.initialize_from_yaml(yaml_path)
