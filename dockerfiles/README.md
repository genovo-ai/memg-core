# Memory System Docker Setup

**Single container solution** with embedded Qdrant and Kuzu storage.

## Architecture

- **MCP Server**: FastMCP server with memory tools
- **Qdrant**: Embedded file-based vector storage
- **Kuzu**: Embedded graph database
- **Storage**: All data persists in internal container storage

## Quick Start

1. **Start the memory system:**
   ```bash
   cd dockerfiles/
   docker-compose up -d
   ```

2. **Check service status:**
   ```bash
   docker-compose ps
   ```

3. **Test the MCP server:**
   ```bash
   curl http://localhost:8766/sse/
   ```

4. **Stop the system:**
   ```bash
   docker-compose down
   ```

## MCP Server Access

- **SSE Endpoint**: http://localhost:8766/sse/
- **Available Tools**: `add_memory`, `search_memories`, `get_memory_stats`
- **Resources**: `memory://system/info`, `memory://config/current`

## Testing with Curl

The MCP server uses JSON-RPC 2.0 over Server-Sent Events (SSE). Here's how to test it:

### Step 1: Get Session Token

First, open a terminal and start an SSE session:

```bash
export MCP_SERVER="http://localhost:8766"
curl "${MCP_SERVER}/sse"
```

This will return something like:
```
event: endpoint
data: http://localhost:8766/messages?sessionId=abc123...
```

**Keep this terminal running!** Copy the session URL from the `data` field.

### Step 2: Initialize Session

In a new terminal, initialize the MCP session:

```bash
export MCP_ENDPOINT="http://localhost:8766/messages?sessionId=abc123..."

curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "clientInfo": {
      "name": "test-client",
      "version": "1.0.0"
    }
  }
}'
```

### Step 3: List Available Tools

```bash
curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}'
```

### Step 4: Add Memory

```bash
curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "add_memory",
    "arguments": {
      "content": "This is a test memory about MCP servers",
      "source": "curl_test",
      "metadata": {
        "category": "testing",
        "priority": "high"
      }
    }
  }
}'
```

**Expected Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "success": true,
    "memory_id": "mem_xyz123",
    "message": "Added memory: This is a test memory about MCP servers..."
  }
}
```

### Step 5: Search Memories

```bash
curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "search_memories",
    "arguments": {
      "query": "MCP servers",
      "limit": 3
    }
  }
}'
```

**Expected Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "success": true,
    "query": "MCP servers",
    "results": [
      {
        "memory_id": "mem_xyz123",
        "content": "This is a test memory about MCP servers",
        "score": 0.95,
        "source": "curl_test",
        "created_at": "2025-01-26T..."
      }
    ],
    "total_found": 1
  }
}
```

### Step 6: Get System Stats

```bash
curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_memory_stats",
    "arguments": {}
  }
}'
```

### Step 7: Access Resources

```bash
# List available resources
curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "resources/list"
}'

# Read system info resource
curl -X POST "${MCP_ENDPOINT}" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "resources/read",
  "params": {
    "uri": "memory://system/info"
  }
}'
```

## Development

**Local testing:**
```bash
# Test production server directly
source .venv/bin/activate && python src/memory_system/mcp_server.py
```

## Troubleshooting

**Check logs:**
```bash
docker-compose logs mcp_server
```

**Reset data:**
```bash
docker-compose down
docker-compose up -d
```

**Common Issues:**
- If SSE session expires, restart from Step 1
- Ensure container is running: `docker-compose ps`
- Check server logs if tools fail to initialize
