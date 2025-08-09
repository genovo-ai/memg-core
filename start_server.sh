#!/bin/bash

# 🚀 Start MEMG Core MCP Server via Docker Compose
# Supports both root-level and dockerfiles/ compose configurations

set -e

echo "🚀 Starting MEMG Core MCP Server via Docker Compose..."

# Usage: ./start_server.sh [--local]
#   --local  Use local Dockerfile/compose to build from current source (no PyPI)

# Load .env first (so docker compose variable substitution uses it)
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# Configuration with defaults (do not override .env)
export MEMORY_SYSTEM_MCP_PORT=${MEMORY_SYSTEM_MCP_PORT:-8787}
export BASE_MEMORY_PATH=${BASE_MEMORY_PATH:-"$HOME/.local/share/memory_system"}
export MEMG_TEMPLATE=${MEMG_TEMPLATE:-"software_development"}

# Create host storage directories
STORAGE_DIR="${BASE_MEMORY_PATH}_${MEMORY_SYSTEM_MCP_PORT}"
mkdir -p "${STORAGE_DIR}/"{qdrant,kuzu}

echo "🔄 Configuration:"
echo "   Port: ${MEMORY_SYSTEM_MCP_PORT}"
echo "   Storage: ${STORAGE_DIR}/"
echo "   Template: ${MEMG_TEMPLATE}"

# Parse flags
USE_LOCAL=false
for arg in "$@"; do
  case $arg in
    --local)
      USE_LOCAL=true
      shift
      ;;
    *)
      ;;
  esac
done

# Choose compose file
if [[ "$USE_LOCAL" == true && -f "dockerfiles/docker-compose.local.yml" ]]; then
  COMPOSE_FILE="dockerfiles/docker-compose.local.yml"
  echo "📁 Using local compose: $COMPOSE_FILE"
else
  COMPOSE_FILE="docker-compose.yml"
  if [[ ! -f "$COMPOSE_FILE" && -f "dockerfiles/docker-compose.yml" ]]; then
      COMPOSE_FILE="dockerfiles/docker-compose.yml"
      echo "📁 Using: dockerfiles/docker-compose.yml"
  else
      echo "📁 Using: docker-compose.yml"
  fi
fi

# Ensure .env exists (copy from env.example if needed)
if [[ ! -f ".env" && -f "env.example" ]]; then
    echo "📋 Creating .env from env.example..."
    cp env.example .env
    echo "⚠️  Please edit .env and set your GOOGLE_API_KEY"
fi

# Docker compose operations
echo "🛑 Stopping existing containers..."
docker-compose -f "$COMPOSE_FILE" down

echo "🔨 Building fresh container..."
docker-compose -f "$COMPOSE_FILE" build --no-cache

echo "🚀 Starting server..."
docker-compose -f "$COMPOSE_FILE" up -d

echo ""
echo "✅ MEMG Core server starting!"
echo "🌐 Server: http://localhost:${MEMORY_SYSTEM_MCP_PORT}/"
echo "🔍 Health: http://localhost:${MEMORY_SYSTEM_MCP_PORT}/health"
echo "📖 Logs: docker-compose -f $COMPOSE_FILE logs -f memg-mcp-server"
echo "🛑 Stop: docker-compose -f $COMPOSE_FILE down"
