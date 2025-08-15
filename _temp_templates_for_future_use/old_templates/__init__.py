"""
Template system for MEMG - Enables use-case specific entity types and relationships
"""

from .base import (
    EntityTypeDefinition,
    MemoryTemplate,
    RelationshipTypeDefinition,
    TemplateValidationError,
)
from .default import DEFAULT_TEMPLATE
from .registry import TemplateRegistry, get_template_registry

__all__ = [
    "EntityTypeDefinition",
    "RelationshipTypeDefinition",
    "MemoryTemplate",
    "TemplateValidationError",
    "TemplateRegistry",
    "get_template_registry",
    "DEFAULT_TEMPLATE",
]
