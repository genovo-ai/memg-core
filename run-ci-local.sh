#!/bin/bash

# run-ci-local.sh - Run the complete CI pipeline locally in Docker
# This replicates the exact GitHub Actions environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE} MEMG Core - Local CI Pipeline (Docker)${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

print_step() {
    echo -e "${YELLOW}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker (colima start) and try again."
    exit 1
fi

print_step "Checking Docker context..."
echo "Docker context: $(docker context show)"
echo "Docker version: $(docker --version)"
echo ""

# Build and run CI pipeline
print_step "Building CI Docker image..."
if docker-compose -f docker-compose.ci.yml build ci-runner; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

echo ""
print_step "Running complete CI pipeline in Ubuntu container..."
echo "This will run:"
echo "  1. Security scan (bandit)"
echo "  2. Code formatting check (ruff format)"
echo "  3. Code linting (ruff check)"
echo "  4. Type checking (mypy)"
echo "  5. Full test suite (pytest)"
echo ""

# Run the CI pipeline
if docker-compose -f docker-compose.ci.yml run --rm ci-runner; then
    echo ""
    print_success "🎉 LOCAL CI PIPELINE PASSED!"
    print_success "Your code is ready for GitHub CI! 🚀"
    echo ""
    echo "To run interactively: ./dev-ci-shell.sh"
    echo "To clean up: docker-compose -f docker-compose.ci.yml down -v"
else
    echo ""
    print_error "❌ LOCAL CI PIPELINE FAILED!"
    print_error "Fix the issues above before pushing to GitHub."
    echo ""
    echo "To debug interactively: ./dev-ci-shell.sh"
    exit 1
fi
