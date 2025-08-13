#!/usr/bin/env python3
"""Test script to verify the refactored memg_core structure"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test imports
print("Testing imports...")

try:
    # Test core imports
    from memg_core.core.models import Memory, MemoryType, Entity, Relationship, SearchResult
    print("✓ Core models imported")

    from memg_core.core.config import get_config, MemGConfig
    print("✓ Core config imported")

    from memg_core.core.exceptions import MemorySystemError, DatabaseError, NetworkError
    print("✓ Core exceptions imported")

    from memg_core.core.logging import get_logger, setup_memory_logging
    print("✓ Core logging imported")

    from memg_core.core.indexing import build_index_text
    print("✓ Core indexing imported")

    # Test interfaces
    from memg_core.core.interfaces.qdrant import QdrantInterface
    from memg_core.core.interfaces.kuzu import KuzuInterface
    from memg_core.core.interfaces.embedder import GenAIEmbedder
    print("✓ Core interfaces imported")

    # Test pipeline
    from memg_core.core.pipeline.indexer import add_memory_index
    from memg_core.core.pipeline.retrieval import graph_rag_search
    print("✓ Core pipeline imported")

    # Test API
    from memg_core.api.public import add_note, add_document, add_task, search
    print("✓ API public functions imported")

    # Test plugins
    from memg_core.plugins.yaml_schema import load_yaml_schema, get_relation_names
    print("✓ Plugins imported")

    # Test showcase
    from memg_core.showcase.retriever import MemoryRetriever
    print("✓ Showcase imported")

    # Test system
    from memg_core.system.info import get_system_info
    print("✓ System utilities imported")

    # Test main package
    from memg_core import add_note, add_document, add_task, search, __version__
    print("✓ Main package exports imported")

    print("\n✅ All imports successful!")

    # Test basic functionality
    print("\nTesting basic functionality...")

    # Create a memory object
    memory = Memory(
        user_id="test_user",
        content="Test memory content",
        memory_type=MemoryType.NOTE,
        title="Test Note"
    )
    print(f"✓ Created memory: {memory.id}")

    # Test index text generation
    index_text = build_index_text(memory)
    print(f"✓ Generated index text: {index_text[:50]}...")

    # Test config
    config = get_config()
    print(f"✓ Loaded config: template={config.memg.template_name}")

    print("\n✅ Basic functionality tests passed!")

except ImportError as e:
    print(f"\n❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
