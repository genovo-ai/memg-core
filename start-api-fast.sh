#!/bin/bash

# start-api-fast.sh - Start FastAPI server using fast Docker build

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting MEMG Core FastAPI Server (Fast Build)...${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker (colima start) and try again.${NC}"
    exit 1
fi

# Build the image if needed
echo -e "${YELLOW}Building fast Docker image (if needed)...${NC}"
docker-compose -f docker-compose.fast.yml build api-server-fast

echo ""
echo -e "${GREEN}🌐 FastAPI Server Starting (Fast)...${NC}"
echo ""
echo "📍 Endpoints:"
echo "  • API Base:    http://localhost:8000"
echo "  • Health:      http://localhost:8000/health"
echo "  • Docs:        http://localhost:8000/docs"
echo "  • ReDoc:       http://localhost:8000/redoc"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start the fast API server
docker-compose -f docker-compose.fast.yml up api-server-fast
