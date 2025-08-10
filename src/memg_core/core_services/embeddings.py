#!/usr/bin/env python3
"""Embedding service wrapper to keep stable import path.

Re-exports GenAIEmbedder from utils.
"""

from memg_core.utils.embeddings import GenAIEmbedder  # noqa: F401

__all__ = ["GenAIEmbedder"]
