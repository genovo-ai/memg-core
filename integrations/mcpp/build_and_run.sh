#!/bin/bash

# build_and_run.sh - Build and run MEMG Core MCP Server locally with Docker

set -e

# Parse command line arguments for help
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            echo "Usage: $0"
            echo ""
            echo "Build and run MEMG MCP Server using memg-core v0.6+ from PyPI."
            echo ""
            echo "OPTIONS:"
            echo "  -h, --help    Show this help message"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🚀 MEMG Core MCP Server - Docker Build & Run"
echo "============================================="
echo "📦 Using memg-core v0.6+ from PyPI (self-contained)"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "📋 Loading environment from .env file..."
    # Load specific variables directly to avoid subshell issues
    eval $(grep -E '^(MEMORY_SYSTEM_MCP_PORT|MEMG_YAML_PATH|MEMG_DB_PATH|BASE_MEMORY_PATH)=' .env | sed 's/^/export /')
    echo "✅ Loaded configuration variables"
fi

# Get the port from environment or use default (respecting .env)
MCP_PORT=${MEMORY_SYSTEM_MCP_PORT:-8888}

# Create a unique project name based on port for complete isolation
PROJECT_NAME="memg-mcp-${MCP_PORT}"

echo "📍 Using port: $MCP_PORT"
echo "🏗️ Using Docker Compose project: $PROJECT_NAME"

# No volume mounting - data stays inside container
echo "💾 Data will be stored inside container (non-persistent)"

# Step 1: Shutdown only containers for THIS specific port
echo ""
echo "🛑 Step 1: Shutting down existing containers for port $MCP_PORT..."

# Check for our specific container name first
SPECIFIC_CONTAINER="memg-mcp-server-$MCP_PORT"
if docker ps -a --filter "name=$SPECIFIC_CONTAINER" --format "{{.Names}}" | grep -q "$SPECIFIC_CONTAINER" 2>/dev/null; then
    echo "Found container '$SPECIFIC_CONTAINER', stopping and removing..."
    docker stop "$SPECIFIC_CONTAINER" 2>/dev/null || true
    docker rm "$SPECIFIC_CONTAINER" 2>/dev/null || true
else
    echo "No container found for port $MCP_PORT"
fi

# Also check for any other containers using our port (safety check)
RUNNING_CONTAINER=$(docker ps --filter "publish=$MCP_PORT" --format "{{.Names}}" 2>/dev/null || true)
if [ -n "$RUNNING_CONTAINER" ] && [ "$RUNNING_CONTAINER" != "$SPECIFIC_CONTAINER" ]; then
    echo "Found additional container '$RUNNING_CONTAINER' using port $MCP_PORT, stopping..."
    docker stop "$RUNNING_CONTAINER" || true
    docker rm "$RUNNING_CONTAINER" || true
fi

# Step 2: Build Docker image (clean build)
echo ""
echo "🔨 Step 2: Building Docker image with memg-core v0.6+ from PyPI..."
echo "💡 Note: Building with latest memg-core from PyPI"
docker-compose --project-name "$PROJECT_NAME" build

# Step 3: Start the service
echo ""
echo "🚀 Step 3: Starting MCP server..."
docker-compose --project-name "$PROJECT_NAME" up -d

# Step 4: Wait for startup and test
echo ""
echo "⏳ Step 4: Waiting for server startup..."
sleep 5

# Check if container is running
if ! docker-compose --project-name "$PROJECT_NAME" ps | grep -q "Up"; then
    echo "❌ Container failed to start!"
    echo ""
    echo "📋 Container logs:"
    docker-compose --project-name "$PROJECT_NAME" logs
    exit 1
fi

# Test custom health endpoint
echo "🔍 Testing health endpoint..."
for i in {1..10}; do
    if curl -f "http://localhost:$MCP_PORT/health" > /dev/null 2>&1; then
        echo "✅ Health check passed!"
        break
    elif [ $i -eq 10 ]; then
        echo "❌ Health check failed after 10 attempts"
        echo ""
        echo "📋 Container logs:"
        docker-compose --project-name "$PROJECT_NAME" logs
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
docker-compose --project-name "$PROJECT_NAME" ps
echo ""
echo "🌐 Server URLs:"
echo "  Health: http://localhost:$MCP_PORT/health"
echo "  Root:   http://localhost:$MCP_PORT/"
echo ""
echo "🔧 Management commands:"
echo "  View logs:    docker-compose --project-name $PROJECT_NAME logs -f"
echo "  Stop server:  docker-compose --project-name $PROJECT_NAME down"
echo "  Restart:      ./build_and_run.sh"
echo "  Help:         ./build_and_run.sh --help"
echo ""
echo "🏗️ Dependencies:"
echo "  memg-core: v0.6+ from PyPI (self-contained)"
echo ""
echo "📋 Available MCP tools (6 total):"
echo "  - add_memory"
echo "  - delete_memory"
echo "  - search_memories (with graph expansion)"
echo "  - add_relationship"
echo "  - get_system_info"
echo "  - health_check"
echo ""
echo "📄 Configuration:"
echo "  YAML Schema: ${MEMG_YAML_PATH:-software_dev.yaml}"
echo "  DB Path: ${MEMG_DB_PATH:-tmp}"
echo ""
echo "💾 Data Storage:"
echo "  Data stored inside container (non-persistent)"
echo "  Data will be lost when container is removed"
