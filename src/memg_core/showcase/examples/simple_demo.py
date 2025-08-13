#!/usr/bin/env python3
"""Simple demo of memg-core API - 30 lines"""

import os

from memg_core import add_document, add_note, add_task, search

# Set required environment variables
os.environ["QDRANT_STORAGE_PATH"] = "$HOME/.memg/qdrant"
os.environ["KUZU_DB_PATH"] = "$HOME/.memg/kuzu/db"
os.environ["GOOGLE_API_KEY"] = "your-api-key-here"  # Replace with actual key


def main():
    user_id = "demo_user"

    # Add a note
    note = add_note(
        text="GraphRAG combines graph databases with vector search for better retrieval",
        user_id=user_id,
        tags=["graphrag", "retrieval"],
    )
    print(f"Added note: {note.id}")

    # Add a document
    doc = add_document(
        text="The complete GraphRAG implementation guide covers entity extraction, relationship mapping, and hybrid search strategies.",
        user_id=user_id,
        title="GraphRAG Implementation Guide",
        summary="Comprehensive guide to implementing GraphRAG systems",
        tags=["documentation", "graphrag"],
    )
    print(f"Added document: {doc.id}")

    # Add a task
    task = add_task(
        text="Implement graph neighbor expansion for search results",
        user_id=user_id,
        title="Add neighbor expansion",
        tags=["enhancement", "search"],
    )
    print(f"Added task: {task.id}")

    # Search memories
    results = search(
        query="graphrag implementation",
        user_id=user_id,
        limit=5,
    )

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(
            f"{i}. {result.memory.title or result.memory.content[:50]}... (score: {result.score:.3f})"
        )


if __name__ == "__main__":
    main()
