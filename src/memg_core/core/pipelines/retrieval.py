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

from ...core.exceptions import DatabaseError
from ...utils.db_clients import DatabaseClients
from ...utils.hrid_tracker import HridTracker
from ..config import get_config
from ..exceptions import ProcessingError
from ..models import EnhancedSearchResult, SearchResult
from ..retrievers.composer import compose_enhanced_result, separate_seeds_and_neighbors
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

    Attributes:
        qdrant: Qdrant interface instance.
        kuzu: Kuzu interface instance.
        embedder: Embedder instance.
        yaml_translator: YAML translator instance.
        hrid_tracker: HRID tracker instance.
    """

    def __init__(self, db_clients):
        """Initialize SearchService with DatabaseClients.

        Args:
            db_clients: DatabaseClients instance (after init_dbs() called).
        """
        if not isinstance(db_clients, DatabaseClients):
            raise TypeError("db_clients must be a DatabaseClients instance")

        # Get interfaces from DatabaseClients (reuses DDL-created clients)
        self.qdrant = db_clients.get_qdrant_interface()
        self.kuzu = db_clients.get_kuzu_interface()
        self.embedder = db_clients.get_embedder()
        self.yaml_translator = db_clients.get_yaml_translator()
        self.hrid_tracker = HridTracker(self.kuzu)
        self.config = get_config()

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
        score_threshold: float | None = None,
        enhanced_format: bool = False,
        decay_threshold: float | None = None,
    ) -> list[SearchResult] | EnhancedSearchResult:
        """GraphRAG search: vector seeds → graph expansion → semantic enhancement.

        This method encapsulates the graph_rag_search logic as a class method,
        eliminating the need to pass interfaces as parameters.

        Args:
            query: Search query text (required).
            user_id: User ID for filtering (required).
            limit: Maximum results to return (default: 5).
            memory_type: Optional memory type filter.
            relation_names: Specific relations to expand (None = all relations).
            neighbor_limit: Max neighbors per seed (default: 5).
            hops: Number of graph hops to expand (default: 1).
            include_semantic: Enable semantic expansion via see_also (default: True).
            include_details: "self" (full payload) or "none" (anchor only) for seeds.
            modified_within_days: Filter by recency (e.g., last 7 days).
            filters: Custom field-based filtering (e.g., {"project": "memg-core"}).
            projection: Control which fields to return per memory type.
            score_threshold: Minimum similarity score threshold (0.0-1.0).
            enhanced_format: Return EnhancedSearchResult with explicit seed/neighbor
                separation (default: False).
            decay_threshold: Minimum neighbor relevance threshold when
                enhanced_format=True (0.0-1.0).

        Returns:
            list[SearchResult] | EnhancedSearchResult: Legacy format or enhanced format
                based on enhanced_format parameter.
        """
        if not query or not query.strip():
            return EnhancedSearchResult() if enhanced_format else []

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
            filters=qdrant_filters,  # user_id already included by _build_qdrant_filters
            score_threshold=score_threshold,
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
            user_id=user_id,
            relation_names=relation_names,
            neighbor_limit=neighbor_limit,
            hops=hops,
            projection=projection,
            hrid_tracker=self.hrid_tracker,
            yaml_translator=self.yaml_translator,
            decay_rate=self.config.memg.decay_rate,
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

        # Handle enhanced format if requested
        if enhanced_format:
            # Use more results for better seed/neighbor separation
            all_results = results[: limit * 3] if len(results) > limit else results

            # Separate seeds and neighbors based on new semantics
            seeds, neighbors = separate_seeds_and_neighbors(all_results, limit)

            # Compose enhanced result with explicit relationships
            return compose_enhanced_result(
                seeds=seeds,
                neighbors=neighbors,
                yaml_translator=self.yaml_translator,
                query=query,
                embedder=self.embedder,
                decay_threshold=decay_threshold or self.config.memg.decay_threshold,
                decay_rate=self.config.memg.decay_rate,
            )

        # Legacy format
        return results[:limit]

    def _build_qdrant_filters(
        self,
        user_id: str,
        memory_type: str | None,
        modified_within_days: int | None,
        extra_filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build Qdrant filters from parameters with mandatory user isolation.

        Args:
            user_id: User ID for filtering (CRITICAL: included in filters dict).
            memory_type: Optional memory type filter.
            modified_within_days: Filter by recency (days).
            extra_filters: Additional custom filters.

        Returns:
            dict[str, Any]: Combined filters dictionary for Qdrant with user_id always included.

        Note:
            user_id is now included in filters dict for security validation.
        """
        # CRITICAL SECURITY: Always start with user_id
        filters: dict[str, Any] = {"user_id": user_id}

        # Add extra filters (user_id will be overridden if present, which is fine)
        if extra_filters:
            filters.update(extra_filters)

        # memory_type filter - use flat structure
        if memory_type:
            filters["memory_type"] = memory_type

        # Time-based filtering - use flat structure
        if modified_within_days and modified_within_days > 0:
            cutoff_date = datetime.now(UTC) - timedelta(days=modified_within_days)
            filters["updated_at_from"] = cutoff_date.isoformat()

        return filters

    def get_memory(
        self,
        hrid: str,
        user_id: str,
        memory_type: str | None = None,
        collection: str | None = None,
    ) -> dict[str, Any] | None:
        """Get a single memory by HRID.

        Args:
            hrid: Human-readable identifier of the memory.
            user_id: User ID for ownership verification.
            memory_type: Optional memory type hint (inferred from HRID if not provided).
            collection: Optional Qdrant collection override.

        Returns:
            dict[str, Any] | None: Memory data with full payload, or None if not found.
        """
        try:
            # Infer memory type from HRID if not provided
            if memory_type is None:
                memory_type = hrid.split("_")[0].lower()

            # Get UUID from HRID
            uuid = self.hrid_tracker.get_uuid(hrid, user_id)
            if not uuid:
                return None

            # Get memory data from Qdrant
            point_data = self.qdrant.get_point(uuid, collection)
            if not point_data:
                return None

            # Verify user ownership
            payload = point_data.get("payload", {})
            if payload.get("user_id") != user_id:
                return None

            # Build response with full memory information (HRID-only policy - no UUID exposure)
            memory_data = {
                "hrid": hrid,
                "memory_type": payload.get("memory_type", memory_type),
                "user_id": user_id,
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "payload": {
                    k: v
                    for k, v in payload.items()
                    if k
                    not in (
                        "id",
                        "user_id",
                        "memory_type",
                        "created_at",
                        "updated_at",
                        "hrid",
                    )
                },
            }

            return memory_data

        except (DatabaseError, ValueError, KeyError):
            return None

    def get_memories(
        self,
        user_id: str,
        memory_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
        include_neighbors: bool = False,
        hops: int = 1,
    ) -> list[dict[str, Any]]:
        """Get multiple memories with filtering and optional graph expansion.

        Args:
            user_id: User ID for ownership verification.
            memory_type: Optional memory type filter (e.g., "task", "note").
            filters: Optional field filters (e.g., {"status": "open", "priority": "high"}).
            limit: Maximum number of memories to return (default 50).
            offset: Number of memories to skip for pagination (default 0).
            include_neighbors: Whether to include neighbor nodes via graph traversal.
            hops: Number of hops for neighbor expansion (default 1).

        Returns:
            list[dict[str, Any]]: List of memory data with full payloads.
        """
        try:
            # Use KuzuInterface to get nodes with filtering
            results = self.kuzu.get_nodes(
                user_id=user_id,
                node_type=memory_type,
                filters=filters,
                limit=limit,
                offset=offset,
            )

            # Convert Kuzu results to SearchResult objects for expansion
            search_results = []
            for result in results:
                node_data = result.get("node", {})

                # Get HRID from UUID
                uuid = result.get("id")
                hrid = self.hrid_tracker.get_hrid(uuid, user_id) if uuid else None

                if not hrid:
                    continue

                # Build Memory object using existing utility
                memory = build_memory_from_flat_payload(
                    point_id=uuid,
                    payload={
                        **node_data,
                        "user_id": user_id,
                        "memory_type": result.get("memory_type"),
                        "created_at": result.get("created_at"),
                        "updated_at": result.get("updated_at"),
                    },
                    hrid_tracker=self.hrid_tracker,
                )

                # Create SearchResult with score 1.0 (not from vector search)
                search_result = SearchResult(
                    memory=memory,
                    score=1.0,
                    distance=None,
                    source="kuzu_query",
                    metadata={"query_type": "get_memories"},
                )
                search_results.append(search_result)

            # Apply graph expansion if requested using existing utilities
            if include_neighbors and hops > 0:
                expanded_results = _append_neighbors(
                    seeds=search_results,
                    kuzu=self.kuzu,
                    user_id=user_id,
                    relation_names=None,  # All relations
                    neighbor_limit=10,  # Reasonable limit per seed
                    hops=hops,
                    projection=None,
                    hrid_tracker=self.hrid_tracker,
                    yaml_translator=self.yaml_translator,
                    decay_rate=self.config.memg.decay_rate,
                )
                search_results = expanded_results

            # Convert SearchResult objects back to memory data format
            memories = []
            for search_result in search_results:
                memory = search_result.memory
                memory_data = {
                    "hrid": memory.hrid,  # Always return HRID for API consistency
                    "memory_type": memory.memory_type,
                    "user_id": memory.user_id,
                    "created_at": (memory.created_at.isoformat() if memory.created_at else None),
                    "updated_at": (memory.updated_at.isoformat() if memory.updated_at else None),
                    "payload": memory.payload,
                    "score": search_result.score,
                    "source": search_result.source,
                }

                # Add metadata if from neighbor expansion
                if search_result.metadata:
                    memory_data["metadata"] = search_result.metadata

                memories.append(memory_data)

            return memories

        except (DatabaseError, ValueError, KeyError):
            return []

    def get_memory_neighbors(
        self,
        memory_id: str,
        memory_type: str,
        user_id: str,
        relation_types: list[str] | None = None,
        direction: str = "any",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get related memories through graph relationships.

        Args:
            memory_id: Memory ID to find neighbors for
            memory_type: Memory entity type
            user_id: User ID for isolation
            relation_types: Filter by specific relationship types
            direction: "in", "out", or "any"
            limit: Maximum number of neighbors

        Returns:
            List of neighbor memories with relationship info
        """
        try:
            return self.kuzu.neighbors(
                node_label=memory_type,
                node_uuid=memory_id,
                user_id=user_id,
                rel_types=relation_types,
                direction=direction,
                limit=limit,
            )
        except Exception as e:
            raise ProcessingError(
                "Failed to get memory neighbors",
                operation="get_memory_neighbors",
                context={"memory_id": memory_id, "memory_type": memory_type},
                original_error=e,
            ) from e


def create_search_service(db_clients) -> SearchService:
    """Factory function to create a SearchService instance.

    Args:
        db_clients: DatabaseClients instance (after init_dbs() called).

    Returns:
        SearchService: Configured SearchService instance.
    """
    return SearchService(db_clients)
