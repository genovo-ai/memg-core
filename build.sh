#!/bin/bash

# 🏗️ MEMG Core Build Script (package only)
# - Builds the memg-core wheel/sdist into ./dist
# - Verifies the package can be installed
# - MCP runtime is handled separately by start_server.sh + dockerfiles/docker-compose.yml

set -euo pipefail

echo "🏗️ Building memg-core package..."

# Clean previous build artifacts
rm -rf dist build ./*.egg-info || true

# Ensure build tool is available
python -m pip install --upgrade pip build >/dev/null

# Build wheel and sdist
python -m build

echo "✅ Build complete. Artifacts:"
ls -la dist/

# Smoke test install
echo "🧪 Verifying installation of built wheel..."
pip install --force-reinstall dist/*.whl >/dev/null

echo "✅ memg-core installs successfully from the built wheel."
echo ""
echo "Next steps:"
echo "- To run MCP server, use: ./start_server.sh (uses dockerfiles/docker-compose.yml)"
echo "- To publish (CI will handle), ensure PYPI_API_TOKEN is set in secrets."
