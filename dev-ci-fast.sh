#!/bin/bash

# dev-ci-fast.sh - Interactive development shell using fast build

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 Starting fast interactive CI development shell...${NC}"
echo ""
echo "This gives you a bash shell inside the fast Python environment."
echo ""
echo "Available commands:"
echo "  pytest tests/                    - Run all tests"
echo "  pytest tests/unit_temp/ -v       - Run specific test group"
echo "  ruff check src/                  - Run linting"
echo "  mypy src/ --ignore-missing-imports - Run type checking"
echo "  bandit -r src/                   - Run security scan"
echo "  python -c 'from memg_core import *' - Test imports"
echo ""
echo -e "${GREEN}Environment:${NC}"
echo "  Python: Available as 'python'"
echo "  Working dir: /workspace"
echo "  Source code: /workspace/src"
echo "  Tests: /workspace/tests"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker (colima start) and try again."
    exit 1
fi

# Build if needed
echo "Building fast CI environment..."
docker-compose -f docker-compose.fast.yml build ci-dev-fast > /dev/null

echo -e "${GREEN}🚀 Launching fast interactive shell...${NC}"
echo "Type 'exit' to leave the container."
echo ""

# Run interactive container
docker-compose -f docker-compose.fast.yml run --rm ci-dev-fast
