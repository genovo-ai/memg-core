# memg_core/core/pipelines/graph_retriever.py
"""Clean GraphRAG retrieval pipelines - vector seeds → graph expansion → semantic enhancement.

True GraphRAG architecture:
1. Query → Qdrant vector search → seeds (full payloads)
2. Seeds → Kuzu graph expansion → neighbors (anchor-only payloads)
3. Optional semantic expansion using seed anchor text
4. Dedupe by ID, deterministic sorting

NO modes, NO fallbacks, NO backward compatibility.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ...utils.hrid_tracker import HridTracker
from ..models import SearchResult
from ..retrievers.expanders import _append_neighbors, _find_semantic_expansion
from ..retrievers.parsers import (
    _dedupe_and_sort,
    _project_payload,
    build_memory_from_flat_payload,
)


class SearchService:
    """Unified search service - handles all search and retrieval operations.

    Provides GraphRAG search functionality using DatabaseClients for interface access.
    Eliminates the need to pass interfaces as function parameters.
    """

    def __init__(self, db_clients):
        """Initialize SearchService with DatabaseClients.

        Args:
            db_clients: DatabaseClients instance (after init_dbs() called)
        """
        from ...utils.db_clients import DatabaseClients

        if not isinstance(db_clients, DatabaseClients):
            raise TypeError("db_clients must be a DatabaseClients instance")

        # Get interfaces from DatabaseClients (reuses DDL-created clients)
        self.qdrant = db_clients.get_qdrant_interface()
        self.kuzu = db_clients.get_kuzu_interface()
        self.embedder = db_clients.get_embedder()
        self.yaml_translator = db_clients.get_yaml_translator()
        self.hrid_tracker = HridTracker(self.kuzu)

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        *,
        memory_type: str | None = None,
        relation_names: list[str] | None = None,
        neighbor_limit: int = 5,
        hops: int = 1,
        include_semantic: bool = True,
        include_details: str = "self",
        modified_within_days: int | None = None,
        filters: dict[str, Any] | None = None,
        projection: dict[str, list[str]] | None = None,
    ) -> list[SearchResult]:
        """GraphRAG search: vector seeds → graph expansion → semantic enhancement.

        This method encapsulates the graph_rag_search logic as a class method,
        eliminating the need to pass interfaces as parameters.

        Args:
            query: Search query text (required)
            user_id: User ID for filtering (required)
            limit: Maximum results to return (default: 20)
            memory_type: Optional memory type filter
            relation_names: Specific relations to expand (None = all relations)
            neighbor_limit: Max neighbors per seed (default: 5)
            hops: Number of graph hops to expand (default: 1)
            include_semantic: Enable semantic expansion via see_also (default: True)
            include_details: "self" (full payload) or "none" (anchor only) for seeds
            modified_within_days: Filter by recency (e.g., last 7 days)
            filters: Custom field-based filtering (e.g., {"project": "memg-core"})
            projection: Control which fields to return per memory type

        Returns:
            List of SearchResult objects with HRIDs, deduplicated and sorted
        """
        if not query or not query.strip():
            return []

        # 1. Get seeds from Qdrant vector search
        query_vector = self.embedder.get_embedding(query)

        # Build filters for Qdrant
        qdrant_filters = self._build_qdrant_filters(
            user_id=user_id,
            memory_type=memory_type,
            modified_within_days=modified_within_days,
            extra_filters=filters,
        )

        # Search Qdrant for vector seeds
        vector_points = self.qdrant.search_points(
            vector=query_vector,
            limit=limit,
            user_id=user_id,
            filters=qdrant_filters,
        )

        # Convert Qdrant points to SearchResult seeds
        seeds: list[SearchResult] = []
        for point in vector_points:
            payload = point["payload"]
            point_id = point["id"]

            # Use centralized utility for Memory construction
            memory = build_memory_from_flat_payload(point_id, payload, self.hrid_tracker)

            # Project seed payload based on include_details and projection
            memory.payload = _project_payload(
                memory.memory_type,
                memory.payload,
                include_details=include_details,
                projection=projection,
                yaml_translator=self.yaml_translator,
            )

            seed_result = SearchResult(
                memory=memory,
                score=float(point["score"]),
                distance=None,
                source="qdrant",
                metadata={},
            )

            seeds.append(seed_result)

        if not seeds:
            return []

        # 2. Graph expansion (neighbors with anchor-only payloads)
        results = _append_neighbors(
            seeds=seeds,
            kuzu=self.kuzu,
            relation_names=relation_names,
            neighbor_limit=neighbor_limit,
            hops=hops,
            projection=projection,
            hrid_tracker=self.hrid_tracker,
            yaml_translator=self.yaml_translator,
        )

        # 3. Semantic expansion (optional, type-specific "see also")
        # "See also" finds semantically related memories (not graph neighbors)
        # e.g., if looking at a bug, find solutions that are semantically similar
        # to the bug's anchor text, even if not directly connected in the graph
        if include_semantic:
            semantic_results = _find_semantic_expansion(
                seeds=seeds,  # Only expand from original seeds, not neighbors
                qdrant=self.qdrant,
                embedder=self.embedder,
                user_id=user_id,
                projection=projection,
                hrid_tracker=self.hrid_tracker,
                yaml_translator=self.yaml_translator,
            )
            results.extend(semantic_results)

        # 4. Dedupe by ID and sort deterministically
        results = _dedupe_and_sort(results)

        return results[:limit]

    def _build_qdrant_filters(
        self,
        user_id: str,
        memory_type: str | None,
        modified_within_days: int | None,
        extra_filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build Qdrant filters from parameters.

        Args:
            user_id: User ID for filtering (passed to qdrant.search_points)
            memory_type: Optional memory type filter
            modified_within_days: Filter by recency (days)
            extra_filters: Additional custom filters

        Returns:
            Combined filters dictionary for Qdrant

        Note:
            user_id is not added to filters dict because it's passed separately
            to qdrant.search_points() as a parameter (see line 174-175)
        """
        filters: dict[str, Any] = extra_filters.copy() if extra_filters else {}

        # memory_type filter - use flat structure
        if memory_type:
            filters["memory_type"] = memory_type

        # Time-based filtering - use flat structure
        if modified_within_days and modified_within_days > 0:
            cutoff_date = datetime.now(UTC) - timedelta(days=modified_within_days)
            filters["updated_at_from"] = cutoff_date.isoformat()

        return filters


def create_search_service(db_clients) -> SearchService:
    """Factory function to create a SearchService instance.

    Args:
        db_clients: DatabaseClients instance (after init_dbs() called)

    Returns:
        Configured SearchService instance
    """
    return SearchService(db_clients)
