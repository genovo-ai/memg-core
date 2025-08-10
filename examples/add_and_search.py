#!/usr/bin/env python3
"""Tiny demo: add a few memories and search graph-first.

Usage:
  KUZU_DB_PATH=/tmp/memg_kuzu.db QDRANT_STORAGE_PATH=/tmp/memg_qdrant python examples/add_and_search.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from memg_core.application.memory import add_memory, search_memories
from memg_core.models.core import Memory, MemoryType


def seed() -> None:
    user = "demo_user"
    notes = [
        Memory(user_id=user, content="Set up Postgres with Docker", memory_type=MemoryType.NOTE),
        Memory(user_id=user, content="Use Redis for caching", memory_type=MemoryType.NOTE),
    ]
    doc = Memory(
        user_id=user,
        content="PostgreSQL tuning guide...",
        summary="Guide for tuning Postgres",
        title="DB Tips",
        memory_type=MemoryType.DOCUMENT,
    )
    for m in notes + [doc]:
        add_memory(m)


async def main():
    seed()
    results = await search_memories("postgres", user_id="demo_user", limit=5)
    for r in results:
        mem = r.memory
        print(f"- {mem.memory_type.value}: {mem.title or mem.content[:30]}... (score={r.score:.2f}, source={r.source})")


if __name__ == "__main__":
    asyncio.run(main())
