#!/bin/bash

# dev-ci-shell.sh - Interactive development shell in CI environment
# Perfect for debugging test failures and developing in exact CI environment

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 Starting interactive CI development shell...${NC}"
echo ""
echo "This gives you a bash shell inside the exact Ubuntu environment used by CI."
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
echo "  Python: Available as 'python' and 'python3'"
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
echo "Building CI environment..."
docker-compose -f docker-compose.ci.yml build ci-dev > /dev/null

echo -e "${GREEN}🚀 Launching interactive shell...${NC}"
echo "Type 'exit' to leave the container."
echo ""

# Run interactive container
docker-compose -f docker-compose.ci.yml run --rm ci-dev
