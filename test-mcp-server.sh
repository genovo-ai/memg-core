#!/bin/bash

# test-mcp-server.sh - Test MCP server with published image

set -e

echo "🚀 MEMG Core MCP Server Test"
echo "================================"

# Step 1: Use published Docker image
echo "🐳 Step 1: Using published Docker image..."
echo "✅ Using ghcr.io/genovo-ai/memg-core-mcp:latest"

# Step 2: Test the server
echo ""
echo "🧪 Step 2: Testing MCP server..."

# Start the container in background
echo "Starting container..."
docker run -d \
    --name memg-mcp-test \
    -p 8787:8787 \
    -e QDRANT_STORAGE_PATH=/qdrant \
    -e KUZU_DB_PATH=/kuzu/memory_db \
    -e MEMG_YAML_SCHEMA=/app/schema/core.minimal.yaml \
    ghcr.io/genovo-ai/memg-core-mcp:latest

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
