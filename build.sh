#!/bin/bash

# 🏗️ MEMG Core Build Script
# Builds both the core package and MCP server

set -e

echo "🏗️ Building MEMG Core..."

# Configuration
CORE_PACKAGE="memg-core"
MCP_IMAGE="memg-mcp-server"
REGISTRY="ghcr.io/genovo-ai"

# Build core package
echo "📦 Building core package..."
python -m build

echo "✅ Core package built successfully!"
echo "📋 Built files:"
ls -la dist/

# Test installation
echo "🧪 Testing core package installation..."
pip install --force-reinstall dist/*.whl
echo "✅ Core package installs successfully!"

# Build MCP Docker image (for local testing)
echo "🐳 Building MCP Docker image for local testing..."
docker build -f dockerfiles/Dockerfile.mcp -t ${MCP_IMAGE}:local .

echo ""
echo "🎉 Build complete!"
echo ""
echo "📦 Core package: dist/memg_core-*.whl"
echo "🐳 MCP image: ${MCP_IMAGE}:local"
echo ""
echo "🚀 Test MCP server locally:"
echo "docker run -p 8787:8787 -e GOOGLE_API_KEY=your_key ${MCP_IMAGE}:local"
echo ""
echo "📚 Install core library:"
echo "pip install dist/memg_core-*.whl"
