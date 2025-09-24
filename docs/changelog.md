# Changelog

All notable changes to memg-core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Enhanced Search Control**: New `include_details` parameter with "none", "self", and "all" options
  - "none": Show only anchor text for both seeds and neighbors (minimal)
  - "self": Show full payload for seeds, anchor only for neighbors (default)
  - "all": Show full payload for both seeds and neighbors (maximum detail)
- **YAML-Based Datetime Formatting**: Configure default datetime format in YAML schema
  - Automatic application of format without per-request configuration
  - Custom format override still available per search request
  - Clean, consistent datetime output across all operations
- **Override Fields System**: New YAML schema section for display customization
  - `display_field`: Custom display text that overrides anchor field
  - `force_display`: List of fields to always include in results
  - `exclude_display`: List of fields to never include in results
  - Proper precedence: exclude > force > include_details > anchor protection
  - **Computed `display_text` field**: Automatically added to search results, prioritizes `display_field` over anchor field
  - **Vectorization separation**: Anchor field always used for embedding, `display_field` only affects display
- **Enhanced Models**: Updated Pydantic models to support both datetime objects and formatted strings
- **Comprehensive Test Suite**: 16 new tests covering all new functionality
- MkDocs documentation site with Material theme
- Comprehensive API reference documentation
- Usage guide with examples and configuration details
- GitHub Actions workflow for automated documentation deployment

### Changed
- **API Enhancement**: Added `datetime_format` parameter to search functions
- **Model Updates**: `MemorySeed` and `MemoryNeighbor` now accept `datetime | str` for timestamps
- **Documentation**: Updated usage guide with new features and examples
- Improved README with badges and better structure
- Enhanced project metadata for PyPI integration

### Technical Details
- **Backward Compatibility**: All existing APIs continue to work unchanged
- **Performance**: No performance impact - new features are opt-in
- **Type Safety**: Strong typing maintained throughout with proper annotations
- **Error Handling**: Graceful handling of invalid override field types

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
