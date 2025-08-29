# Usage Guide

This guide covers installation, configuration, and common usage patterns for memg-core.

## Installation

### From PyPI

```bash
pip install memg-core
```

### Development Setup

```bash
# 1) Clone the repository
git clone https://github.com/genovo-ai/memg-core.git
cd memg-core

# 2) Create virtualenv and install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) For development, install dev dependencies
pip install -r requirements-dev.txt

# 4) Run tests
export YAML_PATH="config/core.test.yaml"
export QDRANT_STORAGE_PATH="$HOME/.local/share/qdrant"
export KUZU_DB_PATH="$HOME/.local/share/kuzu/memg"
mkdir -p "$QDRANT_STORAGE_PATH" "$HOME/.local/share/kuzu"
PYTHONPATH=$(pwd)/src pytest -q
```

## Configuration

Configure memg-core using environment variables:

### Required Variables

```bash
# Storage paths
export QDRANT_STORAGE_PATH="/path/to/qdrant"
export KUZU_DB_PATH="/path/to/kuzu/database"
export YAML_PATH="config/core.memo.yaml"
```

### Optional Variables

```bash
# Embeddings configuration
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"  # Default

# For MCP server (if using)
export MEMORY_SYSTEM_MCP_PORT=8787
```

## YAML Schema Configuration

memg-core uses YAML schemas to define memory types. Core ships with example schemas:

- `config/core.memo.yaml`: Basic memory types (`memo`, `note`, `document`, `task`)
- `config/software_dev.yaml`: Enhanced schema with `bug` and `solution` types
- `config/core.test.yaml`: Test configuration for development

### Using Different Schemas

```bash
# Basic schema
export YAML_PATH="config/core.memo.yaml"

# Enhanced development schema
export YAML_PATH="config/software_dev.yaml"

# Test schema
export YAML_PATH="config/core.test.yaml"
```

## Basic Operations

### Adding Memories

```python
from memg_core.api.public import add_memory

# Add a simple note
note_hrid = add_memory(
    memory_type="note",
    payload={
        "statement": "Remember to update the API documentation",
        "project": "docs-update"
    },
    user_id="user123"
)
print(f"Created: {note_hrid}")  # Returns "NOTE_AAA001"

# Add a document with more details
doc_hrid = add_memory(
    memory_type="document",
    payload={
        "statement": "API Authentication Guide",
        "details": "Complete guide for implementing JWT authentication in our API",
        "project": "backend-auth",
        "url": "https://wiki.company.com/auth-guide"
    },
    user_id="user123"
)

# Add a task
task_hrid = add_memory(
    memory_type="task",
    payload={
        "statement": "Implement user registration endpoint",
        "assignee": "john.doe",
        "priority": "high",
        "status": "in_progress",
        "project": "backend-auth"
    },
    user_id="user123"
)
```

### Searching Memories

```python
from memg_core.api.public import search

# Basic search
results = search(
    query="authentication API",
    user_id="user123",
    limit=10
)

for result in results:
    memory = result.memory
    print(f"[{memory.memory_type}] {memory.hrid}: {memory.payload['statement']}")
    print(f"Score: {result.score:.3f}")
    print("---")

# Search with memory type filtering
task_results = search(
    query="registration",
    user_id="user123",
    memory_type="task",
    limit=5
)

# Search with project filtering
project_results = search(
    query="backend authentication",
    user_id="user123",
    project="backend-auth",
    limit=10
)
```

### Deleting Memories

```python
from memg_core.api.public import delete_memory

# Delete by HRID
success = delete_memory(hrid="NOTE_AAA001", user_id="user123")
print(f"Deletion successful: {success}")

# Delete by UUID (if you have it)
success = delete_memory(memory_id="550e8400-e29b-41d4-a716-446655440000", user_id="user123")
```

## Advanced Usage

### Memory Types and Schemas

The available memory types depend on your YAML schema. Common types include:

#### Basic Types (core.memo.yaml)
- **memo**: Simple statements or observations
- **note**: Notes with optional project association
- **document**: Structured documents with details and optional URLs
- **task**: Task items with assignee, priority, and status

#### Enhanced Types (software_dev.yaml)
- **bug**: Bug reports with severity, status, and reproduction steps
- **solution**: Solutions with code snippets and test status

### Working with Projects

Use the `project` field to organize memories:

```python
# Add memories to a project
add_memory(
    memory_type="note",
    payload={"statement": "Database migration notes", "project": "v2-migration"},
    user_id="user123"
)

# Search within a project
results = search(
    query="migration",
    user_id="user123",
    project="v2-migration"
)
```

### Embedding Configuration

memg-core uses FastEmbed for local, offline embeddings:

```python
# Default model (recommended)
export EMBEDDER_MODEL="Snowflake/snowflake-arctic-embed-xs"

# Alternative models
export EMBEDDER_MODEL="intfloat/e5-small"
export EMBEDDER_MODEL="BAAI/bge-small-en-v1.5"
```

### User Isolation

All operations are user-scoped. Each user has their own:
- Memory namespace
- HRID sequences (NOTE_AAA001, NOTE_BBB001, etc.)
- Search results

```python
# User A's memories
add_memory(memory_type="note", payload={"statement": "User A note"}, user_id="userA")

# User B's memories (completely isolated)
add_memory(memory_type="note", payload={"statement": "User B note"}, user_id="userB")

# Search only returns memories for the specified user
results_a = search(query="note", user_id="userA")  # Only User A's memories
results_b = search(query="note", user_id="userB")  # Only User B's memories
```

## Error Handling

```python
from memg_core.core.exceptions import MemgCoreError

try:
    result = add_memory(
        memory_type="invalid_type",
        payload={"statement": "This will fail"},
        user_id="user123"
    )
except MemgCoreError as e:
    print(f"Error: {e}")
```

## Performance Tips

1. **Batch Operations**: For multiple memories, consider batching your operations
2. **Appropriate Limits**: Use reasonable search limits (5-50 results typically)
3. **Memory Types**: Use specific memory type filters when possible
4. **Project Filtering**: Leverage project-based filtering for better performance

## Troubleshooting

### Common Issues

1. **Storage Path Errors**: Ensure storage directories exist and are writable
2. **YAML Schema Errors**: Validate your YAML schema file exists and is valid
3. **Memory Type Errors**: Ensure memory types match your YAML schema
4. **User Isolation**: Remember that all operations are user-scoped

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Checking Configuration

```python
from memg_core.core.config import get_config

config = get_config()
print(f"YAML Path: {config.yaml_path}")
print(f"Qdrant Path: {config.qdrant_storage_path}")
print(f"Kuzu Path: {config.kuzu_db_path}")
```
