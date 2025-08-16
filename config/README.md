# MEMG Schema Specification

This document defines the structure and generation pattern of the YAML schema used in `memg-core`, an AI memory system for agents. The schema is modular, human-readable, and designed for extensibility across memory types.

---

## Available Schema Files

- **`core.memo.yaml`**: Minimal schema with just the base `memo` entity
- **`core.test.yaml`**: Extended schema with `memo` and `memo_test` entities for development/testing
- **Custom schemas**: Can be created following the patterns below

---

## Overview

Each memory type is represented as an `entity`. Entities can declare `fields` (data properties) and `relations` (directed edges to other entities). The schema also defines system-wide defaults for ID generation, timestamp management, and vector embedding.

---

## Schema Sections

### `version`

Schema version identifier.

### `id_policy`

Controls how unique IDs are assigned. Typically:

```yaml
id_policy:
  kind: uuid
  field: id
```

### `defaults`

Defines system-level defaults:

```yaml
defaults:
  vector:
    metric: cosine
    normalize: true
  timestamps:
    auto_create: true
    auto_update: true
```

### `entities`

Each object in the `entities` list is a memory unit definition.

#### Entity Fields:

* `name`: Unique identifier for the entity
* `parent`: Optional parent entity name (for inheritance)
* `description`: Human-readable summary
* `anchor`: Field to use as semantic reference (used for vectorization)
* `fields`: Field map with types and constraints
* `relations`: List of directed links from/to other entities

#### Example: Base Entity (`core.memo.yaml`)

```yaml
- name: memo
  description: "Base memory unit"
  anchor: statement
  fields:
    id:          { type: string, required: true, system: true }
    user_id:     { type: string, required: true, system: true }
    statement:   { type: string, required: true, max_length: 8000 }
    created_at:  { type: datetime, required: true, system: true }
    updated_at:  { type: datetime, system: true }
    vector:      { type: vector, derived_from: statement, system: true }
  relations:
    - name: memo_related
      description: "Generic relation between memos"
      directed: true
      predicates: [RELATED_TO]
      source: memo
      target: memo
```

#### Example: Extended Entity (`core.test.yaml`)

```yaml
- name: memo_test
  description: "Ad-hoc test entity combining note, task, and document"
  anchor: statement
  fields:
    id:         { type: string, required: true, system: true }
    user_id:    { type: string, required: true, system: true }
    statement:  { type: string, required: true, max_length: 8000 }
    details:    { type: string }  # optional for doc/note-style
    status:     { type: enum, choices: [backlog, todo, in_progress, in_review, done, cancelled] }
    priority:   { type: enum, choices: [low, medium, high, critical] }
    assignee:   { type: string }
    due_date:   { type: datetime }
    created_at: { type: datetime, required: true, system: true }
    updated_at: { type: datetime, system: true }
    vector:     { type: vector, derived_from: statement, system: true }
  relations:
    - name: memo_test_related
      description: "Generic relation between test memos"
      directed: true
      predicates: [RELATED_TO, ANNOTATES, SUPPORTS, REFERENCED_BY]
      source: memo_test
      target: memo_test
```

---

## Field Types

* `string`, `datetime`, `enum`, `vector`
* `required`: boolean
* `system`: boolean (reserved for system-use fields)
* `derived_from`: used for vector fields
* `choices`: array (for `enum` types)

---

## Relation Properties

* `name`: Unique identifier for the relation
* `description`: Human-readable
* `directed`: If true, relation has source → target direction
* `predicates`: One or more semantics for the link (e.g., `ANNOTATES`, `REFERENCED_BY`)
* `source`: Origin entity type
* `target`: Destination entity type

---

## Schema Design Patterns

### Core Entity Pattern
The `memo` entity serves as the foundational memory unit with essential fields:
- **System fields**: `id`, `user_id`, `created_at`, `updated_at`, `vector` (automatically managed)
- **Content field**: `statement` (the primary content, used for vectorization via `anchor`)
- **Relations**: Generic `RELATED_TO` connections between memos

### Extended Entity Pattern
The `memo_test` entity demonstrates how to extend functionality:
- **All core memo fields** plus additional optional fields
- **Task-like fields**: `status`, `priority`, `assignee`, `due_date`
- **Document-like fields**: `details` for extended content
- **Rich relations**: Multiple predicates (`RELATED_TO`, `ANNOTATES`, `SUPPORTS`, `REFERENCED_BY`)

### Custom Schema Creation
To create custom schemas:
1. Start with the `memo` base entity (or copy from `core.memo.yaml`)
2. Add entities with domain-specific fields (following `memo_test` pattern)
3. Define meaningful relations between entities
4. Use inheritance sparingly - flat entities are often clearer

---

## Usage

### Setting Schema in Environment
```bash
# Use minimal schema (memo only)
export MEMG_YAML_SCHEMA=config/core.memo.yaml

# Use test schema (memo + memo_test)  
export MEMG_YAML_SCHEMA=config/core.test.yaml

# Use custom schema
export MEMG_YAML_SCHEMA=config/my_custom.yaml
```

### Schema Validation Requirements

The final YAML must:
* Follow standard YAML syntax
* Be suitable for direct use in the MEMG config loader
* Contain **no extra text** (comments are okay)
* Include at least one entity with required system fields
* Define valid field types and relation structures
