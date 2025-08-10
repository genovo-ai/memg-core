#!/usr/bin/env python3
"""Policy module namespace for memg-core.

Includes deterministic policies for indexing and retrieval configuration.
"""

from .indexing import build_index_text  # re-export

__all__ = [
    "build_index_text",
]
