#!/usr/bin/env python3
"""
YAML → Docstring Helper for MCP Server Dynamic Tools

This module creates clean, filtered documentation from YAML schemas for MCP tool consumers.
It filters out system-managed fields and provides only user-relevant information.
"""

import os
from typing import Dict, List, Any, Optional
from memg_core.core.yaml_translator import YamlTranslator


class YamlDocstringHelper:
    """Helper to generate clean docstrings from YAML schema for MCP consumers."""

    def __init__(self, yaml_path: Optional[str] = None):
        """Initialize with YAML schema path."""
        self.translator = YamlTranslator(yaml_path)
        self._entity_cache: Dict[str, Dict[str, Any]] = {}

    def get_entity_info(self, entity_name: str) -> Dict[str, Any]:
        """Get filtered entity information for consumers."""
        if entity_name in self._entity_cache:
            return self._entity_cache[entity_name]

        # Get full entity spec with inheritance
        entity_spec = self.translator._resolve_entity_with_inheritance(entity_name)

        # Filter out system fields and create consumer-friendly info
        filtered_info = {
            "name": entity_name,
            "description": entity_spec.get("description", f"{entity_name.title()} entity"),
            "required_fields": [],
            "optional_fields": [],
            "field_descriptions": {},
            "field_constraints": {},
            "relations": []
        }

        # Process fields
        fields = entity_spec.get("fields", {})
        for field_name, field_def in fields.items():
            if isinstance(field_def, dict):
                # Skip system-managed fields
                if field_def.get("system", False):
                    continue

                # Determine if required
                is_required = field_def.get("required", False)

                # Add to appropriate list
                if is_required:
                    filtered_info["required_fields"].append(field_name)
                else:
                    filtered_info["optional_fields"].append(field_name)

                # Add field description
                field_type = field_def.get("type", "string")
                description_parts = [f"Type: {field_type}"]

                # Add constraints
                constraints = []
                if "max_length" in field_def:
                    constraints.append(f"max_length={field_def['max_length']}")
                if "choices" in field_def:
                    choices = field_def["choices"]
                    constraints.append(f"choices={choices}")
                if "default" in field_def:
                    constraints.append(f"default={field_def['default']}")

                if constraints:
                    description_parts.append(f"Constraints: {', '.join(constraints)}")

                filtered_info["field_descriptions"][field_name] = "; ".join(description_parts)
                filtered_info["field_constraints"][field_name] = constraints

        # Process relations (for reference)
        relations = entity_spec.get("relations", [])
        for relation in relations:
            if isinstance(relation, dict):
                rel_info = {
                    "name": relation.get("name", ""),
                    "description": relation.get("description", ""),
                    "predicates": relation.get("predicates", []),
                    "source": relation.get("source", ""),
                    "target": relation.get("target", ""),
                    "directed": relation.get("directed", True)
                }
                filtered_info["relations"].append(rel_info)

        self._entity_cache[entity_name] = filtered_info
        return filtered_info

    def get_all_entities(self) -> List[str]:
        """Get list of all available entity types."""
        return self.translator.get_entity_types()

    def generate_add_memory_docstring(self) -> str:
        """Generate comprehensive docstring for add_memory tool covering all entity types."""
        entities = self.get_all_entities()

        lines = [
            "Add a memory with proper payload based on the type of memory.",
            "",
            "Args:",
            f"  memory_type: One of the supported memory types: {', '.join(sorted(entities))}",
            "  user_id: User identifier - it separates user's memories from each other",
            "  payload: Memory data with required fields based on the type of memory",
            "",
            "Returns: Dict with result message and a human readable identifier (HRID), or error details",
            "",
            "Type specific fields to include in the payload:"
        ]

        # Process each entity type
        for entity_name in sorted(entities):
            info = self.get_entity_info(entity_name)
            lines.append(f"  • {entity_name}:")

            # Required fields
            if info["required_fields"]:
                for field in info["required_fields"]:
                    lines.append(f"    - {field}: required")
            else:
                lines.append("    - statement: required")

            # Optional fields (limit to most important ones to avoid clutter)
            important_optional = []
            for field in info["optional_fields"]:
                if field in ["project", "priority", "status", "severity", "details", "url", "file_path"]:
                    important_optional.append(field)

            if important_optional:
                for field in important_optional[:3]:  # Limit to 3 most important
                    lines.append(f"    - {field}: optional")

        return "\n".join(lines)

    def generate_add_relationship_docstring(self) -> str:
        """Generate comprehensive docstring for add_relationship tool."""
        entities = self.get_all_entities()

        lines = [
            "Add a relationship between two memories.",
            "",
            "Args:",
            "  from_memory_hrid: Source memory HRID",
            "  to_memory_hrid: Target memory HRID",
            "  relation_type: Relationship type",
            "  from_memory_type: Source entity type",
            "  to_memory_type: Target entity type",
            "  user_id: User identifier",
            "",
            "Returns: Dict with success message or error details",
            "",
            "Available relationships:"
        ]

        # Collect all relationships organized by source type
        # Only include relationships where the entity is actually the SOURCE
        relationships_by_source = {}

        for entity_name in entities:
            info = self.get_entity_info(entity_name)
            for rel in info["relations"]:
                source = rel["source"]
                target = rel["target"]
                predicates = rel["predicates"]

                # Only include relationships that are defined under the source entity
                # This ensures we only show relationships that are actually enforced
                if source == entity_name:  # The relationship source matches the entity we're processing
                    if source not in relationships_by_source:
                        relationships_by_source[source] = []

                    for predicate in predicates:
                        relationships_by_source[source].append(f"{predicate}: {target}")

        # Format relationships by source type
        for source_type in sorted(relationships_by_source.keys()):
            lines.append(f"  • {source_type}")
            for relationship in sorted(set(relationships_by_source[source_type])):
                lines.append(f"    - {relationship}")

        return "\n".join(lines)

    def generate_search_memories_docstring(self) -> str:
        """Generate docstring for search_memories tool."""
        entities = self.get_all_entities()

        lines = [
            "Search memories using semantic vector search with graph expansion.",
            "",
            "Args:",
            "  query: Search query text",
            "  user_id: User identifier (required for data isolation)",
            "  limit: Maximum results (default: 5, max: 50)",
            f"  memory_type: Filter by type ({', '.join(sorted(entities))}, optional)",
            "  neighbor_limit: Max graph neighbors per result (default: 5)",
            "  hops: Graph traversal depth (default: 1)",
            "  include_semantic: Include semantic search (default: true)",
            "",
            "Returns: Dict with memories array, each containing hrid, memory_type, payload, score"
        ]

        return "\n".join(lines)

    def generate_delete_memory_docstring(self) -> str:
        """Generate docstring for delete_memory tool."""
        lines = [
            "Delete a memory by HRID.",
            "",
            "Args:",
            "  memory_id: Memory HRID (human readable identifier)",
            "  user_id: User identifier (for ownership verification)",
            "",
            "Returns: Dict with result message and deletion status, or error details"
        ]

        return "\n".join(lines)

    def generate_entity_summary(self) -> str:
        """Generate a summary of all entities in the schema."""
        entities = self.get_all_entities()
        lines = [
            "Available Memory Types:",
            "=" * 25,
            ""
        ]

        for entity_name in sorted(entities):
            info = self.get_entity_info(entity_name)
            lines.append(f"📝 {entity_name.upper()}")
            lines.append(f"   Description: {info['description']}")
            lines.append(f"   Required: {', '.join(info['required_fields']) if info['required_fields'] else 'statement (inherited)'}")
            lines.append(f"   Optional: {', '.join(info['optional_fields']) if info['optional_fields'] else 'none'}")
            lines.append("")

        return "\n".join(lines)

    def generate_fastmcp_annotations(self, entity_name: str) -> Dict[str, Any]:
        """Generate FastMCP parameter annotations for an entity."""
        info = self.get_entity_info(entity_name)

        annotations = {}

        # Generate payload field annotation with detailed schema info
        payload_desc_parts = [
            f"Fields for {entity_name} entity:",
        ]

        if info["required_fields"]:
            payload_desc_parts.append("Required: " + ", ".join(info["required_fields"]))

        if info["optional_fields"]:
            payload_desc_parts.append("Optional: " + ", ".join(info["optional_fields"]))

        # Add field details
        for field_name, desc in info["field_descriptions"].items():
            payload_desc_parts.append(f"  {field_name}: {desc}")

        annotations["payload_description"] = "; ".join(payload_desc_parts)
        annotations["entity_description"] = info["description"]
        annotations["required_fields"] = info["required_fields"]
        annotations["optional_fields"] = info["optional_fields"]

        return annotations


def main():
    """Test the YAML docstring helper with the software_dev.yaml schema."""
    import sys

    print("🔍 Testing YAML Docstring Helper - Improved MCP Tool Docstrings")
    print("=" * 70)

    # Get YAML path from command line or use default
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "../software_developer/software_dev.yaml"
    print(f"Using YAML file: {yaml_path}")

    # Initialize helper
    helper = YamlDocstringHelper(yaml_path)

    # Test 1: Generate ADD_MEMORY docstring
    print("\n📝 ADD_MEMORY TOOL DOCSTRING:")
    print("=" * 40)
    print(helper.generate_add_memory_docstring())

    # Test 2: Generate ADD_RELATIONSHIP docstring
    print("\n🔗 ADD_RELATIONSHIP TOOL DOCSTRING:")
    print("=" * 40)
    print(helper.generate_add_relationship_docstring())

    # Test 3: Generate SEARCH_MEMORIES docstring
    print("\n🔍 SEARCH_MEMORIES TOOL DOCSTRING:")
    print("=" * 40)
    print(helper.generate_search_memories_docstring())

    # Test 4: Generate DELETE_MEMORY docstring
    print("\n🗑️ DELETE_MEMORY TOOL DOCSTRING:")
    print("=" * 40)
    print(helper.generate_delete_memory_docstring())

    # Test 5: Show entity summary for reference
    print("\n📋 ENTITY SUMMARY (for reference):")
    print("=" * 40)
    print(helper.generate_entity_summary())

    print("\n" + "=" * 70)
    print("✅ All docstrings generated successfully!")
    print("These can now be used to replace the current MCP tool descriptions.")


if __name__ == "__main__":
    main()
