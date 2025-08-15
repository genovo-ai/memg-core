"""Tests for plugin optionality."""

import os

import pytest

pytestmark = pytest.mark.plugin
import importlib
from unittest.mock import patch

from memg_core.api.public import search


def test_core_has_no_plugins_imports_grep():
    """Test that core modules don't import from plugins."""
    # List of core modules to check
    core_modules = [
        "memg_core.core.models",
        "memg_core.core.indexing",
        "memg_core.core.exceptions",
        "memg_core.core.logging",
        "memg_core.core.pipeline.indexer",
        "memg_core.core.pipeline.retrieval",
    ]

    # Check each module
    for module_name in core_modules:
        # Import the module
        module = importlib.import_module(module_name)

        # Get the module source file
        source_file = module.__file__
        assert source_file is not None

        # Read the source code
        with open(source_file) as f:
            source_code = f.read()

        # Check for imports from plugins
        assert "from ..plugins" not in source_code
        assert "import ..plugins" not in source_code
        assert "from memg_core.plugins" not in source_code
        assert "import memg_core.plugins" not in source_code


def test_api_safe_plugin_import_missing():
    """Test that API safely handles missing plugins."""
    # Mock environment variable to enable YAML schema
    with patch.dict(os.environ, {"MEMG_ENABLE_YAML_SCHEMA": "true"}):
        # Mock dependencies
        with (
            patch("memg_core.api.public.get_config") as mock_config,
            patch("memg_core.api.public.QdrantInterface"),
            patch("memg_core.api.public.KuzuInterface"),
            patch("memg_core.api.public.Embedder"),
            patch("memg_core.api.public.graph_rag_search") as mock_search,
            patch("importlib.import_module") as mock_import,
        ):
            # Configure mocks
            mock_config.return_value.memg.qdrant_collection_name = "memories"
            mock_config.return_value.memg.kuzu_database_path = "/tmp/kuzu"

            # Mock import error for plugin
            mock_import.side_effect = ImportError("Module not found")

            # Call search - should not crash
            try:
                search(query="test", user_id="test-user")
            except Exception as e:
                pytest.fail(f"search() raised {type(e).__name__} unexpectedly: {e}")

            # Check that graph_rag_search was called
            mock_search.assert_called_once()

            # Check that relation_names is None (default fallback)
            assert mock_search.call_args[1].get("relation_names") is None
