# MEMG Schema Specification

This document defines the structure and generation pattern of the YAML schema used in `memg-core`, an AI memory system for agents. The schema is modular, human-readable, and designed for extensibility across memory types such as notes, tasks, and documents.

---

## Overview

Each memory type is represented as an `entity`. These are structured hierarchically and support inheritance. Entities can declare `fields` (data properties) and `relations` (directed edges to other entities). The schema also defines system-wide defaults for ID generation, timestamp management, and vector embedding.

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
* `see_also`: Optional configuration for semantic discovery of related memories

#### Example: Base Entity

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

#### Example: Inherited Entity

```yaml
- name: note
  parent: memo
  description: "A simple note with a short 'details' field."
  anchor: statement
  fields:
    details: { type: string, required: true }
  relations:
    - name: note_document
      description: "Note providing additional context to a document"
      directed: true
      predicates: [ANNOTATES]
      source: note
      target: document
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

## See Also Configuration

The `see_also` field enables automatic discovery of semantically related memories through vector similarity search. When a user searches for memories of an entity type with `see_also` configured, the system automatically finds and includes related memories from specified target types.

### See Also Properties

* `enabled`: Boolean - whether to enable see_also functionality for this entity
* `threshold`: Float (0.0-1.0) - minimum similarity score required (e.g., 0.7 = 70% similarity)
* `limit`: Integer - maximum number of related memories to return per target type
* `target_types`: Array of entity type names to search for related memories

### Example: Task with See Also

```yaml
- name: task
  parent: memo
  description: "Development task or work item"
  anchor: statement
  fields:
    details: { type: string }
    status: { type: enum, choices: [todo, in_progress, done] }
  see_also:
    enabled: true
    threshold: 0.7
    limit: 3
    target_types: [bug, solution, note]
```

### See Also Behavior

When `include_see_also=true` is passed to search:

1. **Primary Search**: Normal search returns memories matching the query
2. **Related Discovery**: For each primary result with see_also config:
   - Extract anchor text from the memory
   - Search target_types for memories with similarity >= threshold
   - Return up to `limit` memories per target type
3. **Result Tagging**: Related memories have `source` field set to `see_also_{type}`

This creates knowledge graph-style associative discovery where users find relevant content they weren't explicitly searching for.

---

## Inheritance Rules

* All `fields` and `relations` declared in a `parent` entity are inherited by its children
* Children can override or extend both `fields` and `relations`
* This enables a minimal and reusable core schema for all memory types

---

## Output Requirements

The final YAML must:

* Follow standard YAML syntax
* Be suitable for direct use in the MEMG config loader
* Contain **no extra text** (comments are okay)
