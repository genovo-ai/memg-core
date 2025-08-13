"""FastEmbed-based embedder - local, no API keys required"""

from __future__ import annotations

import os

from fastembed import TextEmbedding


class Embedder:
    """Local embedder using FastEmbed - no API keys required"""

    def __init__(self, model_name: str | None = None):
        """Initialize the FastEmbed embedder

        Args:
            model_name: Model to use. Defaults to env EMBEDDER_MODEL or snowflake-arctic-embed-xs
        """

        # Use env variable or default to the winner model
        self.model_name = (
            model_name or os.getenv("EMBEDDER_MODEL") or "Snowflake/snowflake-arctic-embed-xs"
        )

        self.model = TextEmbedding(model_name=self.model_name)

    def get_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text"""
        # FastEmbed returns a generator, so we need to extract the first result
        embeddings = list(self.model.embed([text]))
        if embeddings:
            return embeddings[0].tolist()
        raise RuntimeError("FastEmbed returned empty embedding")

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts"""
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() for emb in embeddings]
