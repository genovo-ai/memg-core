"""FastEmbed-based embedder - local, no API keys required"""

from __future__ import annotations

import os

try:
    from fastembed import TextEmbedding

    _FASTEMBED_AVAILABLE = True
except ImportError as e:
    TextEmbedding = None
    _FASTEMBED_AVAILABLE = False
    _IMPORT_ERROR = str(e)

from ..exceptions import NetworkError


class Embedder:
    """Local embedder using FastEmbed - no API keys required"""

    def __init__(self, model_name: str | None = None):
        """Initialize the FastEmbed embedder

        Args:
            model_name: Model to use. Defaults to env EMBEDDER_MODEL or snowflake-arctic-embed-xs
        """
        if TextEmbedding is None:
            error_msg = "FastEmbed is required for Embedder. Install with: pip install fastembed"
            if not _FASTEMBED_AVAILABLE:
                error_msg += f" (Import error: {_IMPORT_ERROR})"
            raise ImportError(error_msg)

        # Use env variable or default to the winner model
        self.model_name = model_name or os.getenv(
            "EMBEDDER_MODEL", "Snowflake/snowflake-arctic-embed-xs"
        )

        try:
            self.model = TextEmbedding(model_name=self.model_name)
        except Exception as e:
            raise NetworkError(
                f"Failed to initialize FastEmbed model '{self.model_name}'",
                original_error=e,
            )

    def get_embedding(self, text: str) -> list[float]:
        """Get embedding for a single text"""
        try:
            # FastEmbed returns a generator, so we need to extract the first result
            embeddings = list(self.model.embed([text]))
            if embeddings:
                return embeddings[0].tolist()
            raise NetworkError("FastEmbed returned empty embedding")
        except Exception as e:
            raise NetworkError(
                "Failed to generate embedding for text",
                context={"model": self.model_name, "text_length": len(text)},
                original_error=e,
            )

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts"""
        try:
            embeddings = list(self.model.embed(texts))
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            raise NetworkError(
                f"Failed to generate embeddings for {len(texts)} texts",
                context={"model": self.model_name, "text_count": len(texts)},
                original_error=e,
            )
