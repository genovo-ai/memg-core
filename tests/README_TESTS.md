# MEMG Core Test Suite

## Overview
Comprehensive test suite for MEMG Core with proper CI/local separation to handle database dependencies safely.

## Test Categories & Database Dependencies

### ✅ CI-Safe Tests (7 tests)
**Can run in build/CI environments** - No database dependencies

- **Unit Tests** (`tests/unit/`)
  - `test_yaml_schema.py` - YAML validation and schema logic

- **API Error Handling** (`tests/api/test_public_api.py`)
  - `test_add_memory_returns_hrid` - Return type validation
  - `test_add_memory_invalid_type` - Input validation errors
  - `test_add_memory_missing_required_fields` - Required field validation
  - `test_delete_nonexistent_memory` - Error handling for missing data

### 🏠 Local-Only Tests (17 tests)
**Require writable databases** - Local development only

- **System Integration** (`tests/test_system_ready.py`)
  - Full end-to-end system functionality tests
  - Performance baseline tests

- **User Isolation** (`tests/test_user_isolation.py`)
  - Multi-user data isolation tests
  - Access control and security tests

- **API Integration** (`tests/api/test_public_api.py`)
  - Database write operations
  - Search functionality tests
  - User isolation in API layer

### Why Tests Fail in CI
Local-only tests fail with: `sqlite3.OperationalError: attempt to write a readonly database`

This happens because they require:
- **Qdrant** (vector database) - write operations for embeddings
- **Kuzu** (graph database) - write operations for relationships
- **File system** - database files need write permissions

## Running Tests

### Quick Commands
```bash
# CI-safe tests only (for build environments)
python scripts/test_runner.py --ci

# Local tests only (requires database setup)
python scripts/test_runner.py --local

# All tests
python scripts/test_runner.py --all

# Show test categorization
python scripts/test_runner.py --check
```

### Manual pytest Commands
```bash
# CI-safe tests (using markers - RECOMMENDED)
pytest -m "unit" -v

# CI-safe tests (manual selection)
pytest tests/unit/ tests/api/test_public_api.py::TestPublicAPIErrorHandling -v

# Local-only tests
pytest tests/test_system_ready.py tests/test_user_isolation.py -v

# All tests
pytest tests/ -v
```

### CI/Build Pipeline Usage
The GitHub workflow automatically runs only CI-safe tests:
```yaml
# In .github/workflows/workflow.yml
- name: Tests (CI-Safe Only)
  run: python -m pytest -m "unit" -v --cov=src --cov-report=xml --cov-report=term-missing
```

This command:
- ✅ Runs only the 7 unit tests marked with `@pytest.mark.unit`
- ✅ Automatically skips all 17 database-dependent tests
- ✅ Provides coverage reporting for CI
- ✅ No database setup required

## Test Strategy Details

### 1. Original Test Categories

#### Unit Tests (`tests/unit/`)
- **YAML Schema Tests**: Validate schema loading, entity creation, field validation
- **HRID Generation Tests**: Deterministic HRID generation, counter persistence, format validation
- **Type Registry Tests**: Entity model creation, inheritance, field mapping
- **Interface Tests**: Individual database interface operations (mocked)

#### Integration Tests (`tests/integration/`)
- **End-to-End Memory Operations**: Full add/search/delete cycles with real databases
- **User Isolation Tests**: Ensure no data leakage between users
- **Persistence Tests**: Data survives database restarts
- **Search Accuracy Tests**: Verify search results match expectations

#### API Tests (`tests/api/`)
- **Public API Interface**: Test add_memory(), search(), delete_memory()
- **HRID-Only Surface**: Ensure UUIDs never exposed in public API
- **Error Handling**: Proper exception handling and user-friendly errors
- **Input Validation**: Schema validation, required fields, type checking

### 2. Test Configuration

#### Test YAML Schema (`config/core.test.yaml`)
Using simplified schema with:
- **memo**: Base entity (statement, user_id, timestamps)
- **note**: Extends memo (project, origin fields)
- **document**: Extends memo (details, url fields)
- **Relations**: note↔document with ANNOTATES/REFERENCED_BY predicates

#### Test Data Strategy
- **Deterministic**: Same inputs always produce same outputs
- **User Isolation**: Each test uses unique user_id
- **Clean State**: Each test starts with fresh database
- **Minimal**: Use only essential fields from test schema

### 3. Key Test Requirements

#### ✅ HRID-Only Public API
- Public functions return/accept only HRIDs
- UUIDs used internally but never exposed
- HRID format validation: `TYPE_XXX###`

#### ✅ User Data Isolation
- User A cannot see User B's memories
- Search results filtered by user_id
- HRID counters isolated per user

#### ✅ Data Persistence
- Memories survive database restarts
- HRID mappings persist correctly
- Search indexes remain consistent

#### ✅ Search Accuracy
- **True Positives**: Find relevant memories
- **True Negatives**: Exclude irrelevant memories
- **False Positives**: Minimize irrelevant results
- **False Negatives**: Minimize missed relevant results

#### ✅ Schema Compliance
- YAML validation works correctly
- Required fields enforced
- Optional fields handled properly
- Inheritance works as expected

### 4. Test Organization

```
tests/
├── README_TESTS.md           # This file
├── conftest.py              # Shared fixtures and utilities
├── unit/
│   ├── test_yaml_schema.py  # YAML loading, validation
│   ├── test_hrid_system.py  # HRID generation, persistence
│   ├── test_type_registry.py # Entity models, inheritance
│   └── test_interfaces.py   # Database interface units
├── integration/
│   ├── test_memory_lifecycle.py # Add→Search→Delete cycles
│   ├── test_user_isolation.py   # Multi-user scenarios
│   ├── test_persistence.py      # Database restart scenarios
│   └── test_search_accuracy.py  # Search quality validation
├── api/
│   ├── test_public_api.py    # Public function interface
│   ├── test_hrid_surface.py  # HRID-only validation
│   └── test_error_handling.py # Exception scenarios
└── data/
    └── test_memories.json    # Standardized test data
```

### 5. CI/CD Compliance

#### GitHub Workflow Requirements (`.github/workflows/workflow.yml`)
- **Python 3.11**: Match workflow environment
- **Quality Gates**: Bandit, Ruff, Pylint (≥7.0), MyPy
- **Test Coverage**: pytest with coverage reporting
- **Environment**: Temp directories for Qdrant/Kuzu

#### Test Execution
```bash
# Local development
pytest tests/ -v --cov=src --cov-report=term-missing

# CI environment (matches workflow)
QDRANT_STORAGE_PATH=temp_data/qdrant KUZU_DB_PATH=temp_data/kuzu/ci_test.db \
pytest tests/ -v --cov=src --cov-report=xml --cov-report=term-missing
```

### 6. Success Criteria

- [ ] All tests pass in CI environment
- [ ] Code coverage ≥90% for core modules
- [ ] No UUID exposure in public API
- [ ] User isolation verified with concurrent tests
- [ ] Search accuracy meets quality thresholds
- [ ] YAML schema validation comprehensive
- [ ] Performance benchmarks within acceptable ranges

### 7. Implementation Plan

1. **Setup & Cleanup**: Create conftest.py with database fixtures
2. **Unit Tests**: Start with YAML and HRID tests (fastest feedback)
3. **Integration Tests**: Build up to full memory lifecycle tests
4. **API Tests**: Validate public interface compliance
5. **Performance**: Add benchmarks for search and storage operations
6. **Documentation**: Update with test results and coverage reports

---

**Note**: This test suite replaces ad-hoc testing with systematic validation ensuring MEMG Core is production-ready for main branch integration.
