"""Scoring utilities for neighbor relevance calculation."""

from __future__ import annotations

import math

from ..core.interfaces import Embedder


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        float: Cosine similarity score (0.0-1.0).

    Raises:
        ValueError: If vectors have different lengths or are empty.
    """
    if not vec1 or not vec2:
        raise ValueError("Vectors cannot be empty")

    if len(vec1) != len(vec2):
        raise ValueError(f"Vector dimensions must match: {len(vec1)} != {len(vec2)}")

    # Calculate dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))

    # Calculate magnitudes
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    # Calculate cosine similarity
    similarity = dot_product / (magnitude1 * magnitude2)

    # Clamp to [0, 1] range (cosine similarity can be [-1, 1])
    return max(0.0, min(1.0, similarity))


def calculate_neighbor_relevance(
    neighbor_anchor: str,
    seed_anchor: str,
    seed_score: float,
    embedder: Embedder,
) -> float:
    """Calculate recursive neighbor relevance: seed_score × neighbor_to_seed_similarity.

    Args:
        neighbor_anchor: Anchor text of the neighbor memory.
        seed_anchor: Anchor text of the seed memory.
        seed_score: Score of the seed that led to this neighbor.
        embedder: Embedder instance for generating embeddings.

    Returns:
        float: Recursive relevance score (always ≤ seed_score).
    """
    try:
        # Calculate similarity between neighbor and seed
        neighbor_embedding = embedder.get_embedding(neighbor_anchor)
        seed_embedding = embedder.get_embedding(seed_anchor)
        neighbor_to_seed_similarity = cosine_similarity(neighbor_embedding, seed_embedding)

        # Recursive multiplication: seed_score × neighbor_to_seed_similarity
        # This naturally decays through the relationship chain
        return seed_score * neighbor_to_seed_similarity
    except Exception:
        # Fallback: use 50% of seed score if embedding fails
        return seed_score * 0.5


def filter_by_decay_threshold(
    scores: dict[str, float],
    decay_threshold: float | None = None,
) -> bool:
    """Check if neighbor scores meet the decay threshold.

    Args:
        scores: Dictionary with 'to_query' and 'to_neighbor' scores.
        decay_threshold: Minimum threshold for neighbor relevance.

    Returns:
        bool: True if neighbor meets threshold, False otherwise.
    """
    if decay_threshold is None:
        return True

    # Use the higher of the two scores for threshold comparison
    max_score = max(scores.get("to_query", 0.0), scores.get("to_neighbor", 0.0))
    return max_score >= decay_threshold
