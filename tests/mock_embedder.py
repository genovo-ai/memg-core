"""Deterministic mock embedder for testing"""

from __future__ import annotations

import hashlib
from typing import Any

from typing import Protocol


class EmbeddingInterface(Protocol):
    """Interface for embedding providers"""

    def get_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text"""
        ...

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts"""
        ...


class MockEmbedder(EmbeddingInterface):
    """Deterministic mock embedder that generates consistent vectors based on text hash"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def get_embedding(self, text: str) -> list[float]:
        """Generate deterministic embedding based on text hash"""
        # Use MD5 hash for deterministic but varied embeddings
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()

        # Convert hash bytes to normalized floats
        embedding = []
        for i in range(self.dimension):
            # Use hash bytes cyclically and normalize to [-1, 1]
            byte_val = hash_bytes[i % len(hash_bytes)]
            normalized = (byte_val / 255.0) * 2.0 - 1.0  # Scale to [-1, 1]
            embedding.append(normalized)

        return embedding

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        return [self.get_embedding(text) for text in texts]


class SimilarityMockEmbedder(EmbeddingInterface):
    """Mock embedder that creates predictable similarity patterns"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._word_vectors = {}

    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding with predictable similarity patterns"""
        words = text.lower().split()

        # Create base vector for each unique word
        if not hasattr(self, '_base_seed'):
            self._base_seed = 0

        # Generate embedding based on key words
        vector = [0.0] * self.dimension

        for word in words:
            if word not in self._word_vectors:
                # Create consistent vector for each word
                word_hash = hash(word) % (2**31)  # Ensure positive
                self._word_vectors[word] = [
                    ((word_hash >> i) % 256 / 255.0) * 2.0 - 1.0
                    for i in range(self.dimension)
                ]

            # Add word vector to text vector
            word_vec = self._word_vectors[word]
            for i in range(self.dimension):
                vector[i] += word_vec[i]

        # Normalize vector
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        return [self.get_embedding(text) for text in texts]
