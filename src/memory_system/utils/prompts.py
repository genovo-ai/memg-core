"""
Prompt loading utilities for the memory system.
"""

from pathlib import Path
from typing import Dict, Optional


class PromptLoader:
    """Utility class for loading prompts from files."""

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt files. Defaults to module prompts dir.
        """
        if prompts_dir is None:
            # Default to prompts directory in memory_system module
            module_root = Path(__file__).parent.parent
            prompts_dir = module_root / "prompts"

        self.prompts_dir = Path(prompts_dir)
        self._prompt_cache: Dict[str, str] = {}

    def load_prompt(self, prompt_path: str) -> str:
        """
        Load a prompt from a file.

        Args:
            prompt_path: Relative path to prompt file from prompts directory

        Returns:
            The loaded prompt content

        Raises:
            FileNotFoundError: If the prompt file doesn't exist
        """
        if prompt_path in self._prompt_cache:
            return self._prompt_cache[prompt_path]

        full_path = self.prompts_dir / prompt_path

        if not full_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        self._prompt_cache[prompt_path] = content
        return content

    def get_memory_extraction_prompt(self) -> str:
        """Get the memory extraction prompt."""
        return self.load_prompt("memory_extraction/fact_extraction.txt")

    def get_content_analysis_prompt(self) -> str:
        """Get a content analysis prompt (create basic one if not exists)."""
        try:
            return self.load_prompt("conversation_processing/insight_extraction.md")
        except FileNotFoundError:
            # Return a basic content analysis prompt
            return """
Analyze the provided content and extract key information:

1. Determine the content type (technical, personal, professional, etc.)
2. Identify main themes and topics
3. Extract key insights and actionable items
4. Assess complexity and domain

Provide a structured analysis that captures the essence of the content.
"""

    def get_memory_type_classification_prompt(self) -> str:
        """Get the memory type classification prompt."""
        return self.load_prompt("memory_processing/type_classification.md")

    def get_document_summarization_prompt(self) -> str:
        """Get the document summarization prompt."""
        return self.load_prompt("memory_processing/document_summarization.md")

    def get_entity_extraction_prompt(self) -> str:
        """Get the entity extraction prompt."""
        return self.load_prompt("memory_processing/entity_extraction.md")

    def get_conversation_summarization_prompt(self) -> str:
        """Get the conversation summarization prompt."""
        return self.load_prompt("conversation_processing/conversation_summarization.md")


# Global prompt loader instance
prompt_loader = PromptLoader()
