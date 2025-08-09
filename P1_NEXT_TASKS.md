# MEMG Core - P1 High Priority Tasks (Next Session)

## 🎯 Context for Next AI Session

**Project**: MEMG - "True memory for AI" - lightweight, open-source memory system for AI agents
**Language**: Python 3.11+, FastMCP, Docker (colima), Kuzu+Qdrant
**Architecture**: 20+ MCP tools, dual storage, user isolation

### ✅ **P0 CRITICAL TASKS COMPLETED** (Jan 2025)
All P0 critical issues have been resolved:
- **MEMG-1** ✅: mem0 → memg config references fixed
- **MEMG-2** ✅: graph_search method implemented and tested
- **MEMG-3** ✅: Qdrant add_point return handling + enum types fixed
- **MEMG-4** ✅: created_at Range filter working properly

### 🔧 **Recent Improvements Applied**
- Pre-commit hooks with ruff check for local validation
- Python 3.9+ UTC imports (cleaner than timezone.utc)
- Pydantic v2 validators (@field_validator with @classmethod)
- All timezone compatibility issues resolved

### 📋 **Current Environment Status**
- **Port**: Mix of 8787/8788 (needs standardization - see MEMG-8)
- **Tests**: ~59 tests, some import issues (see MEMG-12)
- **Required env vars**: MEMG_TEMPLATE=software_development, QDRANT_STORAGE_PATH, KUZU_DB_PATH
- **Key commands**: `./start_server.sh`, `pytest -q`, health at `/health`

---

## 🚀 P1 HIGH PRIORITY TASKS (Ready to Execute)

### **MEMG-5: Fix GraphValidator to use uppercase entity types**
- **Priority**: P1 / High
- **Description**: Validator queries currently use lowercase types (e.g., 'technology'). Update to uppercase string values (e.g., 'TECHNOLOGY').
- **Files to check**: `src/memory_system/validation/graph_validator.py`
- **Acceptance Criteria**: `validate_graph` reports non-zero counts after extractions
- **Effort**: Low (string case conversion)
- **Labels**: validation, graph

### **MEMG-12: Fix tests referencing non-existent modules/tools**
- **Priority**: P1 / High
- **Description**: Update tests that import `memory_system.mcp_server` (server resides under `integration/mcp/`). Remove/gate tests referencing unexposed tools.
- **Files to check**: `tests/test_e2e_validation.py`, other test files
- **Acceptance Criteria**: `pytest -q` runs without import errors; non-applicable tests skipped or updated
- **Effort**: Medium (test refactoring)
- **Labels**: tests, stability

### **MEMG-8: Standardize port to 8787 across code and docs**
- **Priority**: P1 / High
- **Description**: Ensure README(s), Docker, scripts, and examples consistently use 8787 (or update everything to 8788, but be consistent).
- **Files to check**: `README.md`, `dockerfiles/`, `start_server.sh`, integration examples
- **Acceptance Criteria**: All docs and health endpoints reference the same port; health checks pass
- **Effort**: Low (find/replace)
- **Labels**: docs, devops

---

## 🛠️ **Development Protocol for Next AI**

### **Memory Usage**
1. **ALWAYS search existing memories first** before answering questions
2. **Store every insight, solution, bug fix** using `mcp_gmem_add_memory`
3. **Tag systematically**: memg, P1, solution, bugfix, etc.

### **Environment Setup**
```bash
# Required environment variables
export MEMG_TEMPLATE="software_development"
export QDRANT_STORAGE_PATH="$HOME/.local/share/qdrant"
export KUZU_DB_PATH="$HOME/.local/share/kuzu/memg.db"

# Create directories
mkdir -p "$HOME/.local/share/qdrant" "$HOME/.local/share/kuzu"

# Run tests
PYTHONPATH=/Users/yasinsalimibeni/memg-core/src pytest -q
```

### **Pre-commit Validation**
```bash
# Pre-commit hooks are configured - run before committing
pre-commit run --all-files

# Or let git hooks handle it automatically
git add -A && git commit -m "Your message"
```

### **Recommended Execution Order**
1. **MEMG-5** (GraphValidator) - Quick win, improves validation
2. **MEMG-12** (Test imports) - Unblocks CI, improves reliability
3. **MEMG-8** (Port standardization) - User experience consistency

### **Success Criteria**
- All 3 P1 tasks completed and validated
- Tests pass cleanly with `pytest -q`
- Pre-commit hooks pass
- Health checks work consistently
- Documentation is accurate

---

## 📝 **Notes for Next AI**

- **Codebase is stable**: P0 foundation solid, focus on polish
- **Pre-commit works**: Ruff catches issues locally now
- **MCP tools**: 6 core tools working (add_memory, search_memories, graph_search, validate_graph, get_memory_schema, get_system_info)
- **Architecture**: Dual storage (Qdrant for vectors, Kuzu for graph), template-based entity types
- **Tests**: Some structural mypy issues remain but don't block functionality

**Ready to tackle P1 tasks with confidence! 🚀**
