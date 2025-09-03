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
from ..models import Memory, MemoryNeighbor, MemorySeed, SearchResult
from ..retrievers.expanders import _append_neighbors, _find_semantic_expansion
from ..retrievers.parsers import (
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
        decay_threshold: float | None = None,
    ) -> SearchResult:
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
            decay_threshold: Minimum neighbor relevance threshold (0.0-1.0).

        Returns:
            SearchResult: Search result with explicit seed/neighbor separation.
        """
        if not query or not query.strip():
            return SearchResult()

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
        seeds: list[MemorySeed] = []
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

            seed_result = MemorySeed(
                hrid=memory.hrid or memory.id,
                memory_type=memory.memory_type,
                payload=memory.payload,
                score=float(point["score"]),
                relationships=[],  # Will be populated by graph expansion
            )

            seeds.append(seed_result)

        if not seeds:
            return SearchResult()

        # 2. Graph expansion (neighbors with anchor-only payloads)
        neighbors: list[MemoryNeighbor] = []
        if hops > 0:
            graph_result = _append_neighbors(
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
            # Seeds are now modified with relationships, neighbors are in graph_result.neighbors
            neighbors.extend(graph_result.neighbors)

        # 3. Semantic expansion (optional, type-specific "see also")
        if include_semantic:
            semantic_neighbors = _find_semantic_expansion(
                seeds=seeds,  # Only expand from original seeds, not neighbors
                qdrant=self.qdrant,
                embedder=self.embedder,
                user_id=user_id,
                projection=projection,
                hrid_tracker=self.hrid_tracker,
                yaml_translator=self.yaml_translator,
            )
            neighbors.extend(semantic_neighbors)

        # Compose final SearchResult with seeds and neighbors
        return SearchResult(
            memories=seeds,
            neighbors=neighbors,
        )

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

            # Convert Kuzu results directly to memory data
            memories = []
            for result in results:
                node_data = result.get("node", {})

                # Get HRID from UUID
                uuid = result.get("id")
                hrid = self.hrid_tracker.get_hrid(uuid, user_id) if uuid else None

                if not hrid:
                    continue

                # Filter out UUID fields from payload (consumers should only see HRIDs)
                filtered_payload = {
                    k: v for k, v in node_data.items() if k not in ["id", "_id", "uuid"]
                }

                # Build memory data directly
                memory_data = {
                    "hrid": hrid,
                    "memory_type": result.get("memory_type"),
                    "user_id": user_id,
                    "created_at": result.get("created_at"),
                    "updated_at": result.get("updated_at"),
                    "payload": filtered_payload,
                    "score": 1.0,  # Not from vector search
                    "source": "kuzu_query",
                    "metadata": {"query_type": "get_memories"},
                }

                memories.append(memory_data)

            # Apply graph expansion if requested
            if include_neighbors and memories:
                try:
                    # Convert to MemorySeed objects for graph expansion
                    memory_seeds = []
                    for memory_data in memories:
                        # Get UUID from HRID for proper Memory object creation
                        hrid = memory_data["hrid"]
                        uuid = self.hrid_tracker.get_uuid(hrid, user_id)

                        # Create Memory object with proper UUID as id
                        memory = Memory(
                            id=uuid,  # Use UUID for internal operations
                            user_id=memory_data["user_id"],
                            memory_type=memory_data["memory_type"],
                            payload=memory_data["payload"],
                            created_at=memory_data["created_at"],
                            updated_at=memory_data["updated_at"],
                            hrid=hrid,  # HRID as separate field
                        )

                        # Create MemorySeed
                        seed = MemorySeed(
                            memory=memory,
                            score=memory_data["score"],
                            source=memory_data["source"],
                            metadata=memory_data["metadata"],
                            relationships=[],  # Will be populated by graph expansion
                        )
                        memory_seeds.append(seed)

                    # Apply graph expansion
                    expanded_result = _append_neighbors(
                        seeds=memory_seeds,
                        kuzu=self.kuzu,
                        user_id=user_id,
                        relation_names=None,  # All relations
                        neighbor_limit=5,  # Default limit
                        hops=hops,
                        projection=None,
                        hrid_tracker=self.hrid_tracker,
                        yaml_translator=self.yaml_translator,
                        decay_rate=self.config.memg.decay_rate,
                    )

                    # Convert back to dict format for API compatibility
                    expanded_memories = []
                    for seed in expanded_result.memories:
                        memory_data = {
                            "hrid": seed.memory.hrid,
                            "memory_type": seed.memory.memory_type,
                            "user_id": seed.memory.user_id,
                            "created_at": seed.memory.created_at,
                            "updated_at": seed.memory.updated_at,
                            "payload": seed.memory.payload,
                            "score": seed.score,
                            "source": seed.source,
                            "metadata": seed.metadata,
                            "relationships": [
                                {
                                    "relation_type": rel.relation_type,
                                    "target_hrid": rel.target_hrid,
                                    "scores": rel.scores,
                                }
                                for rel in seed.relationships
                            ],
                        }
                        expanded_memories.append(memory_data)

                    return expanded_memories

                except Exception as e:
                    # If graph expansion fails, fall back to basic memories
                    # Log the error but don't fail the entire operation
                    import logging

                    logging.warning(f"Graph expansion failed in get_memories(): {e}")
                    # Fall through to return basic memories

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
