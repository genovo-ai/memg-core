# MEMG Core: Types, Entities, Prompts, and Processing Flows

## Enums / Types
- MemoryType: document, note, conversation, task
- TaskStatus: backlog, todo, in_progress, in_review, done, cancelled
- TaskPriority: low, medium, high, critical
- ImportanceLevel: LOW, MEDIUM, HIGH, CRITICAL
- RelationshipStrength: WEAK, MODERATE, STRONG, ESSENTIAL
- RelationshipType: MENTIONED_IN, RELATES_TO, USED_IN, WORKS_WITH, PART_OF, SIMILAR_TO
- EntityType (16 core + task mgmt): TECHNOLOGY, DATABASE, LIBRARY, TOOL, COMPONENT, SERVICE, ARCHITECTURE, PROTOCOL, ERROR, ISSUE, SOLUTION, WORKAROUND, CONCEPT, METHOD, CONFIGURATION, FILE_TYPE, TICKET, EPIC, MILESTONE, SPRINT, BOARD

## Core Models
- Memory (core fields with defaults; only user_id, content required)
- Entity (type = EntityType)
- Relationship (source_id, target_id, relationship_type)
- Project (optional scoping)
- MemoryPoint (memory + vector)
- SearchResult (memory + score + source + metadata)
- ProcessingResult (summaries of created items)

## Prompts
- Prompts directory removed from core in current branch; no prompt files present.
- GenAI utility provides structured/text generation interfaces (uses google-genai).

## Extraction / Processing Flows
- Unified/legacy processors removed from core; not present in this branch.
- Current active processing component: MemoryRetriever (search).

### MemoryRetriever Search Flow
1. Generate embedding for query via GenAIEmbedder
2. Build Qdrant filters (supports days_back -> ISO timestamp)
3. Qdrant search_points(vector, limit, user_id, filters)
4. Convert raw results to Memory + SearchResult objects
   - Reconstruct Memory from payload (id, user_id, content, summary, title, source, tags, confidence, created_at, project fields, supersession fields)
   - Filter by score_threshold and invalid memories (config.memg.enable_temporal_reasoning)
5. Sort results by score; annotate relevance tier

### Graph Flows (enabled if KuzuInterface available or MEMG_ENABLE_GRAPH_SEARCH=true)
- search_by_technology(tech_name): MATCH (m)-[:MENTIONS]->(e) with type in [TECHNOLOGY, DATABASE, LIBRARY, TOOL, FRAMEWORK]
- find_error_solutions(error_description): combine graph-first search over ERROR/ISSUE + SOLUTION/WORKAROUND with semantic fallback; merge/dedupe by memory.id
- search_by_component(component_name): types [COMPONENT, SERVICE, ARCHITECTURE, PROTOCOL]
- graph_search(query, entity_types?): generic entity name match with optional type filter
- All graph queries ultimately call _convert_kuzu_to_search_results which builds Memory and SearchResult

## Configuration Highlights
- MemGConfig: thresholds, AI verification, temporal reasoning, vector dimension, batch size, template name, collection/db paths
- System: port 8787, host 0.0.0.0 (intentional; bandit ignored via #nosec)

## Missing / Extracted from Core (now external)
- templates/: empty placeholder (moved out)
- validation/: empty placeholder (moved out)
- prompts/: removed in this branch
- processing/unified_memory_processor.py, processing/memory_processor.py: removed

## Current Status & Next Stage Plan

### Current Baseline (Updated)
- **Tests**: 39 passed, 6 skipped (improved from 55 passed, 5 skipped)
- **Coverage**: ~52% (improved from 40%)
- **Type Errors**: Significantly reduced (was 135 errors in 15 files)
- **CI**: Minimal but functional; Docker MCP build enabled; PyPI disabled

### Current Flow Summary
- **Write path (processing)**: externalized; not in core
- **Read path (retrieval)**: MemoryRetriever -> QdrantInterface (+ optional Kuzu graph) -> SearchResult
- **Models**: Pydantic v2 core models with defaults; enums define standard types

### Next Stages (from MEMG_CORE_NEXT_STAGE_PLAN.md)
**Stage 1**: Minimal Core API (add_note, add_document, search) + Documentation
**Stage 2**: Coverage 52% → 70%+ and Type-Safety (pyright = 0 errors)
**Stage 3**: CI Hardening + Python matrix (3.11, 3.12)
**Stage 4**: Documentation Polish + Developer Experience
