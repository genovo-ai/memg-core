#!/bin/bash

# 🚀 Start MCP Server via Docker Compose
# Fast dev cycle: port drives both network and storage isolation

echo "🚀 Starting MemG MCP Server via Docker Compose..."

# Single source of truth: port for dev-8787 cycle
export MEMORY_SYSTEM_MCP_PORT=8787
export BASE_MEMORY_PATH="$HOME/.local/share/memory_system"

# Create host storage directories
mkdir -p "${BASE_MEMORY_PATH}_${MEMORY_SYSTEM_MCP_PORT}/"{qdrant,kuzu}

echo "🔄 Rebuilding and starting server on port ${MEMORY_SYSTEM_MCP_PORT}..."
echo "📁 Storage: ${BASE_MEMORY_PATH}_${MEMORY_SYSTEM_MCP_PORT}/"

# Docker compose: down, build, up
docker-compose -f dockerfiles/docker-compose.yml down
docker-compose -f dockerfiles/docker-compose.yml build --no-cache
docker-compose -f dockerfiles/docker-compose.yml up -d

echo "✅ Server starting on http://localhost:${MEMORY_SYSTEM_MCP_PORT}/"
echo "📖 Check logs: docker-compose -f dockerfiles/docker-compose.yml logs -f"
