"""Memory expansion and retrieval utilities for MEMG core system.

This module provides functions for expanding search queries and retrieving
related memories through vector similarity and graph relationships.
"""

from __future__ import annotations

from ..interfaces import Embedder, KuzuInterface, QdrantInterface
from ..models import MemoryNeighbor, MemorySeed, RelationshipInfo, SearchResult
from ..yaml_translator import YamlTranslator
from . import (
    _project_payload,
    build_memory_from_flat_payload,
    build_memory_from_kuzu_row,
)


def _find_semantic_expansion(
    seeds: list[MemorySeed],
    qdrant: QdrantInterface,
    embedder: Embedder,
    user_id: str,
    projection: dict[str, list[str]] | None = None,
    hrid_tracker=None,
    yaml_translator: YamlTranslator | None = None,
) -> list[MemoryNeighbor]:
    """Type-specific semantic expansion using seed anchor text.

    For seeds with see_also configuration in YAML:
    1. Extract anchor text from seed
    2. Create embedding from anchor text
    3. Search Qdrant for similar memories in target_types
    4. Apply threshold and limit filters
    5. Return as see_also_<type> results

    Args:
        seeds: Initial seed results from vector search.
        qdrant: Qdrant interface instance.
        embedder: Embedder instance.
        user_id: User ID for filtering.
        projection: Optional field projection.
        hrid_tracker: Optional HRID tracker.
        yaml_translator: Optional YAML translator.

    Returns:
        list[MemoryNeighbor]: List of semantically related neighbors.
    """
    see_also_results: list[MemoryNeighbor] = []

    for seed in seeds:
        # Get see_also config for this memory type from YAML
        if not yaml_translator:
            yaml_translator = YamlTranslator()
        see_also_config = yaml_translator.get_see_also_config(seed.memory_type)
        if not see_also_config or not see_also_config.get("enabled"):
            continue

        threshold = see_also_config["threshold"]
        limit = see_also_config["limit"]
        target_types = see_also_config["target_types"]

        if not target_types:
            continue

        # Extract anchor text from seed memory - crash if fails
        # Create a Memory object from the MemorySeed for anchor text extraction
        from ..models import Memory

        memory = Memory(
            id=seed.hrid,  # Use HRID as ID for anchor text
            user_id=user_id,
            memory_type=seed.memory_type,
            payload=seed.payload,
            hrid=seed.hrid,
        )
        anchor_text = yaml_translator.build_anchor_text(memory)

        # Create embedding from anchor text
        anchor_embedding = embedder.get_embedding(anchor_text)

        # Search for similar memories in target types - use flat structure
        filters = {
            "user_id": user_id,  # CRITICAL: Always include user_id for isolation
            "memory_type": target_types,
        }

        similar_points = qdrant.search_points(
            vector=anchor_embedding,
            limit=limit * len(target_types) * 2,  # Get enough candidates
            filters=filters,
        )

        # Group by type to respect per-type limits
        results_by_type: dict[str, list] = {target_type: [] for target_type in target_types}

        for point in similar_points:
            score = float(point["score"])

            # Apply threshold filter
            if score < threshold:
                continue

            # Skip if it's the same memory as the seed
            if point["id"] == memory.id:
                continue

            # Use centralized utility for Memory construction
            payload = point["payload"]
            point_id = point["id"]
            point_memory_type = payload.get("memory_type")

            # Check per-type limit
            if len(results_by_type[point_memory_type]) >= limit:
                continue

            # Build Memory object using centralized utility
            similar_memory = build_memory_from_flat_payload(point_id, payload, hrid_tracker)

            # Project to anchor-only payload
            similar_memory.payload = _project_payload(
                similar_memory.memory_type,
                similar_memory.payload,
                include_details="none",
                projection=projection,
                yaml_translator=yaml_translator,
            )

            # Add to results as MemoryNeighbor
            neighbor = MemoryNeighbor(
                hrid=similar_memory.hrid or similar_memory.id,
                memory_type=similar_memory.memory_type,
                payload=similar_memory.payload,  # Already projected to anchor-only
            )

            see_also_results.append(neighbor)
            results_by_type[point_memory_type].append(neighbor)

    return see_also_results


def _append_neighbors(
    seeds: list[MemorySeed],
    kuzu: KuzuInterface,
    user_id: str,
    relation_names: list[str] | None,
    neighbor_limit: int,
    hops: int = 1,
    projection: dict[str, list[str]] | None = None,
    hrid_tracker=None,
    yaml_translator: YamlTranslator | None = None,
    decay_rate: float = 0.9,
) -> SearchResult:
    """Expand neighbors from Kuzu graph with progressive score decay.

    Args:
        seeds: Initial seed results from vector search.
        kuzu: Kuzu graph interface.
        user_id: User ID for isolation.
        relation_names: Specific relation types to expand (None = all relations).
        neighbor_limit: Max neighbors per seed.
        hops: Number of hops to expand (progressive score decay).
        projection: Optional field projection.
        hrid_tracker: Optional HRID tracker.
        yaml_translator: Optional YAML translator.
        decay_rate: Score decay rate per hop.

    Returns:
        SearchResult: Seeds with populated relationships and neighbors with anchor-only payloads.
    """
    all_neighbors: list[MemoryNeighbor] = []  # Collect all neighbors

    current_hop_seeds = seeds

    for hop in range(hops):
        next_hop_results: list[MemoryNeighbor] = []
        # Track processed nodes per hop to avoid cycles within the same hop
        hop_processed_ids: set[str] = set()

        for seed in current_hop_seeds:
            # Get UUID from HRID for Kuzu queries
            seed_uuid = hrid_tracker.get_uuid(seed.hrid, user_id) if hrid_tracker else None
            if not seed_uuid or seed_uuid in hop_processed_ids:
                continue

            hop_processed_ids.add(seed_uuid)

            # Get neighbors from Kuzu - using entity-specific tables
            neighbor_rows = kuzu.neighbors(
                node_label=seed.memory_type,  # Use entity-specific table (bug, task, etc.)
                node_uuid=seed_uuid,  # Use UUID for Kuzu queries
                user_id=user_id,  # CRITICAL: User isolation
                rel_types=relation_names,  # None means all relations
                direction="any",
                limit=neighbor_limit,
                neighbor_label=None,  # Accept neighbors from any entity table
            )

            for row in neighbor_rows:
                # Extract neighbor memory from row
                neighbor_id = row["id"]
                if not neighbor_id or neighbor_id in hop_processed_ids:
                    continue

                # Build neighbor Memory object using centralized utility
                neighbor_memory = build_memory_from_kuzu_row(row, hrid_tracker)

                # Project to anchor-only payload for neighbors
                if not yaml_translator:
                    yaml_translator = YamlTranslator()
                neighbor_memory.payload = _project_payload(
                    neighbor_memory.memory_type,
                    neighbor_memory.payload,
                    include_details="none",
                    projection=projection,
                    yaml_translator=yaml_translator,
                )

                # Calculate score with progressive decay: seed_score * decay_rate^hop
                neighbor_score = seed.score * (decay_rate ** (hop + 1))

                # Extract relationship info and add to seed's relationships
                rel_type = row.get("rel_type")
                target_hrid = neighbor_memory.hrid or neighbor_memory.id

                if rel_type and target_hrid:
                    # Create RelationshipInfo and add to seed
                    relationship_info = RelationshipInfo(
                        relation_type=rel_type,
                        target_hrid=target_hrid,
                        scores={},  # Empty scores dict - not about scores!
                    )
                    seed.relationships.append(relationship_info)

                # Create MemoryNeighbor object
                neighbor_result = MemoryNeighbor(
                    hrid=neighbor_memory.hrid or neighbor_memory.id,
                    memory_type=neighbor_memory.memory_type,
                    payload=neighbor_memory.payload,  # Already projected to anchor-only
                )

                next_hop_results.append(neighbor_result)

        # Add this hop's results to all neighbors
        all_neighbors.extend(next_hop_results)

        # Prepare for next hop (if any) - convert neighbors back to seeds for next iteration
        # For multi-hop, we need to treat current neighbors as seeds for the next hop
        next_hop_seeds = []
        for neighbor in next_hop_results:
            # Convert MemoryNeighbor back to MemorySeed for next hop expansion
            seed_for_next_hop = MemorySeed(
                hrid=neighbor.hrid,
                memory_type=neighbor.memory_type,
                payload=neighbor.payload,
                score=neighbor_score,  # Use the decayed score
                relationships=[],  # No relationships needed for expansion
            )
            next_hop_seeds.append(seed_for_next_hop)

        current_hop_seeds = next_hop_seeds

        # Stop if no more neighbors found
        if not next_hop_results:
            break

    # Return SearchResult with seeds (with relationships) and unique neighbors
    return SearchResult(
        memories=seeds,  # Seeds now have populated relationships
        neighbors=all_neighbors,  # Neighbors with anchor-only payloads
    )
