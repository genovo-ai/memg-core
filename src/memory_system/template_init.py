"""
Template system initialization for MEMG
"""

import logging
from typing import Optional

from .config import get_config
from .templates.registry import get_template_registry, initialize_template_system
from .utils.schemas import clear_schema_cache

logger = logging.getLogger(__name__)


def initialize_templates(template_name: Optional[str] = None) -> bool:
    """
    Initialize the template system for MEMG

    Args:
        template_name: Optional template name to set as current

    Returns:
        True if initialization successful, False otherwise
    """
    try:
        # Get config to determine template
        if not template_name:
            config = get_config()
            template_name = config.memg.template_name

        logger.info(f"Initializing template system with template: {template_name}")

        # Initialize template registry
        registry = initialize_template_system(template_name)

        # Verify template was loaded
        current_template = registry.get_current_template()
        if not current_template:
            logger.error(f"Failed to load template: {template_name}")
            return False

        # Clear schema cache to force regeneration with new template
        clear_schema_cache()

        logger.info(
            f"Template system initialized successfully with template: "
            f"{current_template.name} v{current_template.version}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to initialize template system: {e}")
        return False


def switch_template(template_name: str) -> bool:
    """
    Switch to a different template at runtime

    Args:
        template_name: Name of template to switch to

    Returns:
        True if switch successful, False otherwise
    """
    try:
        logger.info(f"Switching to template: {template_name}")

        registry = get_template_registry()

        if not registry.set_current_template(template_name):
            logger.error(f"Failed to switch to template: {template_name}")
            return False

        # Clear schema cache to force regeneration with new template
        clear_schema_cache()

        current_template = registry.get_current_template()
        logger.info(
            f"Successfully switched to template: "
            f"{current_template.name} v{current_template.version}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to switch template to {template_name}: {e}")
        return False


def get_current_template_info() -> dict:
    """Get information about the current template"""
    try:
        registry = get_template_registry()
        current_template = registry.get_current_template()

        if not current_template:
            return {"error": "No current template"}

        return {
            "name": current_template.name,
            "display_name": current_template.display_name,
            "description": current_template.description,
            "version": current_template.version,
            "entity_types_count": len(current_template.entity_types),
            "relationship_types_count": len(current_template.relationship_types),
            "entity_types": [et.name for et in current_template.entity_types],
            "relationship_types": [
                rt.name for rt in current_template.relationship_types
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get current template info: {e}")
        return {"error": str(e)}


def list_available_templates() -> list:
    """List all available templates"""
    try:
        registry = get_template_registry()
        template_names = registry.list_templates()

        templates_info = []
        for name in template_names:
            info = registry.get_template_info(name)
            if info:
                templates_info.append(info)

        return templates_info

    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        return []
