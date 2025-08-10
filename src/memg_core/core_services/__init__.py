#!/usr/bin/env python3
"""Core services namespace (embeddings, genai)."""

from .embeddings import GenAIEmbedder

__all__ = [
    "GenAIEmbedder",
]
