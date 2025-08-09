import os
from typing import List, Optional

from dotenv import load_dotenv

# ⚠️  CRITICAL: Use 'google-genai' package (modern), NOT 'google-generativeai' (deprecated)!
# If pylint complains about this import, do NOT switch packages - check .pylintrc config instead!
from google import genai

# Load environment variables
load_dotenv()


class GenAIEmbedder:
    """
    Class for generating embeddings using Google's GenAI embedding models.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
        use_vertex_ai: Optional[bool] = None,
    ):
        """
        Initialize the GenAIEmbedder client using provided API key.

        Args:
            api_key: Google API key for authentication
            project: GCP project ID (for Vertex AI)
            location: GCP region (for Vertex AI)
            use_vertex_ai: Whether to use Vertex AI (defaults to False)
        """
        # Set parameters with defaults
        use_vertex_ai = use_vertex_ai or False

        # Set API key for authentication
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key

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

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using Google GenAI.

        Args:
            text: The input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        # Use the embedding model to generate embeddings
        response = self.client.models.embed_content(
            model="text-embedding-004", contents=text
        )

        # Return the embedding values from the response
        if response.embeddings and response.embeddings[0]:
            return response.embeddings[0].values
        raise ValueError("Failed to generate embeddings, result was empty.")
