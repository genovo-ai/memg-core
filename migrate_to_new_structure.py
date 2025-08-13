#!/usr/bin/env python3
"""Migration guide from old memg_core to new memg_core structure"""

print("""
MEMG-CORE REFACTORING MIGRATION GUIDE
=====================================

The refactoring is complete! Here's how to migrate:

1. IMPORTS TO UPDATE:
   ------------------
   OLD: from memg_core.models.core import Memory, MemoryType
   NEW: from memg_core.core.models import Memory, MemoryType

   OLD: from memg_core.qdrant.interface import QdrantInterface
   NEW: from memg_core.core.interfaces.qdrant import QdrantInterface

   OLD: from memg_core.kuzu_graph.interface import KuzuInterface
   NEW: from memg_core.core.interfaces.kuzu import KuzuInterface

   OLD: from memg_core.utils.embeddings import GenAIEmbedder
   NEW: from memg_core.core.interfaces.embedder import GenAIEmbedder

   OLD: from memg_core.processing.memory_retriever import MemoryRetriever
   NEW: from memg_core.showcase.retriever import MemoryRetriever

   OLD: from memg_core.api import add_note, add_document, add_task, search
   NEW: from memg_core import add_note, add_document, add_task, search

2. REMOVED FEATURES:
   -----------------
   - Async variants moved to showcase/wrappers.py (or dropped)
   - ConversationSummary, Message, MessagePair moved out of core
   - Many entity/relationship enums simplified (now just strings)
   - Complex indexing policies moved to plugins

3. NEW STRUCTURE:
   --------------
   memg_core/
     core/              # Stable, minimal core
       models.py        # Core data models
       config.py        # Configuration
       exceptions.py    # 5 exception classes only
       logging.py       # Logging utilities
       indexing.py      # Deterministic indexing
       interfaces/      # Pure I/O adapters
       pipeline/        # Indexing and retrieval
     api/
       public.py        # 4 sync functions only
     plugins/
       yaml_schema.py   # Optional YAML support
     showcase/
       retriever.py     # Convenience wrappers
       examples/        # Demo scripts
     system/
       info.py          # System information

4. KEY CHANGES:
   ------------
   - Interfaces are now pure I/O (no business logic)
   - Single writer pattern: only pipeline/indexer.py writes to stores
   - Single reader pattern: only pipeline/retrieval.py does GraphRAG
   - YAML support is optional via plugin
   - Public API reduced to 4 functions

5. TO COMPLETE MIGRATION:
   ----------------------
   a) Update all imports in your code
   b) Test with: python test_refactor.py
   c) Update pyproject.toml to point to memg_core
   d) Run your tests
   e) Once verified, rename memg_core to memg_core

6. ENVIRONMENT VARIABLES:
   ----------------------
   No changes - same env vars work:
   - QDRANT_STORAGE_PATH (required)
   - KUZU_DB_PATH (required)
   - GOOGLE_API_KEY (required)
   - MEMG_ENABLE_YAML_SCHEMA (optional)
   - MEMG_YAML_SCHEMA (optional)
""")
