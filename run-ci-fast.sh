./run-ci-fast.sh#!/bin/bash

# run-ci-fast.sh - Run fast CI pipeline using Python base image

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE} MEMG Core - Fast CI Pipeline (Docker)${NC}"
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
echo ""

# Build and run fast CI pipeline
print_step "Building fast CI Docker image (Python 3.11 base)..."
if docker-compose -f docker-compose.fast.yml build ci-runner-fast; then
    print_success "Fast Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

echo ""
print_step "Running fast CI pipeline..."
echo "This will run the same tests as GitHub CI but much faster!"
echo ""

# Run the fast CI pipeline
if docker-compose -f docker-compose.fast.yml run --rm ci-runner-fast; then
    echo ""
    print_success "🎉 FAST CI PIPELINE PASSED!"
    print_success "Your code is ready for GitHub CI! 🚀"
    echo ""
    echo "Fast scripts available:"
    echo "  ./run-ci-fast.sh           # Fast CI pipeline"
    echo "  ./start-api-fast.sh        # Fast API server"
    echo "  ./dev-ci-fast.sh           # Fast interactive shell"
else
    echo ""
    print_error "❌ FAST CI PIPELINE FAILED!"
    print_error "Fix the issues above before pushing to GitHub."
    echo ""
    echo "To debug: ./dev-ci-fast.sh"
    exit 1
fi
