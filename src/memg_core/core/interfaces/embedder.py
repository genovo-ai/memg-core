"""Embedding generation interface - pure I/O only"""

import os

from google import genai

from ..exceptions import NetworkError


class GenAIEmbedder:
    """Simple wrapper for Google GenAI embeddings - embedding generation only"""

    def __init__(
        self,
        api_key: str | None = None,
        use_vertex_ai: bool = False,
        project: str | None = None,
        location: str | None = None,
    ):
        """Initialize the GenAI embedder"""
        # Set API key for authentication
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key

        try:
            # For API key usage, we don't need project/location
            if use_vertex_ai and project and location:
                self.client = genai.Client(
                    vertexai=True,
                    location=location,
                    project=project,
                )
            else:
                # Use API key mode (simpler setup)
                self.client = genai.Client(vertexai=False)
        except Exception as e:
            raise NetworkError(
                "Failed to initialize GenAI client",
                operation="init",
                original_error=e,
            )

    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text"""
        try:
            response = self.client.models.embed_content(model="text-embedding-004", contents=text)

            # Return the embedding values from the response
            if response.embeddings and response.embeddings[0]:
                return response.embeddings[0].values

            raise ValueError("Failed to generate embeddings, result was empty.")
        except Exception as e:
            raise NetworkError(
                "Failed to generate embedding",
                operation="get_embedding",
                context={"text_length": len(text)},
                original_error=e,
            )
