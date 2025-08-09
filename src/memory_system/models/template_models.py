"""
Template-aware models for MEMG - Dynamic entity and relationship types
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from ..templates.registry import get_template_registry

logger = logging.getLogger(__name__)


class TemplateAwareEntity(BaseModel):
    """Template-aware entity that validates against current template"""

    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for entity isolation")
    name: str = Field(..., description="Entity name")
    type: str = Field(
        ..., description="Entity type (validated against current template)"
    )
    description: str = Field(..., description="Entity description")
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Backward compatibility fields
    is_valid: bool = Field(True)
    source_memory_id: Optional[str] = Field(None, description="Source memory ID")

    # Template-specific fields
    importance: Optional[str] = Field("MEDIUM", description="Entity importance level")
    context: Optional[str] = Field(None, description="Entity context information")
    category: Optional[str] = Field(None, description="Entity category")

    @validator("type")
    def validate_entity_type(cls, v):
        """Validate entity type against current template"""
        try:
            registry = get_template_registry()
            current_template = registry.get_current_template()

            if not current_template:
                logger.warning(f"No current template found, accepting entity type: {v}")
                return v

            valid_types = current_template.get_entity_type_names()
            if v not in valid_types:
                raise ValueError(
                    f"Invalid entity type '{v}' for template '{current_template.name}'. "
                    f"Valid types: {valid_types}"
                )

            return v

        except Exception as e:
            logger.error(f"Error validating entity type '{v}': {e}")
            # In case of error, allow the type but log the issue
            return v

    def get_type_definition(self):
        """Get the template definition for this entity type"""
        try:
            registry = get_template_registry()
            current_template = registry.get_current_template()

            if current_template:
                return current_template.get_entity_type_by_name(self.type)
            return None

        except Exception as e:
            logger.error(f"Error getting type definition for '{self.type}': {e}")
            return None

    def to_kuzu_node(self) -> Dict[str, Any]:
        """Convert to Kuzu node properties"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "is_valid": self.is_valid,
            "source_memory_id": self.source_memory_id,
            "importance": self.importance,
            "context": self.context or "",
            "category": self.category or "",
        }


class TemplateAwareRelationship(BaseModel):
    """Template-aware relationship that validates against current template"""

    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for relationship isolation")
    source_entity_id: str = Field(..., description="Source entity ID")
    target_entity_id: str = Field(..., description="Target entity ID")
    type: str = Field(
        ..., description="Relationship type (validated against current template)"
    )
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Backward compatibility fields
    is_valid: bool = Field(True)
    source_memory_id: Optional[str] = Field(None, description="Source memory ID")

    # Template-specific fields
    strength: Optional[str] = Field("MODERATE", description="Relationship strength")
    context: Optional[str] = Field(None, description="Relationship context")
    directionality: Optional[str] = Field(
        None, description="Relationship directionality"
    )

    @validator("type")
    def validate_relationship_type(cls, v):
        """Validate relationship type against current template"""
        try:
            registry = get_template_registry()
            current_template = registry.get_current_template()

            if not current_template:
                logger.warning(
                    f"No current template found, accepting relationship type: {v}"
                )
                return v

            valid_types = current_template.get_relationship_type_names()
            if v not in valid_types:
                raise ValueError(
                    f"Invalid relationship type '{v}' for template '{current_template.name}'. "
                    f"Valid types: {valid_types}"
                )

            return v

        except Exception as e:
            logger.error(f"Error validating relationship type '{v}': {e}")
            # In case of error, allow the type but log the issue
            return v

    def get_type_definition(self):
        """Get the template definition for this relationship type"""
        try:
            registry = get_template_registry()
            current_template = registry.get_current_template()

            if current_template:
                return current_template.get_relationship_type_by_name(self.type)
            return None

        except Exception as e:
            logger.error(f"Error getting type definition for '{self.type}': {e}")
            return None

    def to_kuzu_props(self) -> Dict[str, Any]:
        """Convert to Kuzu relationship properties"""
        return {
            "user_id": self.user_id,
            "relationship_type": self.type,  # Map 'type' to 'relationship_type' for compatibility
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "is_valid": self.is_valid,
            "strength": self.strength,
            "context": self.context or "",
            "source_memory_id": self.source_memory_id,
        }


def validate_entity_type(entity_type: str) -> bool:
    """Validate if an entity type is valid for the current template"""
    try:
        registry = get_template_registry()
        current_template = registry.get_current_template()

        if not current_template:
            return True  # Accept any type if no template

        return entity_type in current_template.get_entity_type_names()

    except Exception as e:
        logger.error(f"Error validating entity type '{entity_type}': {e}")
        return True  # Default to accepting in case of error


def validate_relationship_type(relationship_type: str) -> bool:
    """Validate if a relationship type is valid for the current template"""
    try:
        registry = get_template_registry()
        current_template = registry.get_current_template()

        if not current_template:
            return True  # Accept any type if no template

        return relationship_type in current_template.get_relationship_type_names()

    except Exception as e:
        logger.error(f"Error validating relationship type '{relationship_type}': {e}")
        return True  # Default to accepting in case of error


def get_valid_entity_types() -> List[str]:
    """Get list of valid entity types for current template"""
    try:
        registry = get_template_registry()
        current_template = registry.get_current_template()

        if current_template:
            return current_template.get_entity_type_names()
        return []

    except Exception as e:
        logger.error(f"Error getting valid entity types: {e}")
        return []


def get_valid_relationship_types() -> List[str]:
    """Get list of valid relationship types for current template"""
    try:
        registry = get_template_registry()
        current_template = registry.get_current_template()

        if current_template:
            return current_template.get_relationship_type_names()
        return []

    except Exception as e:
        logger.error(f"Error getting valid relationship types: {e}")
        return []


# Backward compatibility functions to mimic enum behavior
class DynamicEntityType:
    """Dynamic entity type that behaves like an enum but uses template data"""

    @classmethod
    def __call__(cls, value: str) -> str:
        """Convert string to validated entity type"""
        if validate_entity_type(value):
            return value
        else:
            # For backward compatibility, still return the value but log warning
            logger.warning(f"Entity type '{value}' not found in current template")
            return value

    @classmethod
    def values(cls) -> List[str]:
        """Get all valid entity type values"""
        return get_valid_entity_types()


class DynamicRelationshipType:
    """Dynamic relationship type that behaves like an enum but uses template data"""

    @classmethod
    def __call__(cls, value: str) -> str:
        """Convert string to validated relationship type"""
        if validate_relationship_type(value):
            return value
        else:
            # For backward compatibility, still return the value but log warning
            logger.warning(f"Relationship type '{value}' not found in current template")
            return value

    @classmethod
    def values(cls) -> List[str]:
        """Get all valid relationship type values"""
        return get_valid_relationship_types()


# Create instances for backward compatibility
EntityType = DynamicEntityType()
RelationshipType = DynamicRelationshipType()
