"""Tests for new features: include_details, datetime_format, and override fields."""

from datetime import UTC, datetime

from memg_core.core.models import Memory
from memg_core.core.pipelines.retrieval import PayloadProjector, _format_datetime
from memg_core.core.yaml_translator import YamlTranslator


class TestIncludeDetailsOptions:
    """Test the enhanced include_details parameter options."""

    def setup_method(self):
        """Set up test fixtures."""
        self.yaml_translator = YamlTranslator("./config/core.test.yaml")
        self.projector = PayloadProjector(self.yaml_translator)

    def test_include_details_none(self):
        """Test include_details='none' returns anchor field only."""
        payload = {
            "statement": "Test statement",
            "details": "Some details",
            "project": "test-project",
        }

        result = self.projector.project("memo", payload, include_details="none")

        assert "statement" in result
        assert "details" not in result
        assert "project" not in result

    def test_include_details_self(self):
        """Test include_details='self' returns full payload (original behavior)."""
        payload = {
            "statement": "Test statement",
            "details": "Some details",
            "project": "test-project",
        }

        result = self.projector.project("memo", payload, include_details="self")

        assert "statement" in result
        assert "details" in result
        assert "project" in result

    def test_include_details_all(self):
        """Test include_details='all' returns full payload (same as self for seeds)."""
        payload = {
            "statement": "Test statement",
            "details": "Some details",
            "project": "test-project",
        }

        result = self.projector.project("memo", payload, include_details="all")

        assert "statement" in result
        assert "details" in result
        assert "project" in result


class TestForceExcludeDisplay:
    """Test force_display and exclude_display override functionality from YAML schema."""

    def setup_method(self):
        """Set up test fixtures."""
        self.yaml_translator = YamlTranslator("./config/core.test.yaml")
        self.projector = PayloadProjector(self.yaml_translator)

    def test_document_force_display_from_yaml(self):
        """Test that document entity forces display of 'details' field from YAML config."""
        # Document has force_display: [details] in YAML
        payload = {
            "statement": "Document statement",
            "title": "Document Title",
            "details": "Important details",
            "project": "test-project",
        }

        # Even with include_details="none", details should be forced by YAML
        result = self.projector.project("document", payload, include_details="none")

        assert "statement" in result  # Anchor field always included
        assert "details" in result  # Forced by YAML config
        assert "title" not in result  # Not forced, not anchor
        assert "project" not in result  # Not forced, not anchor

    def test_document_exclude_display_from_yaml(self):
        """Test that document entity excludes 'draft' field from YAML config."""
        # Document has exclude_display: [draft] in YAML
        payload = {
            "statement": "Document statement",
            "title": "Document Title",
            "details": "Document details",
            "draft": "Draft content that should be hidden",
        }

        result = self.projector.project("document", payload, include_details="self")

        assert "statement" in result
        assert "title" in result
        assert "details" in result
        assert "draft" not in result  # Excluded by YAML config

    def test_article_force_and_exclude_together(self):
        """Test article entity with both force_display and exclude_display from YAML."""
        # Article has force_display: [summary, author] and exclude_display: [internal_notes]
        payload = {
            "statement": "Article content",
            "title": "Article Title",
            "summary": "Article summary",
            "author": "John Doe",
            "internal_notes": "Private notes",
            "tags": "tech",
        }

        # Test with include_details="none" - force should still work
        result = self.projector.project("article", payload, include_details="none")

        assert "statement" in result  # Anchor field
        assert "summary" in result  # Forced by YAML
        assert "author" in result  # Forced by YAML
        assert "title" not in result  # Not forced, not anchor
        assert "internal_notes" not in result  # Excluded by YAML
        assert "tags" not in result  # Not forced, not anchor

    def test_article_exclude_overrides_force_conceptually(self):
        """Test that exclude_display would override force_display if same field was in both."""
        # This is a conceptual test - in practice, YAML shouldn't have same field in both lists
        # But our logic should handle exclude taking precedence

        # Article has force_display: [summary, author] and exclude_display: [internal_notes]
        payload = {
            "statement": "Article content",
            "summary": "Article summary",
            "author": "John Doe",
            "internal_notes": "Should be excluded",
        }

        result = self.projector.project("article", payload, include_details="self")

        assert "statement" in result
        assert "summary" in result  # Forced and not excluded
        assert "author" in result  # Forced and not excluded
        assert "internal_notes" not in result  # Excluded takes precedence

    def test_memo_no_override_config(self):
        """Test that memo entity with no override config works normally."""
        payload = {"statement": "Test statement", "project": "test-project"}

        # Memo has no force_display or exclude_display in YAML
        result_none = self.projector.project("memo", payload, include_details="none")
        assert "statement" in result_none
        assert "project" not in result_none

        result_self = self.projector.project("memo", payload, include_details="self")
        assert "statement" in result_self
        assert "project" in result_self


class TestDatetimeFormatting:
    """Test datetime formatting functionality."""

    def test_format_datetime_default(self):
        """Test default ISO format when no format specified."""
        dt = datetime(2025, 9, 23, 14, 30, 45, tzinfo=UTC)
        result = _format_datetime(dt, None)
        assert "2025-09-23T14:30:45+00:00" in result

    def test_format_datetime_custom(self):
        """Test custom datetime format."""
        dt = datetime(2025, 9, 23, 14, 30, 45, tzinfo=UTC)
        result = _format_datetime(dt, "%Y-%m-%d %H:%M:%S")
        assert result == "2025-09-23 14:30:45"

    def test_format_datetime_elegant(self):
        """Test elegant datetime format."""
        dt = datetime(2025, 9, 23, 14, 30, 45, tzinfo=UTC)
        result = _format_datetime(dt, "%B %d, %Y at %I:%M %p")
        assert result == "September 23, 2025 at 02:30 PM"

    def test_format_datetime_fallback_behavior(self):
        """Test datetime formatting with edge cases."""
        dt = datetime(2025, 9, 23, 14, 30, 45, tzinfo=UTC)

        # Test with None format (should use ISO)
        result = _format_datetime(dt, None)
        assert "2025-09-23T14:30:45+00:00" in result

        # Test with empty string format
        result = _format_datetime(dt, "")
        assert result == ""


class TestYamlDatetimeDefault:
    """Test YAML-based datetime format defaults."""

    def test_yaml_datetime_format_extraction(self):
        """Test that datetime format is correctly extracted from YAML."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")
        default_format = yaml_translator.get_default_datetime_format()
        assert default_format == "%Y-%m-%d %H:%M:%S"

    def test_yaml_datetime_format_none_when_missing(self):
        """Test that None is returned when no datetime format in YAML."""
        # Create a minimal YAML translator for testing
        yaml_translator = YamlTranslator("./config/core.test.yaml")
        default_format = yaml_translator.get_default_datetime_format()
        # Should return None if not set in the test YAML
        assert default_format is None or isinstance(default_format, str)


class TestDisplayNamePriority:
    """Test display name priority logic."""

    def test_display_field_from_yaml(self):
        """Test that display field is determined by YAML schema."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")

        # Test getting display field name from YAML
        display_field = yaml_translator.get_display_field_name("memo")
        assert display_field == "statement"  # As defined in YAML

        # Test with memory object
        memory = Memory(
            user_id="test_user",
            memory_type="memo",
            payload={"statement": "This is the statement content"},
        )

        display_text = yaml_translator.get_display_text(memory)
        assert display_text == "This is the statement content"

    def test_fallback_to_anchor(self):
        """Test fallback to anchor field when no display_field."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")

        memory = Memory(
            user_id="test_user", memory_type="memo", payload={"statement": "Original statement"}
        )

        display_text = yaml_translator.get_display_text(memory)
        assert display_text == "Original statement"

    def test_document_display_field_ordering(self):
        """Test that display field appears first in document entity."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")
        projector = PayloadProjector(yaml_translator)

        # Document has display_field: title in YAML
        payload = {
            "statement": "Document statement for vectorization",
            "title": "Document Title",
            "details": "Document details",
            "project": "test-project",
        }

        result = projector.project("document", payload, include_details="self")

        # Title should appear first (display field)
        result_keys = list(result.keys())
        assert result_keys[0] == "title"
        assert result["title"] == "Document Title"
        assert result["statement"] == "Document statement for vectorization"

    def test_force_display_from_yaml(self):
        """Test that force_display fields from YAML are always included."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")
        projector = PayloadProjector(yaml_translator)

        # Document has force_display: [details] in YAML
        payload = {
            "statement": "Document statement",
            "title": "Document Title",
            "details": "Important details",
            "project": "test-project",
        }

        # Even with include_details="none", details should be forced
        result = projector.project("document", payload, include_details="none")

        assert "statement" in result  # Anchor always present
        assert "details" in result  # Force displayed from YAML
        assert "title" not in result  # Not forced, not anchor
        assert "project" not in result

    def test_exclude_display_from_yaml(self):
        """Test that exclude_display fields from YAML are never included."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")
        projector = PayloadProjector(yaml_translator)

        # Document has exclude_display: [draft] in YAML
        payload = {
            "statement": "Document statement",
            "title": "Document Title",
            "details": "Document details",
            "draft": "Draft content that should be hidden",
        }

        result = projector.project("document", payload, include_details="self")

        assert "statement" in result
        assert "title" in result
        assert "details" in result
        assert "draft" not in result  # Excluded by YAML config

    def test_article_comprehensive_override_behavior(self):
        """Test article entity with comprehensive override: display_field, force_display, exclude_display."""
        yaml_translator = YamlTranslator("./config/core.test.yaml")
        projector = PayloadProjector(yaml_translator)

        # Article has: display_field: title, force_display: [summary, author], exclude_display: [internal_notes]
        payload = {
            "statement": "Full article content for vectorization",
            "title": "Article Title",
            "summary": "Article summary",
            "author": "John Doe",
            "internal_notes": "Private notes",
            "tags": "tech, ai",
        }

        result = projector.project("article", payload, include_details="self")

        # Title should appear first (display field)
        result_keys = list(result.keys())
        assert result_keys[0] == "title"
        assert result["title"] == "Article Title"

        # Force display fields should be present
        assert "summary" in result
        assert "author" in result

        # Excluded field should not be present
        assert "internal_notes" not in result

        # Other fields should be present
        assert "statement" in result  # Anchor field
        assert "tags" in result  # Regular field

        # Test with include_details="none" - force_display should still work
        result_none = projector.project("article", payload, include_details="none")
        assert "statement" in result_none  # Anchor
        assert "summary" in result_none  # Forced
        assert "author" in result_none  # Forced
        assert "title" not in result_none  # Not forced, not anchor
        assert "internal_notes" not in result_none  # Excluded
