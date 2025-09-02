# MEMG Core MCP Server

A Docker-based MCP (Model Context Protocol) server for the MEMG Core memory system. This provides 10 MCP tools for memory management with automatic schema validation and dual storage (Qdrant + Kuzu).

## 📁 **Setup Requirements**

Create a **target directory** with two essential files:

```
your-project/
├── .env                    # Server configuration (port, schema file)
├── schema.yaml            # Memory types, fields, and relationships
└── backups/               # Auto-created backup directory
```

### **`.env` Configuration**
```bash
MEMORY_SYSTEM_MCP_PORT=8228
MEMORY_SYSTEM_MCP_HOST="0.0.0.0"
MEMG_YAML_SCHEMA=schema.yaml
BASE_MEMORY_PATH=local_memory_data
```

### **YAML Schema Example**
```yaml
entities:
  note:
    description: "General note or observation"
    fields:
      statement: { type: string, required: true }
      project: { type: string, required: false }
      origin: { type: string, required: false, choices: ["user", "system"] }

relations:
  note:
    - source: note
      target: note
      predicate: RELATES_TO
      directed: false
```

## 🚀 **Quick Start**

```bash
# 1. Create your project directory with .env and schema.yaml
# 2. Start server
./cli.sh your-project/

# Server runs on: http://localhost:{PORT}/health
```

## 📋 **CLI Commands**

For detailed CLI usage, backup/restore procedures, and troubleshooting, see **[README_CLI.md](README_CLI.md)**.

**Quick reference:**
- `./cli.sh project/` - Smart start (most common)
- `./cli.sh project/ --fresh` - Fresh rebuild with auto-backup
- `./cli.sh project/ --stop` - Stop server
- `./cli.sh project/ --backup` - Manual backup

## 🔧 **MCP Tools Available**

Once running, the server exposes 10 MCP tools:
- `add_memory`, `update_memory`, `delete_memory`, `get_memory`, `get_memories`
- `search_memories`, `add_relationship`, `delete_relationship`
- `get_system_info`, `health_check`

All tools include schema-aware documentation and validation.

## 📝 **Key Features**

- **Dual Storage**: Qdrant (vector) + Kuzu (graph) for semantic search with relationships
- **Schema Validation**: YAML-driven memory types, fields, and relationship definitions
- **Port Isolation**: Multiple projects can run simultaneously on different ports
- **Auto Backups**: Automatic backups before destructive operations
- **Smart Defaults**: Never destroys data accidentally


## Cursor integration
To use as Cursor AI memory add this to cursor mcp.json file. Adjust the port if needed.
```
{
  "mcpServers": {
    "memg_core_mcp": {
      "url": "localhost:8228/sse",
      "description": "Memory Service for AI."
    }
  }
}
```
