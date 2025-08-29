# Changelog

All notable changes to memg-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MkDocs documentation site with Material theme
- Comprehensive API reference documentation
- Usage guide with examples and configuration details
- GitHub Actions workflow for automated documentation deployment

### Changed
- Improved README with badges and better structure
- Enhanced project metadata for PyPI integration

## [0.1.0] - 2024-01-XX

### Added
- Initial release of memg-core
- YAML-based schema definition system
- Dual-store backend (Qdrant + Kuzu)
- Public Python API for memory operations
- Vector search with semantic similarity
- Graph storage for relationships
- Offline-first embeddings with FastEmbed
- User isolation and HRID-based memory identification
- See Also discovery for associative memory retrieval
- Support for custom memory types via YAML schemas
- Built-in schemas for common use cases (memo, note, document, task, bug, solution)
- Comprehensive test suite
- Development tools (linting, type checking, testing)

### Features
- **Memory Operations**: Add, search, delete memories with full CRUD support
- **Schema Flexibility**: Define custom memory types without code changes
- **Performance**: Optimized for fast semantic search and retrieval
- **Reliability**: Deterministic behavior with comprehensive error handling
- **Developer Experience**: Clean API, good documentation, extensive testing

### Technical Details
- Python 3.11+ support
- FastEmbed for local embeddings (no API keys required)
- Qdrant for vector storage and similarity search
- Kuzu for graph relationships and complex queries
- Pydantic for data validation and serialization
- Comprehensive type hints and documentation
