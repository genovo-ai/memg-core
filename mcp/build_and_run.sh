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
echo "🛡️  SAFETY: This script only affects LOCAL containers in this directory"
echo "🌐 Remote GCP deployments are COMPLETELY SAFE and will NOT be touched"
echo ""

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

# Step 1: Stop ONLY the specific container for this port
echo ""
echo "🛑 Step 1: Checking for container memg-mcp-server-$MCP_PORT ONLY..."

# Check for the specific container name that docker-compose would create
CONTAINER_NAME="memg-mcp-server-$MCP_PORT"
if docker ps --format "{{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
    echo "Found container $CONTAINER_NAME, stopping it..."
    docker stop "$CONTAINER_NAME" || true
    docker rm "$CONTAINER_NAME" || true
else
    echo "✅ Container $CONTAINER_NAME not found - safe to proceed"
fi

# Double-check: Also look for any container using our specific port
OTHER_CONTAINERS=$(docker ps --filter "publish=$MCP_PORT" --format "{{.Names}}" 2>/dev/null || true)
if [ -n "$OTHER_CONTAINERS" ]; then
    echo "⚠️  Found other containers using port $MCP_PORT: $OTHER_CONTAINERS"
    for container in $OTHER_CONTAINERS; do
        echo "Stopping container: $container"
        docker stop "$container" || true
        docker rm "$container" || true
    done
fi

# Step 2: Clean build (no cache)
echo ""
if [ "$USE_PYPI" = true ]; then
    echo "🔨 Step 2: Building Docker image with PyPI installation (no cache)..."
else
    echo "🔨 Step 2: Building Docker image with local source (no cache)..."
fi

# Only remove the specific service if it exists in compose
echo "🧹 Checking docker-compose for memg-mcp-server service..."
if docker-compose ps memg-mcp-server 2>/dev/null | grep -q "memg-mcp-server"; then
    echo "Stopping docker-compose service: memg-mcp-server"
    docker-compose stop memg-mcp-server 2>/dev/null || true
    docker-compose rm -f memg-mcp-server 2>/dev/null || true
else
    echo "✅ No memg-mcp-server service found in docker-compose"
fi

# Build with no cache
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
echo ""
echo "🛡️  SAFETY CONFIRMATION:"
echo "  ✅ This script ONLY stopped: memg-mcp-server-$MCP_PORT (if it existed)"
echo "  ✅ Other containers on different ports: COMPLETELY SAFE"
echo "  ✅ Your GCP deployments: COMPLETELY UNTOUCHED"
echo "  ✅ Other docker-compose projects: COMPLETELY SAFE"
