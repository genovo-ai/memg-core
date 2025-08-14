#!/bin/bash

# test-api-endpoints.sh - Test the FastAPI endpoints

set -e

BASE_URL="http://localhost:8000"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧪 Testing MEMG Core API Endpoints...${NC}"
echo ""

# Test health endpoint
echo -e "${BLUE}1. Testing Health Endpoint...${NC}"
if curl -s -f "$BASE_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ Health endpoint working${NC}"
else
    echo -e "${RED}❌ Health endpoint failed${NC}"
    exit 1
fi

# Test add note
echo -e "${BLUE}2. Testing Add Note...${NC}"
NOTE_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/memories/note" \
    -H "Content-Type: application/json" \
    -d '{
        "text": "This is a test note from Docker API",
        "user_id": "test-user",
        "title": "Docker Test Note",
        "tags": ["docker", "test", "api"]
    }')

if echo "$NOTE_RESPONSE" | grep -q '"memory_type":"note"'; then
    echo -e "${GREEN}✅ Add note working${NC}"
    NOTE_ID=$(echo "$NOTE_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    echo "   Note ID: $NOTE_ID"
else
    echo -e "${RED}❌ Add note failed${NC}"
    echo "Response: $NOTE_RESPONSE"
fi

# Test search
echo -e "${BLUE}3. Testing Search...${NC}"
SEARCH_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/search" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "test note",
        "user_id": "test-user",
        "limit": 10
    }')

if echo "$SEARCH_RESPONSE" | grep -q '"results"'; then
    echo -e "${GREEN}✅ Search working${NC}"
    RESULT_COUNT=$(echo "$SEARCH_RESPONSE" | grep -o '"results":\[[^]]*\]' | tr -cd ',' | wc -c)
    echo "   Results found: $((RESULT_COUNT + 1))"
else
    echo -e "${RED}❌ Search failed${NC}"
    echo "Response: $SEARCH_RESPONSE"
fi

# Test add document
echo -e "${BLUE}4. Testing Add Document...${NC}"
DOC_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/memories/document" \
    -H "Content-Type: application/json" \
    -d '{
        "summary": "Docker API test document",
        "user_id": "test-user",
        "title": "Docker Test Doc",
        "body": "This is a comprehensive test document created via the Docker API endpoint.",
        "tags": ["docker", "document", "test"]
    }')

if echo "$DOC_RESPONSE" | grep -q '"memory_type":"document"'; then
    echo -e "${GREEN}✅ Add document working${NC}"
else
    echo -e "${RED}❌ Add document failed${NC}"
    echo "Response: $DOC_RESPONSE"
fi

# Test add task
echo -e "${BLUE}5. Testing Add Task...${NC}"
TASK_RESPONSE=$(curl -s -X POST "$BASE_URL/v1/memories/task" \
    -H "Content-Type: application/json" \
    -d '{
        "summary": "Test Docker API integration",
        "user_id": "test-user",
        "title": "Docker API Task",
        "due_date": "2024-12-31T23:59:59",
        "tags": ["docker", "task", "api"]
    }')

if echo "$TASK_RESPONSE" | grep -q '"memory_type":"task"'; then
    echo -e "${GREEN}✅ Add task working${NC}"
else
    echo -e "${RED}❌ Add task failed${NC}"
    echo "Response: $TASK_RESPONSE"
fi

echo ""
echo -e "${GREEN}🎉 API Testing Complete!${NC}"
echo ""
echo "📊 API Documentation available at:"
echo "   http://localhost:8000/docs"
