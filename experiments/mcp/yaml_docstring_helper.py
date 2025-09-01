#!/usr/bin/env python3
"""
YAML → Docstring Helper for MCP Server Dynamic Tools

Generates clean, schema-aware documentation from YAML schemas for MCP tool consumers.
Filters out system-managed fields and provides comprehensive relationship information.
"""

from typing import Any, Dict, List, Optional

from memg_core.core.yaml_translator import YamlTranslator

# ========================= DOCSTRING TEMPLATES =========================

ADD_MEMORY_TEMPLATE = """Add a memory with proper payload based on the type of memory.

Args:
  memory_type: One of the supported memory types: {entity_types}
  user_id: User identifier - separates user's memories from each other
  payload: Memory data with required fields based on the type of memory

Returns: Dict with result message and a human readable identifier (HRID), or error details

Type specific fields to include in the payload:
{entity_details}"""

ADD_RELATIONSHIP_TEMPLATE = """Add a relationship between two memories.

Args:
  from_memory_hrid: Source memory HRID
  to_memory_hrid: Target memory HRID
  relation_type: Relationship type
  from_memory_type: Source entity type
  to_memory_type: Target entity type
  user_id: User identifier

Returns: Dict with success message or error details

Available relationships:
{relationships}"""

SEARCH_MEMORIES_TEMPLATE = """Search memories using semantic vector search with graph expansion.

Args:
  query: Search query text
  user_id: User identifier (required for data isolation)
  limit: Maximum results (default: 5, max: 50)
  memory_type: Filter by type ({entity_types}, optional)
  neighbor_limit: Max graph neighbors per result (default: 5)
  hops: Graph traversal depth (default: 1)
  include_semantic: Include semantic search (default: true)

Returns: Dict with memories array, each containing hrid, memory_type, payload, score"""

DELETE_MEMORY_TEMPLATE = """Delete a memory by HRID.

Args:
  memory_id: Memory HRID (human readable identifier)
  user_id: User identifier (for ownership verification)

Returns: Dict with result message and deletion status, or error details"""

GET_MEMORY_TEMPLATE = """Get a single memory by HRID.

Args:
  hrid: Memory HRID (human readable identifier)
  user_id: User identifier (for ownership verification)
  memory_type: Optional memory type hint (inferred from HRID if not provided)

Returns: Dict with memory data including hrid, memory_type, payload, timestamps, or error details"""

GET_MEMORIES_TEMPLATE = """Get multiple memories with filtering and optional graph expansion.

Args:
  user_id: User identifier (required for data isolation)
  memory_type: Filter by type ({entity_types}, optional)
  limit: Maximum results (default: 50)
  offset: Skip first N results for pagination (default: 0)
  include_neighbors: Include graph neighbors (default: false)
  hops: Graph traversal depth when include_neighbors=true (default: 1)
  filters: Additional field-based filters (optional)

Returns: Dict with memories array, count, and query parameters"""


class YamlDocstringHelper:
    """Helper to generate clean docstrings from YAML schema for MCP consumers."""

    def __init__(self, yaml_path: Optional[str] = None):
        """Initialize with YAML schema path."""
        self.translator = YamlTranslator(yaml_path)
        self._entity_cache: Dict[str, Dict[str, Any]] = {}
        self._relationships_cache: Optional[Dict[str, List[str]]] = None

    def get_all_entities(self) -> List[str]:
        """Get list of all available entity types."""
        return self.translator.get_entity_types()

    def _get_entity_fields(self, entity_name: str) -> Dict[str, Any]:
        """Get filtered field information for an entity."""
        if entity_name in self._entity_cache:
            return self._entity_cache[entity_name]

        # Get full entity spec with inheritance
        entity_spec = self.translator._resolve_entity_with_inheritance(entity_name)

        filtered_info = {
            "required_fields": [],
            "optional_fields": [],
            "description": entity_spec.get("description", f"{entity_name.title()} entity")
        }

        # Process fields, filtering out system fields
        fields = entity_spec.get("fields", {})
        for field_name, field_def in fields.items():
            if isinstance(field_def, dict) and not field_def.get("system", False):
                if field_def.get("required", False):
                    filtered_info["required_fields"].append(field_name)
                else:
                    filtered_info["optional_fields"].append(field_name)

        self._entity_cache[entity_name] = filtered_info
        return filtered_info

    def _get_all_relationships(self) -> Dict[str, List[str]]:
        """Get all relationships from YAML schema, organized by source entity."""
        if self._relationships_cache is not None:
            return self._relationships_cache

        relationships_by_source = {}

        # Scan ALL entities for ALL relationships (correct approach based on memg-core analysis)
        for entity_name in self.get_all_entities():
            entity_spec = self.translator._resolve_entity_with_inheritance(entity_name)
            relations = entity_spec.get("relations", [])

            for relation in relations:
                if isinstance(relation, dict):
                    source = relation.get("source", entity_name)
                    target = relation.get("target", "")
                    predicates = relation.get("predicates", [])

                    if source and target and predicates:
                        if source not in relationships_by_source:
                            relationships_by_source[source] = []

                        for predicate in predicates:
                            relationship = f"{predicate}: {target}"
                            if relationship not in relationships_by_source[source]:
                                relationships_by_source[source].append(relationship)

        self._relationships_cache = relationships_by_source
        return relationships_by_source

    def generate_add_memory_docstring(self) -> str:
        """Generate comprehensive docstring for add_memory tool covering all entity types."""
        entities = self.get_all_entities()
        entity_details = []

        # Process each entity type
        for entity_name in sorted(entities):
            info = self._get_entity_fields(entity_name)
            entity_details.append(f"  • {entity_name}:")

            # Required fields
            if info["required_fields"]:
                for field in info["required_fields"]:
                    entity_details.append(f"    - {field}: required")
            else:
                entity_details.append("    - statement: required")

            # Important optional fields (limit to avoid clutter)
            important_optional = [f for f in info["optional_fields"]
                                if f in ["project", "priority", "status", "severity", "details", "url", "file_path"]]

            for field in important_optional[:3]:  # Limit to 3 most important
                entity_details.append(f"    - {field}: optional")

        return ADD_MEMORY_TEMPLATE.format(
            entity_types=', '.join(sorted(entities)),
            entity_details='\n'.join(entity_details)
        )

    def generate_add_relationship_docstring(self) -> str:
        """Generate comprehensive docstring for add_relationship tool."""
        relationships_by_source = self._get_all_relationships()
        relationship_lines = []

        # Format relationships by source type
        for source_type in sorted(relationships_by_source.keys()):
            relationship_lines.append(f"  • {source_type}")
            for relationship in sorted(set(relationships_by_source[source_type])):
                relationship_lines.append(f"    - {relationship}")

        return ADD_RELATIONSHIP_TEMPLATE.format(
            relationships='\n'.join(relationship_lines)
        )

    def generate_search_memories_docstring(self) -> str:
        """Generate docstring for search_memories tool."""
        entities = self.get_all_entities()
        return SEARCH_MEMORIES_TEMPLATE.format(
            entity_types=', '.join(sorted(entities))
        )

    def generate_delete_memory_docstring(self) -> str:
        """Generate docstring for delete_memory tool."""
        return DELETE_MEMORY_TEMPLATE

    def generate_get_memory_docstring(self) -> str:
        """Generate docstring for get_memory tool."""
        return GET_MEMORY_TEMPLATE

    def generate_get_memories_docstring(self) -> str:
        """Generate docstring for get_memories tool."""
        entities = self.get_all_entities()
        return GET_MEMORIES_TEMPLATE.format(
            entity_types=', '.join(sorted(entities))
        )

    def generate_entity_summary(self) -> str:
        """Generate a summary of all entities in the schema for debugging."""
        entities = self.get_all_entities()
        lines = ["Available Memory Types:", "=" * 25, ""]

        for entity_name in sorted(entities):
            info = self._get_entity_fields(entity_name)
            lines.extend([
                f"📝 {entity_name.upper()}",
                f"   Description: {info['description']}",
                f"   Required: {', '.join(info['required_fields']) if info['required_fields'] else 'statement (inherited)'}",
                f"   Optional: {', '.join(info['optional_fields']) if info['optional_fields'] else 'none'}",
                ""
            ])

        return "\n".join(lines)


def main():
    """Test the YAML docstring helper with the software_dev.yaml schema."""
    import sys

    print("🔍 Testing YAML Docstring Helper - Schema-Aware MCP Tool Docstrings")
    print("=" * 70)

    # Get YAML path from command line or use default
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "../software_developer/software_dev.yaml"
    print(f"Using YAML file: {yaml_path}")

    try:
        helper = YamlDocstringHelper(yaml_path)

        # Test all docstring generators
        tests = [
            ("📝 ADD_MEMORY", helper.generate_add_memory_docstring),
            ("🔗 ADD_RELATIONSHIP", helper.generate_add_relationship_docstring),
            ("🔍 SEARCH_MEMORIES", helper.generate_search_memories_docstring),
            ("🗑️ DELETE_MEMORY", helper.generate_delete_memory_docstring),
            ("📄 GET_MEMORY", helper.generate_get_memory_docstring),
            ("📚 GET_MEMORIES", helper.generate_get_memories_docstring),
            ("📋 ENTITY SUMMARY", helper.generate_entity_summary),
        ]

        for title, generator in tests:
            print(f"\n{title} DOCSTRING:")
            print("=" * 40)
            print(generator())

        print("\n" + "=" * 70)
        print("✅ All docstrings generated successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
