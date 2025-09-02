"""Result composition utilities for enhanced search results."""

from __future__ import annotations

from ..interfaces import Embedder
from ..models import (
    EnhancedSearchResult,
    MemoryNeighbor,
    MemorySeed,
    RelationshipInfo,
    SearchResult,
)
from ..yaml_translator import YamlTranslator
from .scoring import calculate_neighbor_scores, filter_by_decay_threshold


def compose_enhanced_result(
    seeds: list[SearchResult],
    neighbors: list[SearchResult],
    yaml_translator: YamlTranslator | None = None,
    query: str | None = None,
    embedder: Embedder | None = None,
    decay_threshold: float | None = None,
    decay_rate: float = 0.9,
) -> EnhancedSearchResult:
    """Compose enhanced search result with explicit seed/neighbor separation.

    Args:
        seeds: List of seed search results with full payloads.
        neighbors: List of neighbor search results with anchor payloads.
        yaml_translator: YAML translator for relationship info.
        query: Original search query for neighbor scoring.
        embedder: Embedder for calculating neighbor-to-query relevance.
        decay_threshold: Minimum threshold for neighbor relevance.
        decay_rate: Graph traversal decay rate per hop.

    Returns:
        EnhancedSearchResult: Composed result with explicit structure.
    """
    if not yaml_translator:
        yaml_translator = YamlTranslator()

    # Build seed-to-neighbors mapping for relationships
    seed_neighbors_map = _build_seed_neighbors_map(neighbors)

    # Convert seeds to MemorySeed objects with relationships
    memory_seeds = []
    for seed in seeds:
        memory = seed.memory
        relationships = _extract_relationships(
            seed_score=seed.score,
            neighbors=seed_neighbors_map.get(memory.id, []),
            yaml_translator=yaml_translator,
            query=query,
            embedder=embedder,
            decay_threshold=decay_threshold,
            decay_rate=decay_rate,
        )

        memory_seed = MemorySeed(
            hrid=memory.hrid or memory.id,
            memory_type=memory.memory_type,
            payload=memory.payload,
            score=seed.score,
            relationships=relationships,
        )
        memory_seeds.append(memory_seed)

    # Convert neighbors to MemoryNeighbor objects (deduplicated)
    memory_neighbors = []
    seen_neighbor_ids = set()

    for neighbor in neighbors:
        memory = neighbor.memory
        if memory.id not in seen_neighbor_ids:
            memory_neighbor = MemoryNeighbor(
                hrid=memory.hrid or memory.id,
                memory_type=memory.memory_type,
                payload=memory.payload,  # Already projected to anchor-only
            )
            memory_neighbors.append(memory_neighbor)
            seen_neighbor_ids.add(memory.id)

    return EnhancedSearchResult(
        memories=memory_seeds,
        neighbors=memory_neighbors,
    )


def _build_seed_neighbors_map(neighbors: list[SearchResult]) -> dict[str, list[SearchResult]]:
    """Build mapping from seed IDs to their neighbors.

    Args:
        neighbors: List of neighbor search results.

    Returns:
        dict: Mapping from seed ID to list of neighbor results.
    """
    seed_neighbors_map: dict[str, list[SearchResult]] = {}

    for neighbor in neighbors:
        # Extract seed ID from metadata
        from_seed = neighbor.metadata.get("from_seed")
        if from_seed:
            if from_seed not in seed_neighbors_map:
                seed_neighbors_map[from_seed] = []
            seed_neighbors_map[from_seed].append(neighbor)

    return seed_neighbors_map


def _extract_relationships(
    seed_score: float,
    neighbors: list[SearchResult],
    yaml_translator: YamlTranslator,
    query: str | None = None,
    embedder: Embedder | None = None,
    decay_threshold: float | None = None,
    decay_rate: float = 0.9,
) -> list[RelationshipInfo]:
    """Extract relationship information from neighbors.

    Args:
        seed_score: Score of the seed memory.
        neighbors: List of neighbor results for this seed.
        yaml_translator: YAML translator for relationship info.
        query: Original search query for neighbor scoring.
        embedder: Embedder for calculating neighbor-to-query relevance.
        decay_threshold: Minimum threshold for neighbor relevance.
        decay_rate: Graph traversal decay rate per hop.

    Returns:
        list[RelationshipInfo]: List of relationship information.
    """
    relationships = []

    for neighbor in neighbors:
        memory = neighbor.memory
        relation_type = neighbor.metadata.get("relation_type", "RELATED_TO")
        hop = neighbor.metadata.get("hop", 1)

        # Calculate dual scores if we have the necessary components
        if query and embedder and memory.payload:
            # Get anchor text from neighbor payload
            anchor_field = yaml_translator.get_anchor_field(memory.memory_type)
            neighbor_anchor = memory.payload.get(anchor_field, "")

            if neighbor_anchor:
                scores = calculate_neighbor_scores(
                    neighbor_anchor=neighbor_anchor,
                    query=query,
                    seed_score=seed_score,
                    hop=hop,
                    embedder=embedder,
                    decay_rate=decay_rate,
                )

                # Apply decay threshold filtering
                if not filter_by_decay_threshold(scores, decay_threshold):
                    continue  # Skip this neighbor if it doesn't meet threshold
            else:
                # Fallback to decay-based scoring if no anchor text
                scores = {
                    "to_query": seed_score * (decay_rate**hop),
                    "to_neighbor": seed_score * (decay_rate**hop),
                }
        else:
            # Fallback for Phase 1 compatibility or missing components
            scores = {}

        relationship = RelationshipInfo(
            relation_type=relation_type,
            target_hrid=memory.hrid or memory.id,
            scores=scores,
        )
        relationships.append(relationship)

    return relationships


def separate_seeds_and_neighbors(
    results: list[SearchResult],
    limit: int,
) -> tuple[list[SearchResult], list[SearchResult]]:
    """Separate search results into seeds and neighbors based on limit.

    This implements the new semantics where limit=N means N seeds.

    Args:
        results: Combined list of search results.
        limit: Number of seeds to return.

    Returns:
        tuple: (seeds, neighbors) where seeds are limited and neighbors are the rest.
    """
    seeds: list[SearchResult] = []
    neighbors: list[SearchResult] = []

    for result in results:
        if result.source == "qdrant" and len(seeds) < limit:
            # This is a vector seed and we haven't reached the limit
            seeds.append(result)
        elif result.source in ("graph_neighbor", "see_also") or result.source.startswith(
            "see_also_"
        ):
            # This is a neighbor or semantic expansion
            neighbors.append(result)
        # Skip additional seeds beyond the limit

    return seeds, neighbors
