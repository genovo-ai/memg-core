# YAML-driven Types for memg-core (Concise Proposal)

## Motivation
- Keep core tiny and domain-agnostic by moving catalogs out of code
- Expand or shrink capabilities by swapping YAML, not releasing code
- Single source of truth for entity/relationship types and query groups
- Prepare clean growth path for memg (full) and extras to extend safely

## Idea
- One YAML defines: entity_types, relationship_types, type_groups, aliases, schema_version
- A loader validates the YAML and exposes:
  - runtime enums (EntityType, RelationshipType)
  - group lookup (get_group(name) → list of strings)
  - alias normalization (normalize_type(name) → canonical)
- Default YAML mirrors current enums; override via environment path

## Risks (with mitigations)
- Dynamic enums reduce static typing → strict validation, cached build, helper introspection
- Bad YAML → schema-validated load, fallback to default, clear warnings, health shows active schema
- Query drift if groups change → versioned groups, tests pin critical groups, deprecation warnings
- Import cycles → isolate loader; models import only values from it

## Implementation (phased)
- Phase 0: Add `schemas/default_types.yaml`; implement `utils/type_registry` (load/validate/cache); feature flag `MEMG_TYPES_FROM_YAML`
- Phase 1: `models/core.py` consumes registry-provided enums (values unchanged)
- Phase 2: `memory_retriever` uses `type_groups` for graph queries instead of hardcoded lists
- Phase 3: Ops knobs: `MEMG_TYPES_PATH`; health/system info returns schema_version and counts
- Phase 4: Deprecate docs about static enums; keep fallback switch for safety

## Stack choices
- YAML parsing: PyYAML (safe_load)
- Validation: Pydantic model for YAML structure (strict)
- Packaging: importlib.resources to bundle default YAML
- Caching: functools.lru_cache for schema, enums, groups
- Config: MEMG_TYPES_FROM_YAML, MEMG_TYPES_PATH, MEMG_TYPES_SCHEMA_VERSION

## Acceptance criteria
- Default behavior identical; tests stay green
- Swapping YAML updates types/groups without code changes
- Health reports active schema version and counts

## Rollback
- Set `MEMG_TYPES_FROM_YAML=false` to restore static enums

## Effort
- ~1–2 days including retriever refactor and docs

## Fit with core
- Preserves a slim, stable core while enabling controlled expansion via configuration rather than code edits
