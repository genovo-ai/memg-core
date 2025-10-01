"""Interfaces module - storage adapters."""

from .embedder import Embedder
from .embedder_protocol import EmbedderProtocol
from .kuzu import KuzuInterface
from .qdrant import QdrantInterface

__all__ = ["Embedder", "EmbedderProtocol", "KuzuInterface", "QdrantInterface"]
