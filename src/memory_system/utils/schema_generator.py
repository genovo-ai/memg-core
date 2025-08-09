"""
Dynamic JSON schema generation from templates for MEMG
"""

import logging
from typing import Any, Dict

from ..templates.base import MemoryTemplate

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """Generates JSON schemas dynamically from template definitions"""

    def __init__(self, template: MemoryTemplate):
        self.template = template

    def generate_entity_relationship_extraction_schema(self) -> Dict[str, Any]:
        """Generate the entity_relationship_extraction schema from template"""

        # Get entity type names from template
        entity_type_names = self.template.get_entity_type_names()

        # Get relationship type names from template
        relationship_type_names = self.template.get_relationship_type_names()

        schema = {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": entity_type_names,
                            },
                            "description": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                            },
                            "context": {"type": "string"},
                        },
                        "required": ["name", "type", "description", "confidence"],
                    },
                },
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "target": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": relationship_type_names,
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "strength": {
                                "type": "string",
                                "enum": ["WEAK", "MODERATE", "STRONG", "ESSENTIAL"],
                            },
                            "context": {"type": "string"},
                        },
                        "required": ["source", "target", "type", "confidence"],
                    },
                },
            },
            "required": ["entities", "relationships"],
        }

        return schema

    def generate_all_schemas(self) -> Dict[str, Any]:
        """Generate all schemas for the template"""

        # Start with the base schemas that don't change
        base_schemas = {
            "memory_list": {
                "type": "object",
                "properties": {
                    "memories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                                "memory_type": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["title", "content"],
                        },
                    },
                },
                "required": ["memories"],
            },
            "content_analysis": {
                "type": "object",
                "properties": {
                    "content_type": {"type": "string"},
                    "main_themes": {"type": "array", "items": {"type": "string"}},
                    "key_insights": {"type": "array", "items": {"type": "string"}},
                    "actionable_items": {"type": "array", "items": {"type": "string"}},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "complexity": {"type": "string"},
                            "domain": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                    },
                },
                "required": ["content_type", "main_themes"],
            },
        }

        # Add the template-specific entity/relationship extraction schema
        base_schemas["entity_relationship_extraction"] = (
            self.generate_entity_relationship_extraction_schema()
        )

        return base_schemas

    def get_entity_type_descriptions(self) -> Dict[str, str]:
        """Get entity type descriptions for AI prompts"""
        descriptions = {}
        for entity_type in self.template.entity_types:
            descriptions[entity_type.name] = entity_type.description
        return descriptions

    def get_relationship_type_descriptions(self) -> Dict[str, str]:
        """Get relationship type descriptions for AI prompts"""
        descriptions = {}
        for relationship_type in self.template.relationship_types:
            descriptions[relationship_type.name] = relationship_type.description
        return descriptions

    def generate_extraction_prompt(self) -> str:
        """Generate entity extraction prompt with template-specific information"""

        # Use custom prompt if available
        if "entity_extraction" in self.template.extraction_prompts:
            base_prompt = self.template.extraction_prompts["entity_extraction"]
        else:
            base_prompt = """
You are an AI assistant specialized in extracting structured information from text.
Your task is to identify entities and relationships from the given content.
"""

        # Add entity type information
        entity_info = "\n\nAvailable Entity Types:\n"
        for entity_type in self.template.entity_types:
            entity_info += f"- {entity_type.name}: {entity_type.description}\n"
            if entity_type.extraction_hints:
                entity_info += f"  Hints: {', '.join(entity_type.extraction_hints)}\n"

        # Add relationship type information
        relationship_info = "\n\nAvailable Relationship Types:\n"
        for relationship_type in self.template.relationship_types:
            relationship_info += (
                f"- {relationship_type.name}: {relationship_type.description}\n"
            )

        # Add requirements
        requirements = """

For each entity, provide:
- name: Clear, concise entity name
- type: One of the predefined entity types above
- description: Brief description of the entity
- confidence: Your confidence in this extraction (0.0 to 1.0)

For relationships, identify how entities connect to each other using the predefined relationship types.
"""

        return base_prompt + entity_info + relationship_info + requirements


def create_schema_generator(template: MemoryTemplate) -> SchemaGenerator:
    """Create a schema generator for the given template"""
    return SchemaGenerator(template)
