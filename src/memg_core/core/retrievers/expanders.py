"""Memory expansion and retrieval utilities for MEMG core system.

This module provides functions for expanding search queries and retrieving
related memories through vector similarity and graph relationships.
"""

from __future__ import annotations

from ..interfaces import Embedder, KuzuInterface, QdrantInterface
from ..models import SearchResult
from ..yaml_translator import YamlTranslator
from . import (
    _project_payload,
    build_memory_from_flat_payload,
    build_memory_from_kuzu_row,
)


def _find_semantic_expansion(
    seeds: list[SearchResult],
    qdrant: QdrantInterface,
    embedder: Embedder,
    user_id: str,
    projection: dict[str, list[str]] | None = None,
    hrid_tracker=None,
    yaml_translator: YamlTranslator | None = None,
) -> list[SearchResult]:
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
        list[SearchResult]: List of semantically related results.
    """
    see_also_results: list[SearchResult] = []

    for seed in seeds:
        memory = seed.memory

        # Get see_also config for this memory type from YAML
        if not yaml_translator:
            yaml_translator = YamlTranslator()
        see_also_config = yaml_translator.get_see_also_config(memory.memory_type)
        if not see_also_config or not see_also_config.get("enabled"):
            continue

        threshold = see_also_config["threshold"]
        limit = see_also_config["limit"]
        target_types = see_also_config["target_types"]

        if not target_types:
            continue

        # Extract anchor text from seed memory - crash if fails
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

            # Add to results with see_also source marking
            search_result = SearchResult(
                memory=similar_memory,
                score=score,
                distance=None,
                source=f"see_also_{point_memory_type}",
                metadata={
                    "see_also_source": memory.memory_type,
                    "see_also_anchor": anchor_text,  # DO NOT TRUNCATE
                },
            )

            see_also_results.append(search_result)
            results_by_type[point_memory_type].append(search_result)

    return see_also_results


def _append_neighbors(
    seeds: list[SearchResult],
    kuzu: KuzuInterface,
    user_id: str,
    relation_names: list[str] | None,
    neighbor_limit: int,
    hops: int = 1,
    projection: dict[str, list[str]] | None = None,
    hrid_tracker=None,
    yaml_translator: YamlTranslator | None = None,
    decay_rate: float = 0.9,
) -> list[SearchResult]:
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
        list[SearchResult]: Combined list of seeds + neighbors with
        anchor-only payloads for neighbors.
    """
    all_results: list[SearchResult] = list(seeds)  # Start with seeds

    current_hop_seeds = seeds

    for hop in range(hops):
        next_hop_results: list[SearchResult] = []
        # Track processed nodes per hop to avoid cycles within the same hop
        hop_processed_ids: set[str] = set()

        for seed in current_hop_seeds:
            memory = seed.memory
            if not memory.id or memory.id in hop_processed_ids:
                continue

            hop_processed_ids.add(memory.id)

            # Get neighbors from Kuzu - using entity-specific tables
            # memory.id should always be UUID - no guessing needed
            memory_uuid = memory.id

            neighbor_rows = kuzu.neighbors(
                node_label=memory.memory_type,  # Use entity-specific table (bug, task, etc.)
                node_uuid=memory_uuid,  # Use UUID, not HRID
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

                neighbor_result = SearchResult(
                    memory=neighbor_memory,
                    score=neighbor_score,
                    distance=None,
                    source="graph_neighbor",
                    metadata={
                        "from_seed": memory.id,
                        "hop": hop + 1,
                        "relation_type": row["rel_type"],
                    },
                )

                next_hop_results.append(neighbor_result)

        # Add this hop's results to all results
        all_results.extend(next_hop_results)

        # Prepare for next hop (if any)
        current_hop_seeds = next_hop_results

        # Stop if no more neighbors found
        if not next_hop_results:
            break

    return all_results
