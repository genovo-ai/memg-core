"""
JSON schema definitions for AI service
Universal schemas for any type of content processing

Now supports dynamic schema generation from templates while maintaining backward compatibility.
"""

import logging
from typing import Any

from ..templates.registry import get_template_registry
from .schema_generator import SchemaGenerator

logger = logging.getLogger(__name__)

# Static schemas that don't depend on templates
_STATIC_SCHEMAS = {
    "text_analysis": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "topics": {"type": "array", "items": {"type": "string"}},
            "key_concepts": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "summary", "topics"],
    },
    "memory_extraction": {
        "type": "object",
        "properties": {
            "memories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of salient memory facts extracted from conversation",
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "extraction_context": {"type": "string"},
        },
        "required": ["memories"],
    },
    # entity_relationship_extraction schema is now generated dynamically from templates
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
                    "complexity": {
                        "type": "string",
                        "enum": ["SIMPLE", "MODERATE", "COMPLEX", "EXPERT"],
                    },
                    "domain": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"],
                    },
                },
            },
        },
        "required": ["content_type", "main_themes"],
    },
}

# Cache for dynamically generated schemas
_schema_cache: dict[str, dict[str, Any]] = {}
_current_template_name: str | None = None


def _get_current_schemas() -> dict[str, Any]:
    """Get schemas for the current template, using cache when possible"""
    global _schema_cache, _current_template_name

    try:
        registry = get_template_registry()
        current_template = registry.get_current_template()

        if not current_template:
            logger.warning("No current template found, using static schemas only")
            return _STATIC_SCHEMAS.copy()

        template_name = current_template.name

        # Check if we need to regenerate schemas
        if template_name != _current_template_name or template_name not in _schema_cache:
            logger.info(f"Generating schemas for template: {template_name}")

            # Generate schemas for this template
            schema_generator = SchemaGenerator(current_template)
            template_schemas = schema_generator.generate_all_schemas()

            # Combine static and template schemas
            all_schemas = _STATIC_SCHEMAS.copy()
            all_schemas.update(template_schemas)

            # Cache the result
            _schema_cache[template_name] = all_schemas
            _current_template_name = template_name

        return _schema_cache[template_name]

    except Exception as e:
        logger.error(f"Failed to get current schemas: {e}")
        # Fallback to static schemas
        return _STATIC_SCHEMAS.copy()


def get_schemas() -> dict[str, Any]:
    """Get all available schemas for the current template"""
    return _get_current_schemas()


def get_schema(schema_name: str) -> dict[str, Any] | None:
    """Get a specific schema by name"""
    schemas = get_schemas()
    return schemas.get(schema_name)


def clear_schema_cache() -> None:
    """Clear the schema cache (useful when templates change)"""
    global _schema_cache, _current_template_name
    _schema_cache.clear()
    _current_template_name = None
    logger.info("Schema cache cleared")


# Create a SCHEMAS object that behaves like the old dictionary but is dynamic
class DynamicSchemasDict:
    """A dictionary-like object that dynamically returns schemas based on current template"""

    def __getitem__(self, key: str) -> dict[str, Any]:
        schema = get_schema(key)
        if schema is None:
            raise KeyError(f"Schema not found: {key}")
        return schema

    def get(self, key: str, default=None) -> dict[str, Any]:
        schema = get_schema(key)
        return schema if schema is not None else default

    def keys(self):
        return get_schemas().keys()

    def values(self):
        return get_schemas().values()

    def items(self):
        return get_schemas().items()

    def __contains__(self, key: str) -> bool:
        return key in get_schemas()

    def __len__(self) -> int:
        return len(get_schemas())


# Replace the old SCHEMAS with dynamic version
SCHEMAS = DynamicSchemasDict()
