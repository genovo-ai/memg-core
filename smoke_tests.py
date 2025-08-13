#!/usr/bin/env python3
"""Minimal smoke tests for core functionality"""

import os
import sys
import tempfile
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set up test environment
test_dir = tempfile.mkdtemp()
os.environ["QDRANT_STORAGE_PATH"] = os.path.join(test_dir, "qdrant")
os.environ["KUZU_DB_PATH"] = os.path.join(test_dir, "kuzu", "db")
os.environ["GOOGLE_API_KEY"] = "test-key"  # Will need real key for actual tests

print(f"Test directory: {test_dir}")

def test_vector_fallback():
    """Test A: Vector fallback when graph is empty"""
    print("\n=== Test A: Vector fallback ===")

    from memg_core import add_note, search

    # Add one note
    note = add_note(
        text="alpha beta gamma",
        user_id="test_user",
        title="Test Note"
    )
    print(f"✓ Added note: {note.id}")

    # Search for it
    results = search(
        query="alpha beta",
        user_id="test_user",
        limit=5
    )

    print(f"✓ Found {len(results)} results")
    assert len(results) >= 1, "Should find at least one result"

    # Check source
    sources = {r.source for r in results}
    print(f"✓ Sources: {sources}")
    assert sources & {"graph_rerank", "vector_fallback"}, f"Expected graph_rerank or vector_fallback, got {sources}"

    # If graph is empty, expect vector_fallback
    if "vector_fallback" in sources:
        print("✓ Got vector_fallback (graph was empty)")
    else:
        print("✓ Got graph_rerank")

    print("✅ Test A passed!")


def test_graph_first_with_neighbors():
    """Test B: Graph-first search with neighbor expansion"""
    print("\n=== Test B: Graph-first + neighbors ===")

    from memg_core import add_note
    from memg_core.core.interfaces.kuzu import KuzuInterface
    from memg_core.api.public import search

    # Add two memories
    note1 = add_note(
        text="The GraphRAG system uses entity extraction",
        user_id="test_user",
        tags=["graphrag"]
    )
    print(f"✓ Added note1: {note1.id}")

    note2 = add_note(
        text="Entity extraction enables better search",
        user_id="test_user",
        tags=["search"]
    )
    print(f"✓ Added note2: {note2.id}")

    # Create a relation between them in Kuzu
    kuzu = KuzuInterface()

    # First create Entity nodes for the relation
    kuzu.add_node("Entity", {
        "id": "entity_graphrag",
        "user_id": "test_user",
        "name": "GraphRAG",
        "type": "TECHNOLOGY",
        "description": "Graph-based retrieval augmented generation",
        "confidence": 0.9,
        "created_at": datetime.utcnow().isoformat(),
        "is_valid": True,
        "source_memory_id": note1.id
    })

    # Create MENTIONS relationships
    kuzu.add_relationship(
        from_table="Memory",
        to_table="Entity",
        rel_type="MENTIONS",
        from_id=note1.id,
        to_id="entity_graphrag",
        props={"confidence": 0.9, "user_id": "test_user"}
    )
    print("✓ Created relation in Kuzu")

    # Search with neighbor_cap
    results = search(
        query="GraphRAG",
        user_id="test_user",
        limit=10
    )

    print(f"✓ Found {len(results)} results")

    # Check sources
    sources = {r.source for r in results}
    print(f"✓ Sources: {sources}")

    # Count neighbors
    neighbor_results = [r for r in results if r.source == "graph_neighbor"]
    print(f"✓ Neighbor results: {len(neighbor_results)}")

    # Default neighbor_cap is 5 (from env)
    assert len(neighbor_results) <= 5, f"Expected <= 5 neighbors, got {len(neighbor_results)}"

    print("✅ Test B passed!")


def test_document_indexing():
    """Test C: Document indexing is deterministic"""
    print("\n=== Test C: Document indexing ===")

    from memg_core import add_document
    from memg_core.core.interfaces.qdrant import QdrantInterface

    # Test 1: Document with no summary
    doc1 = add_document(
        text="This is the document content",
        user_id="test_user",
        title="Doc without summary"
    )
    print(f"✓ Added doc1 (no summary): {doc1.id}")

    # Check index_text in Qdrant
    qdrant = QdrantInterface()
    point1 = qdrant.get_point(doc1.id)
    assert point1 is not None, "Should find doc1 in Qdrant"

    index_text1 = point1["payload"].get("index_text")
    print(f"✓ Doc1 index_text: {index_text1}")
    assert index_text1 == "This is the document content", f"Expected content as index_text, got {index_text1}"

    # Test 2: Document with summary
    doc2 = add_document(
        text="This is the document content that is very long",
        user_id="test_user",
        title="Doc with summary",
        summary="Short summary"
    )
    print(f"✓ Added doc2 (with summary): {doc2.id}")

    # Check index_text in Qdrant
    point2 = qdrant.get_point(doc2.id)
    assert point2 is not None, "Should find doc2 in Qdrant"

    index_text2 = point2["payload"].get("index_text")
    print(f"✓ Doc2 index_text: {index_text2}")
    assert index_text2 == "Short summary", f"Expected summary as index_text, got {index_text2}"

    print("✅ Test C passed!")


def main():
    """Run all smoke tests"""
    try:
        # Note: These tests require a real GOOGLE_API_KEY for embeddings
        # Set it before running: export GOOGLE_API_KEY="your-key"

        test_vector_fallback()
        test_graph_first_with_neighbors()
        test_document_indexing()

        print("\n🎉 All smoke tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"\n✓ Cleaned up test directory: {test_dir}")


if __name__ == "__main__":
    main()
