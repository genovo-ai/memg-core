# MEMG Core + YAML Registry Design

This document defines how MEMG Core separates the minimal, type-agnostic memory model from type definitions that live in YAML registries. It also lists the concrete steps required to fully enable the YAML-driven approach.

## Goals

- Keep the core memory contract minimal, stable, and extensible.
- Define entities and relations in YAML registries (shippable with core or external libraries).
- Use a single, explicit anchor text per entity type for embeddings and similarity search.
- Eliminate hardcoded memory types from core; support user- and library-defined types seamlessly.

## Core Concepts

- **Anchor text**: The single string field in an entity that is embedded for vector search and revealed as the primary text in similarity results.
- **Registry**: A YAML file that declares `EntityType` and `RelationType` definitions plus defaults and id policy.
- **Translator**: Code that loads, validates, and exposes the registry at runtime, providing anchor lookups, field constraints, and relation names.

## Core Memory Contract (type-agnostic)

Core memory must not encode product-specific types. It should provide only the primitives necessary for indexing and retrieval:

- `id` (string; generated via id policy)
- `user_id` (string; multi-tenant isolation)
- `memory_type` (string; must match a registry entity name)
- `tags` (list[string])
- `confidence` (float 0..1)
- `is_valid` (bool)
- `created_at` (datetime)
- `supersedes` / `superseded_by` (string | null) for lineage
- `vector` (list[float] | null) for Qdrant (may be filled by pipeline)
- `payload` (dict) flexible typed fields (e.g., `content`, `summary`, `description`, etc.) that are validated against the registry

The core exposes a single capability related to embeddings:

- `anchor_text(memory) -> str` — returns the content of the anchor field for the given `memory_type`, validated via the registry. This is the only text embedded and used for similarity search.

## YAML Registry Schema

Top-level structure (aligned with `yaml_based_ontology.md`):

- `version: v1`
- `id_policy`: `{ kind: ulid|uuid|snowflake, field: id }`
- `defaults`:
  - `vector`: `{ metric, normalize, dim }`
  - `timestamps`: `{ auto_create, auto_update }`
- `entities`: list of `EntityType`
- `relations`: list of `RelationType`

EntityType:

- `name` (string, snake_case)
- `description` (string)
- `anchor` (string; must refer to a string field defined in `fields`)
- `fields` (map of `FieldSpec`)

FieldSpec:

- `type`: one of `[string, int, float, bool, datetime, date, enum, tags, json, vector, ref]`
- `required`: bool (default false)
- `choices`: list[string] (for enum)
- `max_length`: int (optional)
- `default`: any (optional)
- `dim`: int (for vector)
- `derived_from`: string (for vector)
- `system`: bool (true when runtime-managed)

RelationType:

- `name` (string, snake_case)
- `description` (string)
- `directed` (bool)
- `predicates`: list of enum names (small vocabulary)
- `source`: entity type or `"*"`
- `target`: entity type or `"*"`
- `constraints`: optional map (e.g., `unique_per_predicate: true`)

### Predicates Vocabulary (starter)

`RELATED, HAS_NOTE, HAS_DOCUMENT, BELONGS_TO, PART_OF, MENTIONS, DERIVED_FROM, ALIAS_OF, SIMILAR_TO, SOLVES, DUPLICATES`

## Starter Registry (built-in)

We ship a minimal registry that defines the three generic types with explicit anchors:

- `note`: anchor = `content`
- `document`: anchor = `summary`
- `task`: anchor = `summary`

Example snippet:

```yaml
version: v1

id_policy:
  kind: ulid
  field: id

defaults:
  vector:
    metric: cosine
    normalize: true
    dim: 384  # must align with runtime EMBEDDING_DIMENSION_LEN
  timestamps:
    auto_create: true
    auto_update: true

entities:
  - name: note
    description: "Short free-form note."
    anchor: content
    fields:
      id:          { type: string, required: true, system: true }
      content:     { type: string, required: true, max_length: 8000 }
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      embedding:   { type: vector, dim: 384, derived_from: content, system: true }

  - name: document
    description: "Document where summary is the embedding anchor."
    anchor: summary
    fields:
      id:          { type: string, required: true, system: true }
      title:       { type: string, required: true }
      summary:     { type: string, required: true, max_length: 4000 }
      body:        { type: string }  # full doc content
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      embedding:   { type: vector, dim: 384, derived_from: summary, system: true }

  - name: task
    description: "Actionable item with summary and description."
    anchor: summary
    fields:
      id:          { type: string, required: true, system: true }
      summary:     { type: string, required: true }
      description: { type: string }
      status:      { type: enum, choices: [todo, in_progress, in_review, done, cancelled], default: todo }
      priority:    { type: enum, choices: [low, medium, high, critical], default: medium }
      due:         { type: date }
      assignee:    { type: string }
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      embedding:   { type: vector, dim: 384, derived_from: summary, system: true }

relations:
  - name: has_note
    description: "Attach notes to any entity."
    directed: true
    predicates: [HAS_NOTE]
    source: "*"
    target: note

  - name: has_document
    description: "Attach documents to any entity."
    directed: true
    predicates: [HAS_DOCUMENT]
    source: "*"
    target: document
```

## Translator Responsibilities

The translator (currently `src/memg_core/plugins/yaml_schema.py`, to be made core) must:

1. Load the registry from `MEMG_YAML_SCHEMA` and cache it.
2. Validate against Pydantic definitions (see `yaml_based_ontology.md` stubs).
3. Expose:
   - `get_entity_anchor(entity_type: str) -> str`
   - `get_relation_names() -> list[str]`
   - `get_entity_schema(entity_type: str) -> dict`
   - `build_anchor_text(memory: Memory) -> str` (strict; no silent fallback)
4. Enforce required fields and types on input payloads.
5. Fail fast: missing registry, unknown `memory_type`, or invalid anchor must raise errors.

## Indexing and Retrieval

- On index:
  - Extract `anchor_text` via translator.
  - Compute embedding and store vector in Qdrant.
  - Store full entity payload (including non-anchor details such as `document.body` and `task.description`) in Qdrant payload and map core fields into Kuzu.

- On retrieval:
  - Return `anchor_text` as the primary snippet.
  - Include full payload and metadata for rendering/grounding.
  - Optionally expand via relations from Kuzu when requested.

## API Shape

- Introduce a generic `add_memory(memory_type: str, payload: dict, user_id: str, tags?: list[str], ...)` that:
  - Validates `memory_type` and `payload` against the registry.
  - Derives `anchor_text` and embeddings.
  - Stores to Qdrant/Kuzu.

- Keep convenience wrappers as thin helpers:
  - `add_note(...)`, `add_document(...)`, `add_task(...)` → call `add_memory` with appropriate `memory_type`.

## Migration Plan (make YAML core)

1. Registry files:
   - Add `integration/config/core.minimal.yaml` with `note`, `document`, `task` (anchors per above).
   - Optionally add `core.software_dev.yaml` and `core.knowledge.yaml` later.

2. Core types decoupling:
   - In `src/memg_core/core/models.py`:
     - Replace `MemoryType` enum with plain `memory_type: str`.
     - Move task-only fields out of core into `payload` validated by registry.
     - Keep existing generic fields and conversion helpers; ensure they map `payload` appropriately.

3. Translator hardening:
   - Move `yaml_schema.py` from plugin semantics to core utility; remove `MEMG_ENABLE_YAML_SCHEMA` gating.
   - Add strict validation with Pydantic stubs; surface clear exceptions.
   - Rename `build_index_text_with_yaml` → `build_anchor_text` and make it required.

4. Pipeline updates:
   - `src/memg_core/pipeline/indexer.py` and `retrieval.py` to rely on `build_anchor_text` for embeddings.
   - Ensure Qdrant payload includes full `payload` and minimal core properties.
   - Ensure Kuzu nodes/edges encode `memory_type`, tags, timestamps, and references.

5. API updates:
   - Implement generic `add_memory(...)` and refactor wrappers to call it.
   - Maintain backward compatibility for wrapper signatures.

6. README and docs:
   - Update README to reflect YAML as core, not optional.
   - Reference the shipped registries and `MEMG_YAML_SCHEMA` configuration.

7. Configuration alignment:
   - Align `defaults.vector.dim` with `EMBEDDING_DIMENSION_LEN` (use 384 across code and registry by default).
   - Confirm model default (`Snowflake/snowflake-arctic-embed-xs`) dimension compatibility.

8. Tests:
   - Unit tests for translator (load/validate/anchors/relations).
   - Unit tests for `add_memory` validation and anchor extraction.
   - Pipeline tests (indexing/retrieval) with the starter registry.
   - E2E test ensuring non-core custom type from a test registry is accepted and searchable.

## Operational Notes

- Env vars:
  - `MEMG_YAML_SCHEMA=/path/to/registry.yaml` (required for normal operation)
  - `EMBEDDING_DIMENSION_LEN=384` (must match registry defaults)
- Docker images should include a default registry under `/app/integration/config/core.minimal.yaml` and set `MEMG_YAML_SCHEMA` accordingly, while allowing overrides.

## Decisions (final)

- Anchors:
  - `note` → `content`
  - `document` → `summary`
  - `task` → `summary`

- Strictness: No silent fallbacks; registry is the source of truth. Missing/invalid anchors or unknown types are hard errors.

## FAQ

- Why anchor only one field?
  - Simplicity and better embedding signal. Summaries are less diluted and perform better in similarity search.

- Where do long bodies live?
  - In the Qdrant payload (and optionally in Kuzu as truncated fields). The anchor text alone is embedded.

- How do downstream libraries add types?
  - Ship their own registry YAML. Point `MEMG_YAML_SCHEMA` to it. No core changes required.
