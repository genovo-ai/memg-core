#!/bin/bash

# run-ci-docker.sh - Runs the non-interactive CI pipeline in a Docker container

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 Starting non-interactive CI pipeline in Docker...${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker (colima start) and try again."
    exit 1
fi

# Build and run the CI pipeline container (non-interactive)
echo "Building CI environment..."
docker-compose -f docker-compose.fast.yml build ci-runner-fast

echo "Running CI pipeline..."
docker-compose -f docker-compose.fast.yml run --rm ci-runner-fast
