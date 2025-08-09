"""
Template registry system for MEMG - Dynamic template loading and management
"""

import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import MemoryTemplate, TemplateValidationError
from .default import DEFAULT_TEMPLATE

logger = logging.getLogger(__name__)


class TemplateRegistry:
    """Registry for managing memory templates"""

    def __init__(self):
        self._templates: Dict[str, MemoryTemplate] = {}
        self._current_template: Optional[str] = None
        self._load_built_in_templates()

    def _load_built_in_templates(self) -> None:
        """Load built-in templates"""
        try:
            # Always load default template
            self.register_template(DEFAULT_TEMPLATE)
            self._current_template = "default"
            logger.info("Loaded default template")

        except Exception as e:
            logger.error(f"Failed to load built-in templates: {e}")
            raise TemplateValidationError(f"Failed to load built-in templates: {e}")

    def register_template(self, template: MemoryTemplate) -> None:
        """Register a new template"""
        try:
            # Validate template
            template.validate_template()

            # Store template
            self._templates[template.name] = template
            logger.info(f"Registered template: {template.name} v{template.version}")

        except Exception as e:
            logger.error(f"Failed to register template {template.name}: {e}")
            raise TemplateValidationError(f"Failed to register template {template.name}: {e}")

    def get_template(self, name: str) -> Optional[MemoryTemplate]:
        """Get template by name"""
        return self._templates.get(name)

    def list_templates(self) -> List[str]:
        """List all available template names"""
        return list(self._templates.keys())

    def get_template_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get template information"""
        template = self.get_template(name)
        if not template:
            return None

        return {
            "name": template.name,
            "display_name": template.display_name,
            "description": template.description,
            "version": template.version,
            "entity_types_count": len(template.entity_types),
            "relationship_types_count": len(template.relationship_types),
            "metadata": template.metadata,
        }

    def set_current_template(self, name: str) -> bool:
        """Set the current active template"""
        if name not in self._templates:
            logger.error(f"Template not found: {name}")
            return False

        self._current_template = name
        logger.info(f"Set current template to: {name}")
        return True

    def get_current_template(self) -> Optional[MemoryTemplate]:
        """Get the current active template"""
        if not self._current_template:
            return None
        return self._templates.get(self._current_template)

    def get_current_template_name(self) -> Optional[str]:
        """Get the current active template name"""
        return self._current_template

    def load_template_from_file(self, file_path: str) -> None:
        """Load template from JSON file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                template_data = json.load(f)

            # Convert data to template
            template = self._dict_to_template(template_data)
            self.register_template(template)

        except Exception as e:
            logger.error(f"Failed to load template from file {file_path}: {e}")
            raise TemplateValidationError(f"Failed to load template from file {file_path}: {e}")

    def load_template_from_module(self, module_path: str, template_name: str = "TEMPLATE") -> None:
        """Load template from Python module"""
        try:
            module = importlib.import_module(module_path)
            template = getattr(module, template_name)

            if not isinstance(template, MemoryTemplate):
                raise TemplateValidationError(f"Template object must be MemoryTemplate instance")

            self.register_template(template)

        except Exception as e:
            logger.error(f"Failed to load template from module {module_path}: {e}")
            raise TemplateValidationError(f"Failed to load template from module {module_path}: {e}")

    def _dict_to_template(self, data: Dict[str, Any]) -> MemoryTemplate:
        """Convert dictionary to MemoryTemplate"""
        # This would need more sophisticated conversion logic
        # For now, assume the data structure matches MemoryTemplate
        return MemoryTemplate(**data)

    def export_template(self, name: str, file_path: str) -> None:
        """Export template to JSON file"""
        template = self.get_template(name)
        if not template:
            raise TemplateValidationError(f"Template not found: {name}")

        try:
            template_dict = template.dict()
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(template_dict, f, indent=2, default=str)

            logger.info(f"Exported template {name} to {file_path}")

        except Exception as e:
            logger.error(f"Failed to export template {name}: {e}")
            raise TemplateValidationError(f"Failed to export template {name}: {e}")

    def validate_all_templates(self) -> Dict[str, bool]:
        """Validate all registered templates"""
        results = {}
        for name, template in self._templates.items():
            try:
                template.validate_template()
                results[name] = True
            except Exception as e:
                logger.error(f"Template {name} validation failed: {e}")
                results[name] = False
        return results


# Global template registry instance
_template_registry: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry instance"""
    global _template_registry
    if _template_registry is None:
        _template_registry = TemplateRegistry()
    return _template_registry


def initialize_template_system(template_name: Optional[str] = None) -> TemplateRegistry:
    """Initialize the template system with optional template selection"""
    registry = get_template_registry()

    if template_name:
        if not registry.set_current_template(template_name):
            logger.warning(f"Failed to set template {template_name}, using default")

    return registry
