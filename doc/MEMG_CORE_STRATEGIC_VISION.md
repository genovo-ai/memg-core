# MEMG Core: Strategic Vision & Aligned Roadmap

## 1. Executive Summary

This document outlines the strategic vision for `memg-core`, solidifying its identity as a truly lightweight, graph-first memory system for AI agents. The project is undergoing a deliberate refactoring to address significant scope creep, which has resulted in a codebase with reduced type errors (from 135), ~52% test coverage, and lingering enterprise-level features that contradict its core mission.

The core strategy is to **separate concerns**:
1.  **`memg-core`**: A minimal, robust, and high-performance library focused on essential memory operations (storing, retrieving) with a graph-native approach.
2.  **`memg-extras`**: A future, separate package that will house advanced, domain-specific features like complex processing pipelines, task management, and template-driven schemas.

This refactor will restore developer experience, achieve >80% test coverage, eliminate remaining type errors, and deliver a lean, dependable foundation for building intelligent applications. As an open-source project, it will be community-driven with the project lead acting as benevolent dictator to guide growth while encouraging contributions.

## 2. Motivation: Addressing Scope Creep

The `memg-core` library was conceived as a "lightweight memory system," but it organically grew to include a suite of heavy, enterprise-grade features. This expansion is the root cause of our current technical debt.

**Key Issues Stemming from Scope Creep:**
*   **Overly Complex Models**: The core `Memory` model was bloated with fields for task management (`task_status`, `story_points`), project scoping (`project_id`), and code linking (`code_file_path`), making simple memory creation a complex task.
*   **Heavy Processing Pipelines**: The inclusion of a `UnifiedMemoryProcessor`, multiple validation layers (`GraphValidator`, `PipelineValidator`), and a dynamic template system introduced significant overhead and complexity not suitable for a core library.
*   **Degraded Developer Experience**: The complexity led to a fragile system with type errors, a confusing API, and a steep learning curve for what should be a simple tool.
*   **Poor Maintainability**: Test coverage is at ~52% as the feature set outpaced our ability to write effective tests, making the system difficult to maintain and evolve safely.

Returning to our first principles—simplicity, performance, and reliability—is the primary motivation for this strategic realignment.

## 3. Solution Overview: GraphRAG-first, Minimalist Core

The solution is to architect `memg-core` around a set of clear, minimalist principles, with a strong emphasis on graph-based retrieval.

### Key Definitions
*   **GraphRAG**: A retrieval pipeline where graph queries (via Kuzu) are the primary mechanism for candidate discovery, optionally enhanced by vector reranking (via Qdrant) and neighbor appending for context.
*   **Minimal & Agnostic Types**: Core enforces a small set of memory types (`NOTE`, `DOCUMENT`, `TASK`) but allows free-form strings for entity types to remain domain-agnostic.
*   **Benevolent Dictator Model**: The project lead retains final decision-making authority (e.g., merge vetoes) while actively encouraging community contributions through clear guidelines and open issues.

### Core Principles
1.  **Graph is First-Class**: Retrieval defaults to GraphRAG (defined above).
2.  **Minimal & Agnostic Types**: As defined above.
3.  **Lean, Friendly API**: A small, intuitive public API for the most common memory operations.
4.  **No Heavy Features in Core**: Templates, complex processors, task-board semantics, and project management tools are explicitly out of scope for the core library.
5.  **Community-Driven Growth**: Foster contributions while maintaining direction under a benevolent dictator model.

### Target Architecture (Aligned with Published Code)
*   **Models** (Current: Partial alignment in `models/core.py`; simplify further to remove legacy fields like `story_points`):
    *   `Memory`: A lean model with essential fields: `id`, `user_id`, `content`, `memory_type`, and optional `title`, `tags`. `TASK` is a type of `Memory` with an optional `due_date` (no priorities or epics).
    *   `Entity`: A simple model with `name` and a free-form `type` string.
    *   `Relationship`: A simple model connecting two entities with a `type` (`RELATES_TO` or `MENTIONED_IN`).
*   **Default Retrieval Pipeline (GraphRAG)** (Current: Vector-first in `memory_retriever.py`; evolving via staged `graph_rag.py`):
    1.  **Graph Candidate Discovery (Kuzu)**: Find initial memory candidates by matching entities in the graph (e.g., `MATCH (m:Memory)-[:MENTIONS]->(e:Entity) WHERE e.name ILIKE query`).
    2.  **(Optional) Vector Rerank (Qdrant)**: Rerank the graph candidates using vector similarity for semantic relevance.
    3.  **Neighbor Append (Kuzu)**: For top-ranked results, fetch related memories (neighbors in the graph) to provide rich context.
    4.  **Fallback**: If the graph returns zero candidates, the system falls back to a pure vector search in Qdrant, followed by a neighbor append step.
*   **Indexing Policy** (Current: Deterministic in `policies/indexing.py`; staged refinements align well):
    *   Indexing is deterministic and predictable, with the text used for embedding (`index_text`) stored explicitly in the Qdrant payload for reproducibility.
    *   `NOTE` -> `content` is indexed.
    *   `DOCUMENT` -> `summary` is indexed if present; otherwise, `content`.
    *   `TASK` -> `content` (+ `title` if present) is indexed.
*   **Feature Extraction**: All non-core features will be moved to a `_stash/extras/` directory during the refactor, with the eventual goal of formalizing them in a `memg-extras` package. Import shims with deprecation warnings will ensure a smooth transition.

## 4. Implementation Stages

The refactor is structured into clear, sequential stages, allowing for incremental progress and validation. Focus on delivering value in the first release (v0.1) via the published baseline.

*   **Stage 1: Safe Extraction & API Definition (In Progress)**
    *   **Goal**: Move all non-core modules to a `_stash/extras/` directory using `git mv` to preserve history.
    *   **Tasks**:
        *   Extract complex processors, templates, prompts, and validation systems.
        *   Implement import shims with `DeprecationWarning` to avoid breaking existing integrations immediately.
        *   Define and document a minimal public API (`add_note`, `add_document`, `search`).
    *   **Status**: Planning is complete, and initial file moves are underway. Aligns with staged config changes.

*   **Stage 2: Core Simplification & Quality Uplift**
    *   **Goal**: Refine the core codebase to be lean, well-tested, and type-safe.
    *   **Tasks**:
        *   Refactor `models/core.py` to reflect the minimal model definitions.
        *   Rewrite `processing/memory_retriever.py` to implement the GraphRAG-first pipeline.
        *   Increase test coverage from ~52% to over 70%, with a final target of 80%.
        *   Run `pyright` and fix all type errors to achieve a "type-clean" state.

*   **Stage 3: CI Hardening & Documentation**
    *   **Goal**: Ensure long-term stability and provide clear guidance for users and contributors.
    *   **Tasks**:
        *   Strengthen the CI pipeline by enforcing coverage thresholds and testing against multiple Python versions.
        *   Add a container smoke test to validate the MCP build.
        *   Author a `MIGRATION.md` guide for users of the legacy features.
        *   Polish all user-facing documentation (`README.md`).

*   **Stage 4 (Future): Extras & Extensibility**
    *   **Goal**: Formalize advanced features and introduce controlled extensibility.
    *   **Tasks**:
        *   Create and publish a `memg-extras` package containing the features extracted from the core.
        *   Introduce an optional, YAML-driven ontology system (behind a feature flag) to allow users to define their own types and retrieval policies without modifying core code.

## 5. Current Progress & Next Steps

*   **Current State** (Based on Published Code on origin/main):
    *   The core codebase has been significantly slimmed down, with legacy processors, templates, and validation logic removed from the main source tree.
    *   The primary retrieval logic resides in `MemoryRetriever`, which is slated for the GraphRAG refactor (staged progress in graph_rag.py).
    *   **Metrics**: Tests at **39 passed, 6 skipped**, and coverage at **~52%**. Type errors have been drastically reduced from 135. Staged changes (e.g., indexing.py) align with vision but need pushing.

*   **Immediate Next Steps (P1 Priorities)**:
    1.  **Fix `GraphValidator`**: Align the validator with the correct uppercase entity types to ensure it functions correctly.
    2.  **Stabilize Tests**: Resolve import errors in the test suite to create a reliable CI signal.
    3.  **Standardize Configuration**: Ensure the default port is consistent across all documentation, scripts, and code.

## 6. Risks and Mitigations (New Section)

To ensure a successful first release and community growth, address these risks:

*   **Risk: Breaking Changes for Users**: Legacy fields (e.g., story_points) removal could disrupt adopters.
  *   **Mitigation**: Use shims with warnings; provide MIGRATION.md in v0.1; announce on GitHub.

*   **Risk: Incomplete GraphRAG in First Release**: Published code is vector-heavy, delaying "graph-first" value.
  *   **Mitigation**: Prioritize minimal GraphRAG in Stage 2; release v0.1 as "vector baseline" with roadmap.

*   **Risk: Low Community Engagement**: As benevolent dictator, unbalanced governance could deter contributors.
  *   **Mitigation**: Add CONTRIBUTING.md with clear rules; label "good first issues"; engage via Discussions.

*   **Risk: Technical Debt Persistence**: Coverage at ~52% risks bugs in contributions.
  *   **Mitigation**: Enforce CI gates; aim for 60% in v0.1.

This strategic vision provides a clear path to transforming `memg-core` into the lean, powerful, and reliable memory system it was always meant to be, with a focus on community-driven growth.
