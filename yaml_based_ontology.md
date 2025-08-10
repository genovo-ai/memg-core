TL;DR

Single YAML Registry defines EntityTypes and RelationTypes.
Each Entity has an auto id, timestamps, and exactly one anchor (string) used for embedding.
Relations are typed, directed, and use predicate enums (small vocabulary).
Copy–paste the spec + starter registry below.

⸻

memg Core Definitions (authoring spec)

# === Core concept mini-spec (put in docs or policy) ===
spec:
  version: v1

  definitions:
    EntityType:
      summary: >
        A named schema for instances ("entities") with fields, one 'anchor' string,
        and a runtime-managed embedding derived from that anchor.
      must_have:
        - name (string, snake_case)
        - description (string)
        - anchor (field name; must be a string field)
        - fields (map[name -> FieldSpec])
        - system fields: id:string, created_at:datetime, updated_at:datetime, embedding:vector
      notes:
        - Only one anchor per EntityType
        - 'embedding' is derived_from: anchor

    FieldSpec:
      summary: Primitive, enum, tags, json, or vector.
      attrs:
        - type: [string,int,float,bool,datetime,date,enum,tags,json,vector,ref]
        - required: bool (default false)
        - choices: [for enum]
        - max_length: int (optional)
        - default: any (optional)
        - dim: int [vector]
        - derived_from: fieldname [vector]
        - description: string (recommended)
        - system: bool (runtime-managed)

    RelationType:
      summary: >
        A named link type with fixed predicate enum(s), direction,
        and source/target EntityType constraints.
      must_have:
        - name (string, snake_case)
        - description (string)
        - directed: bool
        - predicates: [enum values]
        - source: EntityType name or "*" (any)
        - target: EntityType name or "*" (any)
      notes:
        - Keep predicate vocabulary small and clear

    Registry:
      summary: A collection of EntityTypes and RelationTypes under an id policy and defaults.
      must_have:
        - version: v1
        - id_policy: {kind: ulid|uuid|snowflake, field: id}
        - entities: [EntityType...]
        - relations: [RelationType...]
        - defaults: { vector: {metric, normalize, dim}, timestamps: {auto_create, auto_update} }

  predicates_vocabulary:
    - RELATED
    - HAS_NOTE
    - HAS_DOCUMENT
    - BELONGS_TO
    - PART_OF
    - MENTIONS
    - DERIVED_FROM
    - ALIAS_OF
    - SIMILAR_TO
    - SOLVES
    - DUPLICATES


⸻

Starter Registry (drop-in)

# registry.v1.yaml
version: v1

id_policy:
  kind: ulid
  field: id

defaults:
  vector:
    metric: cosine
    normalize: true
    dim: 1024
  timestamps:
    auto_create: true
    auto_update: true

entities:
  - name: note
    description: "Short free-form note."
    anchor: content
    fields:
      id:          { type: string, required: true, system: true, description: "ULID" }
      content:     { type: string, required: true, max_length: 8000, description: "Note text" }
      tags:        { type: tags, description: "Labels for filtering" }
      created_at:  { type: datetime, required: true, system: true }
      updated_at:  { type: datetime, system: true }
      embedding:   { type: vector, dim: 1024, derived_from: content, system: true }

  - name: document
    description: "Document with a summary used as the embedding anchor."
    anchor: summary
    fields:
      id:          { type: string, required: true, system: true }
      title:       { type: string, required: true }
      summary:     { type: string, required: true, max_length: 4000 }
      url:         { type: string }
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      updated_at:  { type: datetime, system: true }
      embedding:   { type: vector, dim: 1024, derived_from: summary, system: true }

  - name: task
    description: "Actionable item."
    anchor: description
    fields:
      id:          { type: string, required: true, system: true }
      title:       { type: string, required: true }
      description: { type: string, required: true }
      status:      { type: enum, choices: [todo, doing, done], default: todo }
      due:         { type: date }
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      updated_at:  { type: datetime, system: true }
      embedding:   { type: vector, dim: 1024, derived_from: description, system: true }

  - name: bug
    description: "Defect found in software."
    anchor: description
    fields:
      id:          { type: string, required: true, system: true }
      title:       { type: string, required: true }
      description: { type: string, required: true }
      severity:    { type: enum, choices: [low, medium, high, critical], default: medium }
      status:      { type: enum, choices: [open, triaged, fixed, wontfix], default: open }
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      updated_at:  { type: datetime, system: true }
      embedding:   { type: vector, dim: 1024, derived_from: description, system: true }

  - name: solution
    description: "Proposed or implemented fix."
    anchor: summary
    fields:
      id:          { type: string, required: true, system: true }
      summary:     { type: string, required: true }
      details:     { type: string }
      tags:        { type: tags }
      created_at:  { type: datetime, required: true, system: true }
      updated_at:  { type: datetime, system: true }
      embedding:   { type: vector, dim: 1024, derived_from: summary, system: true }

relations:
  # Generic attachments usable by any module
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

  # General association across types (use sparingly)
  - name: association
    description: "Generic association between entities."
    directed: true
    predicates: [RELATED]
    source: "*"
    target: "*"

  # Software module: bug ↔ solution
  - name: bug_solution
    description: "Link between bug and solution."
    directed: true
    predicates: [RELATED, SOLVES]   # SOLVES flows solution -> bug
    source: solution
    target: bug
    constraints:
      unique_per_predicate: true

  # Structural relations for task/doc
  - name: task_document
    description: "Task references supporting document."
    directed: true
    predicates: [RELATED]
    source: task
    target: document


⸻

How the Registry Works (examples)

1) Create an entity instance (runtime fills system fields)

# input (author/user provides)
bug:
  title: "Null pointer in planner"
  description: "Repro: call memory.plan with empty filters..."
  severity: high
  status: triaged
  tags: [planner, crash]

# runtime result (after apply id_policy, timestamps, embedding)
bug:
  id: "01J8X6HP7M5N2A3B4C5D6E7F8G"
  title: "Null pointer in planner"
  description: "Repro: call memory.plan with empty filters..."
  severity: high
  status: triaged
  tags: [planner, crash]
  created_at: "2025-08-10T16:21:00Z"
  updated_at: "2025-08-10T16:21:00Z"
  embedding: "VECTOR://derived_from:description"  # actual vector stored in DB

2) Create a relation instance

edge:
  relation: bug_solution
  predicate: SOLVES
  from: "solution:01J8X6S0..."
  to:   "bug:01J8X6HP..."

3) Attach a note to anything

note:
  content: "Workaround: guard null before hop"
# runtime returns note ULID → then:
edge:
  relation: has_note
  predicate: HAS_NOTE
  from: "bug:01J8X6HP..."
  to:   "note:01J8X6WQ..."

4) Query planner intent (filter → vector → relations)
	•	Filter by status: open, vector search over anchor embedding, expand via bug_solution:SOLVES.

query_plan:
  entity: bug
  filters:
    status: open
  vector:
    field: embedding
    text: "planner crash null pointer"
    top_k: 20
  relations:
    expand:
      - relation: bug_solution
        predicate: SOLVES
        direction: inbound
        max_neighbors: 5


⸻

Pydantic-ready type stubs (optional)

from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Literal

ScalarType = Literal["string","int","float","bool","datetime","date","enum","tags","json","vector","ref"]

class FieldSpec(BaseModel):
    type: ScalarType
    required: bool = False
    description: Optional[str] = None
    choices: Optional[List[str]] = None
    max_length: Optional[int] = None
    default: Optional[object] = None
    dim: Optional[int] = None
    derived_from: Optional[str] = None
    system: bool = False

class EntityType(BaseModel):
    name: str
    description: str
    anchor: str
    fields: Dict[str, FieldSpec]

    @field_validator("anchor")
    def anchor_exists_and_string(cls, v, info):
        fields = info.data.get("fields", {})
        assert v in fields, "anchor must be a defined field"
        assert fields[v].type == "string", "anchor must be a string field"
        return v

class RelationType(BaseModel):
    name: str
    description: str
    directed: bool = True
    predicates: List[str]
    source: str   # EntityType name or "*"
    target: str   # EntityType name or "*"
    constraints: Optional[Dict[str, object]] = None

class IdPolicy(BaseModel):
    kind: Literal["ulid","uuid","snowflake"] = "ulid"
    field: str = "id"

class Registry(BaseModel):
    version: Literal["v1"]
    id_policy: IdPolicy
    entities: List[EntityType]
    relations: List[RelationType]
    defaults: Dict[str, Dict[str, object]]
