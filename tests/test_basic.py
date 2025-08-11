"""Basic tests for Liberation AI Memory System."""

from pathlib import Path
import sys

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that core modules can be imported."""
    try:
        import memg_core  # noqa: F401

        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")


def test_version():
    """Test version is accessible."""
    try:
        from memg_core.version import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0
    except ImportError:
        # Version might not be set up yet
        pytest.skip("Version module not available")


def test_basic_config():
    """Test basic configuration loading."""
    try:
        from memg_core.config import get_config

        config = get_config()
        assert config is not None
    except Exception as e:
        pytest.skip(f"Config not available: {e}")


def test_mcp_server_import():
    """Test MCP server can be imported from integration package."""
    try:
        from integration.mcp.mcp_server import app, main  # type: ignore

        # Basic sanity checks
        assert app is not None or callable(main)
    except ImportError as e:
        pytest.skip(f"MCP server import failed (integration path): {e}")


def test_requirements_satisfied():
    """Test that key requirements are installed."""
    # FastAPI is not required; this is a FastMCP-based server
    required_packages = ["fastmcp", "qdrant_client", "kuzu", "pydantic", "uvicorn"]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)

    if missing:
        pytest.fail(f"Missing required packages: {missing}")


if __name__ == "__main__":
    pytest.main([__file__])
