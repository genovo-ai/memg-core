# MEMG Core MCP Server

A Docker-based MCP (Model Context Protocol) server for the MEMG Core memory system. This provides 10 MCP tools for memory management with automatic schema validation and dual storage (Qdrant + Kuzu).

## 🚀 **Quick Start**

```bash
# Simple start with defaults
./cli.sh software_developer.yaml

# Custom port and database location
./cli.sh myschema.yaml --port 8228 --database-path ~/my_memories

# Ephemeral mode (no external data)
./cli.sh myschema.yaml --no-mount --port 9999

# Server runs on: http://localhost:{PORT}/health
```

## 📋 **CLI Usage**

### **Basic Syntax**
```bash
./cli.sh <yaml-file> [options]
```

### **Options**
- `--fresh` - Fresh start (auto-backup + clean rebuild) - requires confirmation
- `--force` - Skip safety confirmations (use with --fresh)
- `--no-mount` - Copy YAML into container (ephemeral data, no external folders)
- `--port, -p` - Override port (default: 8888, or from .env if exists)
- `--database-path` - Override database storage location (default: same as YAML file)
- `--stop` - Stop container
- `--backup` - Create manual backup
- `--help` - Show help

### **Smart Start Behavior (Default)**
```bash
./cli.sh myschema.yaml
```
- **Running?** → Shows "already running"
- **Stopped?** → Starts existing container
- **Missing?** → Builds and starts new container
- **Never destroys data**

### **Fresh Start**
```bash
./cli.sh myschema.yaml --fresh
```
1. Auto-backup to backups directory
2. Stop container
3. Delete database files
4. Rebuild container
5. Start with empty database

### **Configuration Priority**
Port selection follows this priority:
1. `--port` argument (highest priority)
2. `.env` file (if exists)
3. Default port 8888 (if no .env)

## 📁 **File Structure**

### **Minimal Setup (No .env required)**
```
your-project/
├── myschema.yaml          # Memory types, fields, and relationships
└── myschema_8888/         # Auto-created database storage (mount mode)
    ├── qdrant/
    └── kuzu/
```

### **Optional .env Configuration**
```bash
# Optional - CLI will use defaults if missing
MEMORY_SYSTEM_MCP_PORT=8228
```

### **YAML Schema Example**
```yaml
version: v1

entities:
  - name: note
    description: "General note or observation"
    fields:
      statement: { type: string, required: true }
      project: { type: string }
      origin: { type: enum, choices: [user, system], default: system }

  - name: task
    parent: note
    description: "Development task or work item"
    fields:
      status: { type: enum, choices: [backlog, todo, in_progress, done], default: backlog }
      priority: { type: enum, choices: [low, medium, high, critical], default: medium }

relations:
  note:
    - name: note_related_to_note
      predicate: RELATED_TO
      directed: false
```

## 🔧 **Deployment Modes**

### **Mount Mode (Default - Persistent Data)**
```bash
./cli.sh myschema.yaml --port 8228
```
- **Data Storage**: External folders (`myschema_8228/`)
- **Persistence**: Survives container restarts and computer reboots
- **Use Case**: Production, long-term storage

### **No-Mount Mode (Ephemeral Data)**
```bash
./cli.sh myschema.yaml --no-mount --port 9999
```
- **Data Storage**: Inside container only
- **Persistence**: Lost when container stops or computer restarts
- **Use Case**: Testing, temporary work, avoiding permission issues
- **Benefits**: No external folders, no chown permission issues

### **Custom Database Path**
```bash
./cli.sh myschema.yaml --database-path ~/my_memories
```
- **Creates**: `~/my_memories/myschema_8888/`
- **Note**: Works best with relative paths (e.g., `./custom_db`) due to Docker volume mounting limitations

## 🛡️ **Safety Features**

- **Auto-backup** before `--fresh` operations
- **Confirmation required** for destructive operations (type "DELETE")
- **Port conflict detection** with fix suggestions
- **Optional .env** - works with smart defaults
- **Never destroys data accidentally**

## 🔄 **Backup & Restore**

### **Manual Backup**
```bash
./cli.sh myschema.yaml --backup
```

### **Restore Process**
```bash
# 1. Stop server
./cli.sh myschema.yaml --stop

# 2. Extract backup to database directory
cd myschema_8888/
tar -xzf ../backups/backup_2024-01-15_14-30.tar.gz

# 3. Restart
./cli.sh myschema.yaml
```

### **Check Backups**
```bash
ls -la backups/
```

## 🔧 **MCP Tools Available**

Once running, the server exposes 10 MCP tools:
- **Memory Management**: `add_memory`, `update_memory`, `delete_memory`, `get_memory`, `get_memories`
- **Search & Relationships**: `search_memories`, `add_relationship`, `delete_relationship`
- **System**: `get_system_info`, `health_check`

All tools include dynamic schema-aware documentation and validation based on your YAML configuration.

## 📝 **Key Features**

- **Dual Storage**: Qdrant (vector) + Kuzu (graph) for semantic search with relationships
- **Schema Validation**: YAML-driven memory types, fields, and relationship definitions
- **Port Isolation**: Multiple projects can run simultaneously on different ports
- **Flexible Configuration**: Optional .env, CLI overrides, smart defaults
- **Auto Backups**: Automatic backups before destructive operations
- **Two Deployment Modes**: Persistent (mount) vs ephemeral (no-mount)

## 🐛 **Troubleshooting**

**Port in use:**
```bash
./cli.sh myschema.yaml --stop
```

**Won't start:**
```bash
./cli.sh myschema.yaml --fresh
```

**Check logs:**
```bash
docker-compose --project-name memg-mcp-{PORT} logs
```

**Permission issues with custom paths:**
```bash
# Use no-mount mode to avoid Docker volume permission issues
./cli.sh myschema.yaml --no-mount
```

## 💻 **Cursor Integration**

To use as Cursor AI memory, add this to your `~/.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "memg_core_mcp": {
      "url": "localhost:8228/sse",
      "description": "Memory Service for AI."
    }
  }
}
```

Adjust the port to match your `--port` setting or .env configuration.

## 📚 **Examples**

```bash
# Basic usage with defaults
./cli.sh software_developer.yaml

# Production setup with custom port
./cli.sh production_schema.yaml --port 8228

# Development with ephemeral data
./cli.sh dev_schema.yaml --no-mount --port 9999

# Custom database location
./cli.sh myschema.yaml --database-path ./project_memories --port 8500

# Fresh start with confirmation
./cli.sh myschema.yaml --fresh

# Force fresh start (skip confirmations)
./cli.sh myschema.yaml --fresh --force
```
