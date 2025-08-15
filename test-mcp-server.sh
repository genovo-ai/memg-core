#!/bin/bash

# test-mcp-server.sh - Build wheel and test MCP server with latest code

set -e

echo "🚀 MEMG Core MCP Server Test"
echo "================================"

# Step 1: Build the wheel
echo "📦 Step 1: Building wheel..."
rm -rf dist/
python -m build

# Check if wheel was created
if [ ! -d "dist" ] || [ -z "$(find dist -name '*.whl')" ]; then
    echo "❌ No wheel file found in dist/"
    exit 1
fi

WHEEL_FILE=$(find dist -name '*.whl' | head -1)
echo "✅ Built wheel: $WHEEL_FILE"

# Step 2: Build Docker image
echo ""
echo "🐳 Step 2: Building Docker image..."
cd mcp/
docker build -f Dockerfile.mcp -t memg-core-mcp:test ..

echo "✅ Docker image built successfully"

# Step 3: Test the server
echo ""
echo "🧪 Step 3: Testing MCP server..."

# Start the container in background
echo "Starting container..."
docker run -d \
    --name memg-mcp-test \
    -p 8787:8787 \
    -e QDRANT_STORAGE_PATH=/qdrant \
    -e KUZU_DB_PATH=/kuzu/memory_db \
    memg-core-mcp:test

# Wait for startup
echo "Waiting for server to start..."
sleep 10

# Test health endpoint
echo "Testing health endpoint..."
if curl -f http://localhost:8787/health > /dev/null 2>&1; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    docker logs memg-mcp-test
    docker stop memg-mcp-test
    docker rm memg-mcp-test
    exit 1
fi

# Test root endpoint
echo "Testing root endpoint..."
curl -s http://localhost:8787/ | python -m json.tool

echo ""
echo "🎉 MCP Server test completed successfully!"
echo ""
echo "Server is running at: http://localhost:8787"
echo "To stop: docker stop memg-mcp-test && docker rm memg-mcp-test"
echo ""
echo "Available tools:"
echo "- mcp_gmem_add_memory"
echo "- mcp_gmem_search_memories"
echo "- mcp_gmem_add_note"
echo "- mcp_gmem_add_document"
echo "- mcp_gmem_add_task"
echo "- mcp_gmem_get_system_info"
