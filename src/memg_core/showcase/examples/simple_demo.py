#!/usr/bin/env python3
"""Simple demo of memg-core API - 30 lines"""

import os

from memg_core import add_memory, search

# Set required environment variables
os.environ["QDRANT_STORAGE_PATH"] = "$HOME/.memg/qdrant"
os.environ["KUZU_DB_PATH"] = "$HOME/.memg/kuzu/db"
os.environ["GOOGLE_API_KEY"] = "your-api-key-here"  # Replace with actual key


def main():
    user_id = "demo_user"

    # Add a note
    note = add_memory(
        memory_type="note",
        payload={
            "content": "GraphRAG combines graph databases with vector search for better retrieval"
        },
        user_id=user_id,
        tags=["graphrag", "retrieval"],
    )
    print(f"Added note: {note.id}")

    # Add a document
    doc = add_memory(
        memory_type="document",
        payload={
            "summary": "Comprehensive guide to implementing GraphRAG systems",
            "body": "The complete GraphRAG implementation guide covers entity extraction, relationship mapping, and hybrid search strategies.",
            "title": "GraphRAG Implementation Guide",
        },
        user_id=user_id,
        tags=["documentation", "graphrag"],
    )
    print(f"Added document: {doc.id}")

    # Add a task
    task = add_memory(
        memory_type="task",
        payload={
            "summary": "Implement graph neighbor expansion for search results",
            "title": "Add neighbor expansion",
        },
        user_id=user_id,
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
