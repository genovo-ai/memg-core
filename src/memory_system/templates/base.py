"""
Base template system for MEMG - Core classes for template definitions
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class TemplateValidationError(Exception):
    """Raised when template validation fails"""

    pass


@dataclass
class EntityTypeDefinition:
    """Definition of an entity type for a template"""

    name: str
    description: str
    category: str = "GENERAL"
    extraction_hints: Optional[List[str]] = None

    def __post_init__(self):
        """Validate entity type definition"""
        if not self.name or not self.name.isupper():
            raise TemplateValidationError(
                f"Entity type name must be uppercase: {self.name}"
            )
        if not re.match(r"^[A-Z][A-Z_]*$", self.name):
            raise TemplateValidationError(
                f"Entity type name must contain only uppercase letters and underscores: {self.name}"
            )
        if not self.description:
            raise TemplateValidationError(
                f"Entity type description is required: {self.name}"
            )


@dataclass
class RelationshipTypeDefinition:
    """Definition of a relationship type for a template"""

    name: str
    description: str
    directionality: str = "BIDIRECTIONAL"  # BIDIRECTIONAL, DIRECTIONAL
    strength_levels: Optional[List[str]] = None

    def __post_init__(self):
        """Validate relationship type definition"""
        if not self.name or not self.name.isupper():
            raise TemplateValidationError(
                f"Relationship type name must be uppercase: {self.name}"
            )
        if not re.match(r"^[A-Z][A-Z_]*$", self.name):
            raise TemplateValidationError(
                f"Relationship type name must contain only uppercase letters and \
        underscores: {self.name}"
            )
        if not self.description:
            raise TemplateValidationError(
                f"Relationship type description is required: {self.name}"
            )
        if self.directionality not in ["BIDIRECTIONAL", "DIRECTIONAL"]:
            raise TemplateValidationError(
                f"Invalid directionality: {self.directionality}"
            )


class MemoryTemplate(BaseModel):
    """Complete template definition for a use case"""

    name: str = Field(..., description="Template name (lowercase with underscores)")
    display_name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description")
    version: str = Field(..., description="Template version")

    entity_types: List[EntityTypeDefinition] = Field(
        ..., description="Entity type definitions"
    )
    relationship_types: List[RelationshipTypeDefinition] = Field(
        ..., description="Relationship type definitions"
    )

    extraction_prompts: Dict[str, str] = Field(
        default_factory=dict, description="Custom AI prompts"
    )
    search_filters: Dict[str, Any] = Field(
        default_factory=dict, description="Template-specific search configurations"
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional template metadata"
    )

    @validator("name")
    def validate_name(cls, v):
        if not re.match(r"^[a-z][a-z_]*$", v):
            raise ValueError("Template name must be lowercase with underscores")
        return v

    @validator("version")
    def validate_version(cls, v):
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("Version must follow semantic versioning (x.y.z)")
        return v

    @validator("entity_types")
    def validate_entity_types(cls, v):
        if not v:
            raise ValueError("Template must define at least one entity type")
        names = [et.name for et in v]
        if len(names) != len(set(names)):
            raise ValueError("Entity type names must be unique")
        return v

    @validator("relationship_types")
    def validate_relationship_types(cls, v):
        if not v:
            raise ValueError("Template must define at least one relationship type")
        names = [rt.name for rt in v]
        if len(names) != len(set(names)):
            raise ValueError("Relationship type names must be unique")
        return v

    def get_entity_type_names(self) -> List[str]:
        """Get list of entity type names"""
        return [et.name for et in self.entity_types]

    def get_relationship_type_names(self) -> List[str]:
        """Get list of relationship type names"""
        return [rt.name for rt in self.relationship_types]

    def get_entity_type_by_name(self, name: str) -> Optional[EntityTypeDefinition]:
        """Get entity type definition by name"""
        for et in self.entity_types:
            if et.name == name:
                return et
        return None

    def get_relationship_type_by_name(
        self, name: str
    ) -> Optional[RelationshipTypeDefinition]:
        """Get relationship type definition by name"""
        for rt in self.relationship_types:
            if rt.name == name:
                return rt
        return None

    def validate_template(self) -> None:
        """Comprehensive template validation"""
        try:
            # Validate all entity types
            for _ in self.entity_types:
                # EntityTypeDefinition.__post_init__ will validate
                pass

            # Validate all relationship types
            for _ in self.relationship_types:
                # RelationshipTypeDefinition.__post_init__ will validate
                pass

        except Exception as e:
            raise TemplateValidationError(f"Template validation failed: {e}")
