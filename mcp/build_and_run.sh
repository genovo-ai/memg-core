#!/bin/bash

# build_and_run.sh - Build and run MEMG Core MCP Server locally with Docker

set -e

# Parse command line arguments
USE_PYPI=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-pypi)
            USE_PYPI=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "OPTIONS:"
            echo "  --use-pypi    Install memg-core from PyPI instead of local source"
            echo "  -h, --help    Show this help message"
            echo ""
            echo "Default behavior: Install memg-core from local source (current behavior)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🚀 MEMG Core MCP Server - Local Docker Build & Run"
echo "=================================================="

if [ "$USE_PYPI" = true ]; then
    echo "📦 Mode: Installing memg-core from PyPI"
else
    echo "🔧 Mode: Installing memg-core from local source (default)"
fi

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "📋 Loading environment from .env file..."
    # Load .env but expand $HOME properly
    while IFS= read -r line; do
        if [[ ! "$line" =~ ^#.* ]] && [[ "$line" =~ ^[A-Z_].*=.* ]]; then
            # Expand $HOME in the value
            expanded_line=$(echo "$line" | envsubst)
            export "$expanded_line"
        fi
    done < .env
fi

# Get the port from environment or use default
MCP_PORT=${MEMORY_SYSTEM_MCP_PORT:-8787}

echo "📍 Using port: $MCP_PORT"

# Ensure BASE_MEMORY_PATH is fully expanded for docker-compose
export BASE_MEMORY_PATH="${BASE_MEMORY_PATH:-$HOME/.local/share/memory_system}"

# Export USE_PYPI for docker-compose
export USE_PYPI

# Ensure mount directories exist to avoid Docker chown issues
VOLUME_BASE="${BASE_MEMORY_PATH}_${MCP_PORT}"
echo "🔧 Ensuring volume directories exist at: ${VOLUME_BASE}"
mkdir -p "${VOLUME_BASE}/qdrant" "${VOLUME_BASE}/kuzu"

# Step 1: Shutdown any existing containers
echo ""
echo "🛑 Step 1: Shutting down existing containers..."
if docker-compose ps -q 2>/dev/null | grep -q .; then
    echo "Found running containers, shutting down..."
    docker-compose down
else
    echo "No running containers found"
fi

# Also check for any containers using our port
RUNNING_CONTAINER=$(docker ps --filter "publish=$MCP_PORT" --format "{{.Names}}" 2>/dev/null || true)
if [ -n "$RUNNING_CONTAINER" ]; then
    echo "Found container '$RUNNING_CONTAINER' using port $MCP_PORT, stopping..."
    docker stop "$RUNNING_CONTAINER" || true
    docker rm "$RUNNING_CONTAINER" || true
fi

# Step 2: Clean build (no cache)
echo ""
if [ "$USE_PYPI" = true ]; then
    echo "🔨 Step 2: Building Docker image with PyPI installation (no cache)..."
else
    echo "🔨 Step 2: Building Docker image with local source (no cache)..."
fi
docker-compose build --no-cache

# Step 3: Start the service
echo ""
echo "🚀 Step 3: Starting MCP server..."
docker-compose up -d

# Step 4: Wait for startup and test
echo ""
echo "⏳ Step 4: Waiting for server startup..."
sleep 5

# Check if container is running
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Container failed to start!"
    echo ""
    echo "📋 Container logs:"
    docker-compose logs
    exit 1
fi

# Test health endpoint
echo "🔍 Testing health endpoint..."
for i in {1..10}; do
    if curl -f "http://localhost:$MCP_PORT/health" > /dev/null 2>&1; then
        echo "✅ Health check passed!"
        break
    elif [ $i -eq 10 ]; then
        echo "❌ Health check failed after 10 attempts"
        echo ""
        echo "📋 Container logs:"
        docker-compose logs
        exit 1
    else
        echo "Attempt $i/10 failed, waiting..."
        sleep 2
    fi
done

# Step 5: Show status and usage info
echo ""
echo "🎉 MCP Server is running successfully!"
echo ""
echo "📊 Container status:"
docker-compose ps
echo ""
echo "🌐 Server URLs:"
echo "  Health: http://localhost:$MCP_PORT/health"
echo "  Root:   http://localhost:$MCP_PORT/"
echo ""
echo "🔧 Management commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Stop server:  docker-compose down"
echo "  Restart:      ./build_and_run.sh"
echo "  Help:         ./build_and_run.sh --help"
echo ""
echo "🏗️ Build options:"
echo "  Local source: ./build_and_run.sh (default)"
echo "  From PyPI:    ./build_and_run.sh --use-pypi"
echo ""
echo "📋 Available MCP tools:"
echo "  - mcp_gmem_add_memory"
echo "  - mcp_gmem_search_memories"
echo "  - mcp_gmem_get_system_info"
echo "  - mcp_gmem_delete_memory"
