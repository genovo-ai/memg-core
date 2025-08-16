# Enhanced Schema Deployment Guide

## Current Status
✅ **All 3 MCP tools working correctly**
- `mcp_gmem_get_system_info` - Returns system info and available types
- `mcp_gmem_add_memory` - Adds memories with YAML validation
- `mcp_gmem_search_memories` - Searches memories with scoring

✅ **Enhanced schema created**: `config/software_dev.yaml`

## To Deploy Enhanced Schema

### Option 1: Environment Variable (Recommended)
```bash
export MEMG_YAML_SCHEMA=/path/to/memg-core/config/software_dev.yaml
# Restart MCP server
```

### Option 2: Docker Environment
```bash
# In .env file
MEMG_YAML_SCHEMA=/app/config/software_dev.yaml

# In docker-compose.yml, mount the new schema
volumes:
  - ./config/software_dev.yaml:/app/config/software_dev.yaml
```

### Option 3: Replace Default (For Testing)
```bash
# Backup original
cp config/core.minimal.yaml config/core.minimal.yaml.backup
# Replace with enhanced
cp config/software_dev.yaml config/core.minimal.yaml
# Restart server
```

## Verification Steps

1. **Check available types**:
   ```bash
   curl -X POST http://localhost:8787/tools/mcp_gmem_get_system_info
   ```
   Should show: `["memo", "document", "task", "note", "bug", "solution"]`

2. **Test new entity type**:
   ```bash
   curl -X POST http://localhost:8787/tools/mcp_gmem_add_memory \
     -H "Content-Type: application/json" \
     -d '{"memory_type": "bug", "user_id": "test", "payload": {"statement": "Test bug", "details": "Testing enhanced schema", "severity": "low", "status": "open"}}'
   ```

3. **Search and verify**:
   ```bash
   curl -X POST http://localhost:8787/tools/mcp_gmem_search_memories \
     -H "Content-Type: application/json" \
     -d '{"query": "bug", "user_id": "test", "limit": 5}'
   ```

## What Changes
- **From 4 types** → **6 types**: memo, document, task, note, bug, solution
- **Enhanced fields**: File paths, code snippets, severity levels
- **Rich relationships**: Bugs link to solutions; solutions implement tasks
- **Developer workflow**: Bug-to-fix lifecycle tracking

## Rollback Plan
```bash
# Restore original schema
cp config/core.minimal.yaml.backup config/core.minimal.yaml
# Or unset environment variable
unset MEMG_YAML_SCHEMA
# Restart server
```

The enhanced schema is backward compatible - all existing memo, document, task, note memories will continue to work unchanged.
