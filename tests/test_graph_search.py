#!/usr/bin/env python3
"""
Unit tests for generic graph_search in MemoryRetriever.

This test avoids hitting real databases by mocking the Kuzu interface
and ensures result shape and basic filtering behavior.
"""

from datetime import datetime, timezone
from typing import List
from unittest.mock import patch

import pytest


def _fake_kuzu_results() -> List[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "m.id": "mem-1",
            "m.user_id": "u",
            "m.content": "Postgres tuning guide",
            "m.title": "DB Tips",
            "m.memory_type": "document",
            "m.created_at": now,
            "e.confidence": 0.93,
        },
        {
            "m.id": "mem-2",
            "m.user_id": "u",
            "m.content": "Using Redis as cache",
            "m.title": "Caching",
            "m.memory_type": "note",
            "m.created_at": now,
            "e.confidence": 0.88,
        },
    ]


@pytest.mark.asyncio
async def test_graph_search_basic_shape():
    from memory_system.processing.memory_retriever import MemoryRetriever

    with (
        patch("memory_system.processing.memory_retriever.QdrantInterface"),
        patch("memory_system.processing.memory_retriever.GenAIEmbedder"),
        patch("memory_system.processing.memory_retriever.KuzuInterface") as MockKuzu,
    ):
        instance = MockKuzu.return_value
        instance.query.return_value = _fake_kuzu_results()

        retriever = MemoryRetriever()
        # Force graph search enabled
        retriever.graph_enabled = True

        results = await retriever.graph_search(
            query="postgres",
            entity_types=["TECHNOLOGY", "DATABASE"],
            limit=5,
            user_id="u",
        )

        assert len(results) == 2
        first = results[0]
        assert getattr(first, "memory", None) is not None
        assert first.memory.id == "mem-1"  # type: ignore[attr-defined]
        assert first.source == "graph_search"
