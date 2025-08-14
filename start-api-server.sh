#!/bin/bash

# start-api-server.sh - Start FastAPI server in Docker for local testing

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting MEMG Core FastAPI Server in Docker...${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker (colima start) and try again.${NC}"
    exit 1
fi

# Build the image if needed
echo -e "${YELLOW}Building Docker image (if needed)...${NC}"
docker-compose -f docker-compose.ci.yml build api-server

echo ""
echo -e "${GREEN}🌐 FastAPI Server Starting...${NC}"
echo ""
echo "📍 Endpoints:"
echo "  • API Base:    http://localhost:8000"
echo "  • Health:      http://localhost:8000/health"
echo "  • Docs:        http://localhost:8000/docs"
echo "  • ReDoc:       http://localhost:8000/redoc"
echo ""
echo "🔧 API Endpoints:"
echo "  • POST /v1/memories/note       - Add note"
echo "  • POST /v1/memories/document   - Add document"
echo "  • POST /v1/memories/task       - Add task"
echo "  • POST /v1/memories            - Add generic memory"
echo "  • POST /v1/search             - Search memories"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start the API server
docker-compose -f docker-compose.ci.yml up api-server
