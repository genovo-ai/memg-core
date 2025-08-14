# MEMG Core Documentation

This directory contains the comprehensive documentation for the `memg-core` project, focusing on its architecture, modules, classes, and functions. The documentation is organized by module, with each Markdown file corresponding to a key component of the system.

## Start Here
- **[System Overview](SYSTEM_OVERVIEW.md)**: High-level architecture, data flow, and critical evaluation of all components

## Project Overview
MEMG Core ("True memory for AI") is a lightweight, open-source memory system designed for AI agents. It emphasizes a modular architecture with dual storage (Kuzu and Qdrant), type-agnostic memory handling via YAML registries, and a graph-first retrieval approach (GraphRAG).

## Module Documentation

### API Layer
- [`api/public.md`](api/public.md): Minimal public API for memory system interactions.

### Core Components
- [`core/config.md`](core/config.md): Configuration settings for the memory system.
- [`core/exceptions.md`](core/exceptions.md): Custom exception hierarchy for error handling.
- [`core/indexing.md`](core/indexing.md): Deprecated indexing logic (superseded by YAML translator).
- [`core/models.md`](core/models.md): Core data models (Memory, Entity, Relationship, etc.).
- [`core/yaml_translator.md`](core/yaml_translator.md): YAML to Memory translator for schema validation and anchor text generation.

#### Core Interfaces
- [`core/interfaces/embedder.md`](core/interfaces/embedder.md): FastEmbed-based text embedder.
- [`core/interfaces/kuzu.md`](core/interfaces/kuzu.md): Simple Kuzu graph database interface.
- [`core/interfaces/qdrant.md`](core/interfaces/qdrant.md): Simple Qdrant vector database interface.

#### Core Pipeline
- [`core/pipeline/indexer.md`](core/pipeline/indexer.md): Deterministic memory indexing pipeline.
- [`core/pipeline/retrieval.md`](core/pipeline/retrieval.md): Graph-first retrieval pipeline with vector reranking.

### Plugins
- [`plugins/yaml_schema.md`](plugins/yaml_schema.md): YAML schema loader for entity/relationship catalogs (to be moved to core).

### Showcase & Examples
- [`showcase/examples/simple_demo.md`](showcase/examples/simple_demo.md): A simple demonstration of the `memg-core` API.
- [`showcase/retriever.md`](showcase/retriever.md): Convenience wrappers and specialized search methods for memory retrieval.

### System Utilities
- [`system/info.md`](system/info.md): Utilities for retrieving core system information and health checks.
- [`utils/hrid.md`](utils/hrid.md): Human-Readable ID (HRID) generator and parser.
