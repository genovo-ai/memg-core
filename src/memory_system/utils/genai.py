import json
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# ⚠️  CRITICAL: Use 'google-genai' package (modern), NOT 'google-generativeai' (deprecated)!
# Pylint may complain about imports - that's configured to be ignored in .pylintrc
# DO NOT "fix" by switching to google-generativeai - it's the old deprecated package!
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()


class GenAI:
    """
    Class for generating outputs using Google's Gemini models
    with support for both structured (JSON) and free-text responses.
    """

    def __init__(
        self,
        system_instruction: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the GenAI client using API key only.

        Args:
            system_instruction: System prompt to guide the model's behavior
            api_key: Google API key for authentication
            model: Gemini model to use (defaults to gemini-2.0-flash, or crashes if not in env)
        """
        # Set parameters with defaults
        model = model or os.getenv("GEMINI_MODEL") or "gemini-2.0-flash"

        # Get API key
        final_api_key = api_key or os.getenv("GOOGLE_API_KEY")

        # Create client with API key only
        self.client = genai.Client(api_key=final_api_key, vertexai=False)
        self.system_instruction = system_instruction
        self.model = model

    def generate_json(self, content: str, json_schema: str | Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate structured content based on the input and schema.

        Args:
            content: The input text content for the model
            json_schema: The JSON schema as string or dict for structured output

        Returns:
            Parsed response as a dictionary
        """
        # Handle both string and dict schema inputs
        if isinstance(json_schema, str):
            schema_dict = json.loads(json_schema)
        else:
            schema_dict = json_schema

        schema = types.Schema(**schema_dict)

        # Create generation config
        generation_config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
        )

        # Generate content
        response = self.client.models.generate_content(
            model=self.model,
            contents=content,
            config=generation_config,
        )

        # Return the parsed response
        return response.parsed

    def generate_text(
        self, content: str, temperature: float = 0.0, max_output_tokens: int = 2000
    ) -> str:
        """
        Generate free-text content based on the input.

        Args:
            content: The input text content for the model
            temperature: Controls randomness (0.0-1.0, default 0.0)
            max_output_tokens: Maximum tokens to generate (default 2000)

        Returns:
            Generated text as a string
        """
        # Create generation config
        generation_config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        # Generate content
        response = self.client.models.generate_content(
            model=self.model,
            contents=content,
            config=generation_config,
        )

        # Return the text response
        return response.text
