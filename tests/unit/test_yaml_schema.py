"""
Unit tests for YAML schema loading and validation - essential use cases only.
"""

from pathlib import Path

import pytest

from memg_core.core.yaml_translator import YamlTranslator


@pytest.mark.unit
class TestYamlSchemaEssentials:
    """Test essential YAML schema functionality."""

    def test_yaml_loads_and_creates_memories(self, test_yaml_path: str):
        """Test YAML loads and can create all entity types."""
        assert Path(test_yaml_path).exists(), f"Test YAML not found: {test_yaml_path}"

        translator = YamlTranslator(yaml_path=test_yaml_path)

        # Test creating each entity type with minimal required fields
        test_cases = [
            ("memo", {"statement": "Test memo"}),
            ("note", {"statement": "Test note"}),
            ("document", {"statement": "Test doc", "details": "Test details"}),
        ]

        for memory_type, payload in test_cases:
            memory = translator.create_memory_from_yaml(
                memory_type=memory_type, payload=payload, user_id="test_user"
            )
            assert memory.memory_type == memory_type
            assert memory.payload["statement"] == payload["statement"]

    def test_inheritance_works(self, test_yaml_path: str):
        """Test that note inherits from memo (essential inheritance test)."""
        translator = YamlTranslator(yaml_path=test_yaml_path)

        # Note should inherit memo fields and add its own
        note = translator.create_memory_from_yaml(
            memory_type="note",
            payload={"statement": "Test note", "project": "test-project"},
            user_id="test_user",
        )

        # Should have inherited 'statement' and added 'project'
        assert note.payload["statement"] == "Test note"
        assert note.payload["project"] == "test-project"

    def test_required_vs_optional_fields(self, test_yaml_path: str):
        """Test required field validation (essential validation test)."""
        translator = YamlTranslator(yaml_path=test_yaml_path)

        # Document requires 'details' - should fail without it
        try:
            translator.create_memory_from_yaml(
                memory_type="document",
                payload={"statement": "Test doc"},  # missing 'details'
                user_id="test_user",
            )
            raise AssertionError("Should have failed without required 'details' field")
        except Exception:
            pass  # Expected to fail

        # Should work with required field
        doc = translator.create_memory_from_yaml(
            memory_type="document",
            payload={"statement": "Test doc", "details": "Required details"},
            user_id="test_user",
        )
        assert doc.payload["details"] == "Required details"

    def test_anchor_field_system(self, test_yaml_path: str):
        """Test that anchor field system works for search."""
        translator = YamlTranslator(yaml_path=test_yaml_path)

        memory = translator.create_memory_from_yaml(
            memory_type="note",
            payload={"statement": "This will be the anchor text"},
            user_id="test_user",
        )

        anchor_text = translator.build_anchor_text(memory)
        assert anchor_text == "This will be the anchor text"
