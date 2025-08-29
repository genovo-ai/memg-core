# MEMG Core MCP Server

A production-ready MCP (Model Context Protocol) server integration for memg-core, providing AI agents with persistent memory capabilities through vector search and graph relationships.

## 🚀 Quick Start

```bash
# Build and run the MCP server
./build_and_run.sh

# Server will be available at:
# - Health: http://localhost:8888/health
# - MCP endpoint: http://localhost:8888/sse
```

## 📋 Features

### Core Memory Operations
- **Add Memory**: Store notes, documents, tasks, bugs, and solutions
- **Search Memory**: Semantic vector search with relevance scoring
- **Delete Memory**: Clean memory removal with user isolation
- **Graph Relationships**: Connect memories with typed relationships

### Advanced Capabilities
- **User Isolation**: Complete separation of user data
- **Graph Traversal**: Multi-hop neighbor discovery
- **Memory Types**: 5 schema-driven types (note, document, task, bug, solution)
- **Relationship Types**: Schema-enforced relationships (FIXES, IMPLEMENTS, ADDRESSES, etc.)

### Production Features
- **Startup Initialization**: Client initializes once during container startup
- **Docker Health Checks**: Proper container health monitoring
- **Resource Management**: Optimized for stable operation
- **Error Handling**: Comprehensive logging and graceful shutdown

## 🛠️ Architecture

### Startup Initialization Pattern
The MCP server uses a **startup initialization pattern** to prevent database re-initialization issues:

- MemgClient initializes **once** during container startup
- Heavy operations (embedding model downloads) happen upfront
- No lazy loading during tool calls = no container restarts
- Stable, predictable resource usage

### Technology Stack
- **memg-core**: v0.6+ from PyPI (vector + graph storage)
- **FastMCP**: MCP protocol server framework
- **Docker**: Containerized deployment
- **Qdrant**: Vector database for semantic search
- **Kuzu**: Graph database for relationships

## 📁 Files

```
integrations/mcp/
├── mcp_server.py          # Main MCP server implementation
├── Dockerfile             # Container build configuration
├── docker-compose.yml     # Service orchestration
├── requirements_mcp.txt   # Python dependencies
├── software_dev.yaml      # Memory schema definition
├── build_and_run.sh      # Build and deployment script
└── README.md             # This file
```

## 🔧 Configuration

### Environment Variables
- `MEMORY_SYSTEM_MCP_PORT`: Server port (default: 8888)
- `MEMORY_SYSTEM_MCP_HOST`: Server host (default: 0.0.0.0)
- `MEMG_YAML_SCHEMA`: Schema file (default: software_dev.yaml)
- `BASE_MEMORY_PATH`: Base path for persistent storage (default: $HOME/.local/share/memg_mcp)
- `QDRANT_STORAGE_PATH`: Internal Qdrant storage path (set by Docker)
- `KUZU_DB_PATH`: Internal Kuzu database path (set by Docker)

### Schema Configuration
The `software_dev.yaml` file defines:
- **Memory Types**: note, document, task, bug, solution
- **Relationships**: FIXES, IMPLEMENTS, ADDRESSES, ANNOTATES, etc.
- **Field Validation**: Required/optional fields per type
- **Enum Values**: Status, priority, severity options

## 🔍 Available MCP Tools

1. **add_memory** - Add new memories with validation
2. **delete_memory** - Remove memories by HRID
3. **search_memories** - Semantic search with graph expansion
4. **add_relationship** - Connect memories with typed relationships
5. **get_system_info** - System information and schema details
6. **health_check** - Server health and status

## 🐳 Docker Usage

### Build and Run
```bash
# Quick start
./build_and_run.sh

# Manual Docker commands
docker-compose build
docker-compose up -d
```

### Management
```bash
# View logs
docker-compose logs -f

# Stop server
docker-compose down

# Health check
curl http://localhost:8888/health
```

## 🧪 Testing

The server has been comprehensively tested:

- ✅ All memory operations (add, search, delete)
- ✅ All relationship types and graph traversal
- ✅ User isolation and data separation
- ✅ Container stability and resource management
- ✅ Schema validation and error handling

## 🔒 Security

- **User Isolation**: Complete data separation between users
- **Schema Validation**: Strict field and type validation
- **Non-root Container**: Runs as dedicated `memg` user
- **Resource Limits**: Proper memory and CPU management

## 💾 Data Persistence

### Mounted Volumes (Default)
Data is now persisted using Docker volumes:
- **Qdrant data**: `$HOME/.local/share/memg_mcp_8888/qdrant`
- **Kuzu data**: `$HOME/.local/share/memg_mcp_8888/kuzu`
- **Port-specific**: Each port gets its own data directory

### Internal Storage (Fallback)
If volume mounting fails, data stays inside container (non-persistent).

## 📊 Performance

- **Startup**: Fast initialization with embedding pre-loading
- **Search**: Sub-second semantic search with relevance scoring
- **Relationships**: Efficient graph traversal with configurable depth
- **Memory**: Clean HRID generation and proper user scoping
- **Persistence**: Data survives container restarts and rebuilds

## 🚨 Troubleshooting

### Container Issues
- **Exit code 137**: Increase Docker memory allocation
- **Port conflicts**: Check `MEMORY_SYSTEM_MCP_PORT` in .env
- **Health check fails**: Wait for embedding model download (60s)

### Common Solutions
- Restart: `docker-compose down && ./build_and_run.sh`
- Logs: `docker-compose logs -f`
- Clean build: `docker-compose build --no-cache`

## 📈 Production Deployment

This MCP server is production-ready with:
- Stable startup initialization pattern
- Comprehensive error handling
- Resource optimization
- Health monitoring
- User data isolation

Perfect for AI agents requiring persistent, searchable memory with relationship modeling.
