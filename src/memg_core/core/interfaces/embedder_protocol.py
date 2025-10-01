"""Embedder protocol for flexible embedding implementations.

This protocol defines the interface that any embedder must implement.
Consumers can provide their own implementations as long as they satisfy this protocol.
"""

from __future__ import annotations

from typing import Protocol


class EmbedderProtocol(Protocol):
    """Protocol defining the embedder interface (structural typing - duck typing with type hints).

    This is NOT an abstract base class - you don't need to inherit from it.
    Any object with get_embedding() and get_embeddings() methods will work.
    The Protocol is purely for type checkers (mypy, pyright) and IDE support.

    This allows consumers to provide their own embedding implementations
    (OpenAI, Cohere, custom models, etc.) without modifying memg-core code.

    Example:
        >>> class MyEmbedder:  # No inheritance needed!
        ...     def get_embedding(self, text: str) -> list[float]:
        ...         return [0.1, 0.2, 0.3]  # Your implementation
        ...     def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        ...         return [[0.1, 0.2, 0.3] for _ in texts]
        >>>
        >>> from memg_core.api import MemgClient
        >>> client = MemgClient(yaml_path="...", db_path="...", embedder=MyEmbedder())
    """

    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        ...

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors.
        """
        ...
