"""Result composition utilities for search results."""

from __future__ import annotations

from ..interfaces import Embedder
from ..models import (
    Memory,
    MemoryNeighbor,
    MemorySeed,
    RelationshipInfo,
    SearchResult,
)
from ..yaml_translator import YamlTranslator
from .scoring import calculate_neighbor_scores, filter_by_decay_threshold


def compose_search_result(
    seed_memories: list[tuple[Memory, float, dict]],  # (memory, score, metadata)
    neighbor_memories: list[tuple[Memory, float, dict]],  # (memory, score, metadata)
    yaml_translator: YamlTranslator | None = None,
    query: str | None = None,
    embedder: Embedder | None = None,
    decay_threshold: float | None = None,
    decay_rate: float = 0.9,
) -> SearchResult:
    """Compose search result with explicit seed/neighbor separation.

    Args:
        seed_memories: List of (memory, score, metadata) tuples for seeds.
        neighbor_memories: List of (memory, score, metadata) tuples for neighbors.
        yaml_translator: YAML translator for relationship info.
        query: Original search query for neighbor scoring.
        embedder: Embedder for calculating neighbor-to-query relevance.
        decay_threshold: Minimum threshold for neighbor relevance.
        decay_rate: Graph traversal decay rate per hop.

    Returns:
        SearchResult: Composed result with explicit structure.
    """
    if not yaml_translator:
        yaml_translator = YamlTranslator()

    # Build seed-to-neighbors mapping for relationships
    seed_neighbors_map = _build_seed_neighbors_map(neighbor_memories)

    # Convert seeds to MemorySeed with relationships
    memory_seeds = []
    for memory, score, _ in seed_memories:
        # Get neighbors for this seed
        seed_neighbors = seed_neighbors_map.get(memory.id, [])
        # Extract relationships with scoring
        relationships = _extract_relationships(
            seed_score=score,
            neighbors=seed_neighbors,
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
            score=score,
            relationships=relationships,
        )
        memory_seeds.append(memory_seed)

    # Convert neighbors to MemoryNeighbor (anchor-only payload)
    memory_neighbors = []
    for memory, _, _ in neighbor_memories:
        # Get anchor field for this memory type
        anchor_field = yaml_translator.get_anchor_field(memory.memory_type)
        anchor_payload = {anchor_field: memory.payload.get(anchor_field, "")}
        memory_neighbor = MemoryNeighbor(
            hrid=memory.hrid or memory.id,
            memory_type=memory.memory_type,
            payload=anchor_payload,
        )
        memory_neighbors.append(memory_neighbor)

    return SearchResult(
        memories=memory_seeds,
        neighbors=memory_neighbors,
    )


def _build_seed_neighbors_map(
    neighbor_memories: list[tuple[Memory, float, dict]],
) -> dict[str, list[tuple[Memory, float, dict]]]:
    """Build mapping from seed ID to its neighbors.

    Args:
        neighbor_memories: List of neighbor memory tuples.

    Returns:
        dict: Mapping from seed ID to list of neighbor tuples.
    """
    seed_neighbors_map: dict[str, list[tuple[Memory, float, dict]]] = {}
    for memory, score, metadata in neighbor_memories:
        seed_id = metadata.get("seed_id")
        if seed_id:
            if seed_id not in seed_neighbors_map:
                seed_neighbors_map[seed_id] = []
            seed_neighbors_map[seed_id].append((memory, score, metadata))
    return seed_neighbors_map


def _extract_relationships(
    seed_score: float,
    neighbors: list[tuple[Memory, float, dict]],
    yaml_translator: YamlTranslator,
    query: str | None = None,
    embedder: Embedder | None = None,
    decay_threshold: float | None = None,
    decay_rate: float = 0.9,
) -> list[RelationshipInfo]:
    """Extract relationship information from neighbors.

    Args:
        seed_score: Score of the seed memory.
        neighbors: List of neighbor memory tuples.
        yaml_translator: YAML translator for anchor fields.
        query: Original query for scoring.
        embedder: Embedder for neighbor-to-query scoring.
        decay_threshold: Minimum relevance threshold.
        decay_rate: Decay rate for fallback scoring.

    Returns:
        list[RelationshipInfo]: List of relationship information.
    """
    relationships = []
    for memory, _, metadata in neighbors:
        relation_type = metadata.get("relation_type", "RELATED_TO")
        hop = metadata.get("hop", 1)

        if query and embedder and memory.payload:
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
                if not filter_by_decay_threshold(scores, decay_threshold):
                    continue
            else:
                # Fallback to decay-based scoring if no anchor text
                scores = {
                    "to_query": seed_score * (decay_rate**hop),
                    "to_neighbor": seed_score * (decay_rate**hop),
                }
        else:
            # Fallback for missing components
            scores = {}

        relationship = RelationshipInfo(
            relation_type=relation_type,
            target_hrid=memory.hrid or memory.id,
            scores=scores,
        )
        relationships.append(relationship)
    return relationships


def separate_seeds_and_neighbors(
    all_memories: list[tuple[Memory, float, dict]],
    limit: int,
) -> tuple[list[tuple[Memory, float, dict]], list[tuple[Memory, float, dict]]]:
    """Separate memory tuples into seeds and neighbors based on limit.

    Args:
        all_memories: All memory tuples from search.
        limit: Maximum number of seeds.

    Returns:
        tuple: (seeds, neighbors) as memory tuple lists.
    """
    seeds: list[tuple[Memory, float, dict]] = []
    neighbors: list[tuple[Memory, float, dict]] = []
    for memory_tuple in all_memories:
        if len(seeds) < limit:
            seeds.append(memory_tuple)
        else:
            neighbors.append(memory_tuple)

    return seeds, neighbors
