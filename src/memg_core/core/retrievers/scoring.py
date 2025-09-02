"""Scoring utilities for neighbor relevance calculation."""

from __future__ import annotations

import math

from ..interfaces import Embedder


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


def calculate_neighbor_scores(
    neighbor_anchor: str,
    query: str,
    seed_score: float,
    hop: int,
    embedder: Embedder,
    decay_rate: float = 0.9,
) -> dict[str, float]:
    """Calculate dual scores for a neighbor memory.

    Args:
        neighbor_anchor: Anchor text of the neighbor memory.
        query: Original search query.
        seed_score: Score of the seed that led to this neighbor.
        hop: Number of hops from original seed (1-based).
        embedder: Embedder instance for generating embeddings.
        decay_rate: Decay rate for hop-based scoring (default: 0.9).

    Returns:
        dict[str, float]: Dictionary with 'to_query' and 'to_neighbor' scores.
    """
    # Calculate to_query score (neighbor relevance to original query)
    try:
        neighbor_embedding = embedder.get_embedding(neighbor_anchor)
        query_embedding = embedder.get_embedding(query)
        to_query_score = cosine_similarity(neighbor_embedding, query_embedding)
    except Exception:
        # Fallback to decay-based score if embedding fails
        to_query_score = seed_score * (decay_rate**hop)

    # Calculate to_neighbor score (relationship strength with decay)
    to_neighbor_score = seed_score * (decay_rate**hop)

    return {
        "to_query": to_query_score,
        "to_neighbor": to_neighbor_score,
    }


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
