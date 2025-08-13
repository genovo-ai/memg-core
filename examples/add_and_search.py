#!/usr/bin/env python3
"""Tiny demo: add a few memories and search using the minimal API.

Usage:
  KUZU_DB_PATH=/tmp/memg_kuzu.db QDRANT_STORAGE_PATH=/tmp/memg_qdrant python examples/add_and_search.py
"""

from __future__ import annotations

from datetime import datetime

from memg_core.api.public import add_note, add_document, add_task, search


def main():
    """Demo the minimal API: add note, document, task, then search."""
    user = "demo_user"

    print("=== Adding memories using minimal API ===")

    # Add a note
    note = add_note(
        text="Set up Postgres with Docker for local development",
        user_id=user,
        title="Docker Postgres Setup",
        tags=["docker", "postgres", "dev"],
    )
    print(f"✓ Added note: {note.id} - {note.title}")

    # Add a document
    doc = add_document(
        text="PostgreSQL tuning guide covering indexing, vacuum settings, connection pooling, and performance monitoring...",
        user_id=user,
        title="PostgreSQL Performance Guide",
        summary="Comprehensive guide for tuning PostgreSQL performance",
        tags=["postgres", "performance", "guide"],
    )
    print(f"✓ Added document: {doc.id} - {doc.title}")

    # Add a task
    task = add_task(
        text="Implement Redis cache layer for user sessions and frequently accessed data",
        user_id=user,
        title="Cache Implementation",
        due_date=datetime(2024, 12, 31),
        tags=["redis", "cache", "task"],
    )
    print(
        f"✓ Added task: {task.id} - {task.title} (due: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'None'})"
    )

    print("\n=== Searching memories (GraphRAG-first) ===")

    # Search for postgres-related memories
    results = search("postgres performance", user_id=user, limit=5)
    print(f"Found {len(results)} results for 'postgres performance':")

    for i, r in enumerate(results, 1):
        mem = r.memory
        content_preview = (
            mem.content[:60] + "..." if len(mem.content) > 60 else mem.content
        )
        print(f"{i}. [{mem.memory_type.value}] {mem.title or 'Untitled'}")
        print(f"   Content: {content_preview}")
        print(f"   Score: {r.score:.2f} | Source: {r.source}")
        print()

    # Search for cache-related memories
    print("=== Searching for 'cache' ===")
    cache_results = search("cache", user_id=user, limit=3)
    print(f"Found {len(cache_results)} results for 'cache':")

    for i, r in enumerate(cache_results, 1):
        mem = r.memory
        print(f"{i}. [{mem.memory_type.value}] {mem.title or mem.content[:30]}")
        print(f"   Score: {r.score:.2f} | Source: {r.source}")


if __name__ == "__main__":
    main()
