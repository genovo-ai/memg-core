# MEMG Core: Implementation Blueprint (ADHD-Friendly Coding Spec)

## Quick Intro (Read This First – 1 Min)
This is NOT vision—it's a **code-now** guide. Each task is small (30-60 mins), with:
- **Why?** (Human need: Why code this? ADHD win: Quick value.)
- **Current Code State**: What's there now (from reads/searches).
- **What to Code**: Exact steps.
- **Claude Prompt**: Copy-paste this to Claude (or me) for code gen.
- **Test It**: How to verify.

Prioritized for v0.1 release: Slim basics first, then GraphRAG. Use Python 3.11+, fix linter errors.

**Total Time Estimate**: 1-2 days for core tasks. Push to main after each.

## Task 1: Slim Down Memory Model (Remove Bloat)
- **Why?** Humans need simple models (no task-board junk). ADHD win: Quick refactor, instant cleanup feel.
- **Current Code State** (from read_file): `models/core.py` has `Memory` with legacy fields (task_status, story_points, epic_id, etc.). EntityType enum is huge (21 items). No free-form yet.
- **What to Code**:
  1. Remove task fields except optional `due_date` for TASK.
  2. Make EntityType free-form str (remove enum).
  3. Update to_qdrant_payload() to match.
- **Claude Prompt** (Copy-Paste This):
  ```
  Here's the current Memory model from src/memg_core/models/core.py: [paste the full file contents here].

  Refactor it to be minimal:
  - Keep essentials: id, user_id, content, memory_type (enum: NOTE, DOCUMENT, TASK), title, tags, created_at.
  - For TASK: Add optional due_date (datetime | None).
  - Remove all other task fields (task_status, priority, story_points, epic_id, etc.) and code linking (code_file_path, etc.).
  - Change EntityType from enum to free-form str.
  - Update methods like to_qdrant_payload() and validators to match.
  - Fix any linter errors (ruff). Output the full updated file.
  ```
- **Test It**: Run `pytest tests/test_basic.py`. Add a simple test: Create Memory(type="TASK", due_date=datetime.now()).

## Task 2: Implement Minimal Public API
- **Why?** Humans need easy entry (add_note in 1 line). ADHD win: Visible progress—run examples/add_and_search.py.
- **Current Code State** (from layout): No explicit API file; sync_wrapper.py has wrappers but is bloated.
- **What to Code**:
  1. Create src/memg_core/api.py with functions: add_note(text, user_id, title=None, tags=[]), add_document(...), search(query, user_id=None, limit=20).
  2. Wrap existing retriever/indexing.
- **Claude Prompt**:
  ```
  Using MEMG-Core codebase (dual Kuzu/Qdrant storage), create a new file src/memg_core/api.py with minimal API:
  - def add_note(text: str, user_id: str, title: str=None, tags: list[str]=[]) -> Memory: Use indexing.py to embed/store.
  - Similar for add_document and add_task (with optional due_date).
  - def search(query: str, user_id: str=None, limit: int=20) -> list[SearchResult]: Call memory_retriever.py.
  - Import from models/core.py (assume slimmed). Make async-friendly. Output the file.
  ```
- **Test It**: Update examples/add_and_search.py to use new API. Run it.

## Task 3: Make Retrieval GraphRAG-First (Basic Version)
- **Why?** Core value: Graph over vector. ADHD win: See search results improve immediately.
- **Current Code State** (from grep/search): memory_retriever.py is vector-first; graph_rag.py has graph_rag_search (entity matching), but no full pipeline (discovery → rerank → append).
- **What to Code**:
  1. Update memory_retriever.py: Default to graph_rag_search, then optional Qdrant rerank, append neighbors (limit 5).
  2. Add fallback to pure vector if graph empty.
- **Claude Prompt**:
  ```
  Current retrieval in src/memg_core/processing/memory_retriever.py is vector-first. graph_rag.py has graph_rag_search.

  Refactor memory_retriever.py for GraphRAG default:
  - Call graph_rag_search for candidates.
  - Optional: Rerank with Qdrant (if >0 candidates).
  - Append neighbors (Kuzu query, limit 5).
  - Fallback: If 0 graph candidates, pure Qdrant search + append.
  - Update search() to use this. Output updated file.
  ```
- **Test It**: Run pytest test_graph_search.py. Query with example data.

## Task 4: Enforce Indexing Policy with Payload Storage
- **Why?** Reproducibility = trust. ADHD win: One-file change, testable.
- **Current Code State** (from search): indexing.py has get_index_text; Qdrant interface stores payloads but not explicit index_text.
- **What to Code**:
  1. In qdrant/interface.py, add 'index_text' to payload in add_point().
  2. Update get_index_text in indexing.py for types.
- **Claude Prompt**:
  ```
  In src/memg_core/policies/indexing.py, get_index_text exists. Qdrant interface adds points without storing index_text.

  Update:
  - indexing.py: Ensure get_index_text handles NOTE (content), DOCUMENT (summary or content), TASK (content + title).
  - qdrant/interface.py: In add_point, include 'index_text' in payload.
  - Output both updated files.
  ```
- **Test It**: Add memory, query Qdrant to verify payload.

## Next: Release & Community
- After these, tag v0.1: git tag v0.1 && git push --tags.
- Add CONTRIBUTING.md: "Welcome PRs! I (benevolent dictator) review all."

## Real AI Power
- Uses Google Gemini embeddings (no fake/mock stuff)
- Quality over cost - we invest in real AI for superior results
- Set `GOOGLE_API_KEY` environment variable

Feed these prompts to Claude one-by-one. If you want me to code them instead, say the word!
