"""FastEmbed-based embedder - local, no API keys required."""

from __future__ import annotations

from fastembed import TextEmbedding

from ..config import get_config


class Embedder:
    """Local embedder using FastEmbed - no API keys required.

    Attributes:
        model_name: Name of the embedding model being used.
        model: FastEmbed TextEmbedding instance.
    """

    def __init__(self, model_name: str | None = None):
        """Initialize the FastEmbed embedder.

        Args:
            model_name: Model to use. Defaults to config or snowflake-arctic-embed-xs.
        """

        # Get model name from config system (which reads env) or use provided override
        if model_name:
            self.model_name = model_name
        else:
            # Use config system which handles env variable EMBEDDER_MODEL
            config = get_config()
            self.model_name = config.memg.embedder_model

        self.model = TextEmbedding(model_name=self.model_name)

    def get_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            list[float]: Embedding vector.

        Raises:
            RuntimeError: If FastEmbed returns empty embedding.
        """
        # FastEmbed returns a generator, so we need to extract the first result
        embeddings = list(self.model.embed([text]))
        if embeddings:
            return embeddings[0].tolist()
        raise RuntimeError("FastEmbed returned empty embedding")

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            list[list[float]]: List of embedding vectors.
        """
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() for emb in embeddings]
