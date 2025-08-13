"""Test fixtures and test doubles for memg_core tests."""

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import pytest
from pydantic import BaseModel

from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory, MemoryType


class DummyEmbedder:
    """Test double for Embedder that returns deterministic vectors."""

    def __init__(self, vector_size: int = 384):
        """Initialize with configurable vector size."""
        self.vector_size = vector_size
        # Skip parent initialization to avoid API key requirements

    def get_embedding(self, text: str) -> List[float]:
        """Generate a deterministic vector based on text hash."""
        # Create a hash of the input text
        text_hash = hashlib.md5(text.encode()).hexdigest()

        # Convert hash to a list of floats between -1 and 1
        hash_bytes = bytes.fromhex(text_hash)
        vector = []
        for i in range(self.vector_size):
            # Use modulo to cycle through the hash bytes
            byte_val = hash_bytes[i % len(hash_bytes)]
            # Convert to float between -1 and 1
            vector.append((byte_val / 128.0) - 1.0)

        return vector


class FakeQdrant(QdrantInterface):
    """Test double for QdrantInterface with in-memory storage."""

    def __init__(self, collection_name: str = "memories"):
        """Initialize with in-memory storage."""
        self.collection_name = collection_name
        self.collections: Dict[str, Dict[str, Dict]] = {}
        self.points: Dict[str, Dict[str, Any]] = {}  # collection_name -> {id: {vector, payload}}

    def collection_exists(self, collection: Optional[str] = None) -> bool:
        """Check if collection exists."""
        collection = collection or self.collection_name
        return collection in self.collections

    def create_collection(self, collection: Optional[str] = None, vector_size: int = 384) -> bool:
        """Create a new collection."""
        collection = collection or self.collection_name
        if collection not in self.collections:
            self.collections[collection] = {}
            self.points[collection] = {}
        return True

    def ensure_collection(self, collection: Optional[str] = None, vector_size: int = 384) -> bool:
        """Ensure collection exists, create if it doesn't."""
        collection = collection or self.collection_name
        if collection not in self.collections:
            return self.create_collection(collection, vector_size)
        return True

    def add_point(
        self,
        vector: List[float],
        payload: Dict[str, Any],
        point_id: Optional[str] = None,
        collection: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Add a single point to collection."""
        collection = collection or self.collection_name
        self.ensure_collection(collection)

        if point_id is None:
            point_id = str(uuid4())
        elif not isinstance(point_id, str):
            point_id = str(point_id)

        self.points[collection][point_id] = {
            "vector": vector,
            "payload": payload,
        }
        return True, point_id

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            # Handle different vector sizes by padding the shorter one
            if len(vec1) < len(vec2):
                vec1 = vec1 + [0.0] * (len(vec2) - len(vec1))
            else:
                vec2 = vec2 + [0.0] * (len(vec1) - len(vec2))

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = sum(a * a for a in vec1) ** 0.5
        norm_b = sum(b * b for b in vec2) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def search_points(
        self,
        vector: List[float],
        limit: int = 5,
        collection: Optional[str] = None,
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar points with optional filtering."""
        collection = collection or self.collection_name
        if collection not in self.points:
            return []

        # Calculate similarities for all points
        similarities = []
        for point_id, point_data in self.points[collection].items():
            # Apply filters if provided
            if filters or user_id:
                payload = point_data["payload"]

                # Apply user_id filter
                if user_id and payload.get("user_id") != user_id:
                    continue

                # Apply additional filters
                if filters:
                    skip = False
                    for key, value in filters.items():
                        if key not in payload:
                            skip = True
                            break

                        # Handle dict filters (range queries)
                        if isinstance(value, dict):
                            if "gt" in value and not (payload[key] > value["gt"]):
                                skip = True
                                break
                            if "gte" in value and not (payload[key] >= value["gte"]):
                                skip = True
                                break
                            if "lt" in value and not (payload[key] < value["lt"]):
                                skip = True
                                break
                            if "lte" in value and not (payload[key] <= value["lte"]):
                                skip = True
                                break
                        # Handle list values - check if any filter value is in the payload list
                        elif isinstance(value, list):
                            payload_value = payload[key]
                            if isinstance(payload_value, list):
                                # Check if any filter value is in the payload list
                                if not any(v in payload_value for v in value):
                                    skip = True
                                    break
                            else:
                                # Payload value is not a list, check direct membership
                                if payload_value not in value:
                                    skip = True
                                    break
                        # Handle simple equality
                        elif payload[key] != value:
                            skip = True
                            break

                    if skip:
                        continue

            # Calculate similarity and normalize to [0, 1] range
            similarity = self._cosine_similarity(vector, point_data["vector"])
            # Normalize from [-1, 1] to [0, 1]
            normalized_score = (similarity + 1.0) / 2.0
            similarities.append((point_id, normalized_score))

        # Sort by similarity (descending) and take top limit
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_similarities = similarities[:limit]

        # Format results
        results = []
        for point_id, score in top_similarities:
            point_data = self.points[collection][point_id]
            results.append({
                "id": point_id,
                "score": score,
                "payload": point_data["payload"],
            })

        return results

    def get_point(self, point_id: str, collection: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a single point by ID."""
        collection = collection or self.collection_name
        if collection not in self.points or point_id not in self.points[collection]:
            return None

        point_data = self.points[collection][point_id]
        return {
            "id": point_id,
            "vector": point_data["vector"],
            "payload": point_data["payload"],
        }

    def delete_points(self, point_ids: List[str], collection: Optional[str] = None) -> bool:
        """Delete points by IDs."""
        collection = collection or self.collection_name
        if collection not in self.points:
            return True  # Nothing to delete

        for point_id in point_ids:
            if point_id in self.points[collection]:
                del self.points[collection][point_id]

        return True

    def get_collection_info(self, collection: Optional[str] = None) -> Dict[str, Any]:
        """Get collection information."""
        collection = collection or self.collection_name
        if collection not in self.collections:
            return {"exists": False}

        # Count vectors
        points_count = len(self.points.get(collection, {}))

        # Get vector size from first point if available
        vector_size = 384  # Default
        if points_count > 0:
            first_point_id = next(iter(self.points[collection]))
            vector_size = len(self.points[collection][first_point_id]["vector"])

        return {
            "exists": True,
            "vectors_count": points_count,
            "points_count": points_count,
            "config": {
                "vector_size": vector_size,
                "distance": "cosine",
            },
        }


class FakeKuzu(KuzuInterface):
    """Test double for KuzuInterface with in-memory storage."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize with in-memory storage."""
        # Skip parent initialization to avoid database requirements
        self.nodes: Dict[str, Dict[str, Dict[str, Any]]] = {
            "Memory": {},
            "Entity": {},
        }
        self.relationships: List[Dict[str, Any]] = []

    def add_node(self, table: str, properties: Dict[str, Any]) -> None:
        """Add a node to the graph."""
        if table not in self.nodes:
            self.nodes[table] = {}

        node_id = properties.get("id")
        if not node_id:
            raise ValueError("Node must have an id property")

        self.nodes[table][node_id] = properties

    def add_relationship(
        self,
        from_table: str,
        to_table: str,
        rel_type: str,
        from_id: str,
        to_id: str,
        props: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add relationship between nodes."""
        # Validate that nodes exist
        if from_id not in self.nodes.get(from_table, {}):
            raise ValueError(f"Node {from_id} not found in table {from_table}")
        if to_id not in self.nodes.get(to_table, {}):
            raise ValueError(f"Node {to_id} not found in table {to_table}")

        # Sanitize relationship type
        rel_type = rel_type.replace(" ", "_").replace("-", "_").upper()
        rel_type = "".join(c for c in rel_type if c.isalnum() or c == "_")

        # Add relationship
        self.relationships.append({
            "from_table": from_table,
            "to_table": to_table,
            "rel_type": rel_type,
            "from_id": from_id,
            "to_id": to_id,
            "props": props or {},
        })

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute Cypher query and return results."""
        params = params or {}

        # Simple implementation that handles basic memory queries
        if "MATCH (m:Memory)" in cypher:
            # Extract user_id filter if present
            user_id = params.get("user_id")

            # Extract query text if present
            query_text = params.get("q", "").lower()

            # Extract limit
            limit = params.get("limit", 10)

            # Filter memories
            results = []
            for node_id, node in self.nodes["Memory"].items():
                # Apply user_id filter
                if user_id and node.get("user_id") != user_id:
                    continue

                # Apply text search filter
                content = node.get("content", "").lower()
                title = node.get("title", "").lower()
                if query_text and query_text not in content and query_text not in title:
                    continue

                # Add to results
                results.append({
                    "m.id": node_id,
                    "m.user_id": node.get("user_id"),
                    "m.content": node.get("content"),
                    "m.title": node.get("title"),
                    "m.memory_type": node.get("memory_type"),
                    "m.created_at": node.get("created_at"),
                    "m.summary": node.get("summary"),
                    "m.source": node.get("source"),
                    "m.tags": node.get("tags"),
                    "m.confidence": node.get("confidence"),
                })

            # Sort by created_at (descending)
            results.sort(key=lambda x: x.get("m.created_at", ""), reverse=True)

            # Apply limit
            return results[:limit]

        # Return empty list for unsupported queries
        return []

    def neighbors(
        self,
        node_label: str,
        node_id: str,
        rel_types: Optional[List[str]] = None,
        direction: str = "any",
        limit: int = 10,
        neighbor_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch neighbors of a node."""
        results = []

        # Find relationships involving the node
        for rel in self.relationships:
            rel_type = rel["rel_type"]

            # Filter by relation type if specified
            if rel_types and rel_type not in rel_types:
                continue

            # Check direction and node label
            is_outgoing = (rel["from_table"] == node_label and rel["from_id"] == node_id)
            is_incoming = (rel["to_table"] == node_label and rel["to_id"] == node_id)

            if (direction == "out" and is_outgoing) or (direction == "in" and is_incoming) or (direction == "any" and (is_outgoing or is_incoming)):
                # Determine the neighbor node
                if is_outgoing:
                    neighbor_table = rel["to_table"]
                    neighbor_id = rel["to_id"]
                else:
                    neighbor_table = rel["from_table"]
                    neighbor_id = rel["from_id"]

                # Filter by neighbor label if specified
                if neighbor_label and neighbor_table != neighbor_label:
                    continue

                # Get the neighbor node
                if neighbor_id in self.nodes.get(neighbor_table, {}):
                    neighbor = self.nodes[neighbor_table][neighbor_id]

                    # Format result based on neighbor type
                    if neighbor_table == "Memory":
                        results.append({
                            "id": neighbor_id,
                            "user_id": neighbor.get("user_id"),
                            "content": neighbor.get("content"),
                            "title": neighbor.get("title"),
                            "memory_type": neighbor.get("memory_type"),
                            "created_at": neighbor.get("created_at"),
                            "rel_type": rel_type,
                        })
                    else:
                        results.append({
                            "node": neighbor,
                            "rel_type": rel_type,
                        })

        # Apply limit
        return results[:limit]


@pytest.fixture
def embedder() -> DummyEmbedder:
    """Fixture for DummyEmbedder."""
    return DummyEmbedder()


@pytest.fixture
def qdrant_fake() -> FakeQdrant:
    """Fixture for FakeQdrant."""
    return FakeQdrant()


@pytest.fixture
def kuzu_fake() -> FakeKuzu:
    """Fixture for FakeKuzu."""
    return FakeKuzu()


@pytest.fixture
def mem_factory() -> Callable[..., Memory]:
    """Fixture for creating Memory objects with defaults."""
    def _create_memory(**kwargs) -> Memory:
        defaults = {
            "id": str(uuid4()),
            "user_id": "test-user",
            "content": "Test memory content",
            "memory_type": MemoryType.NOTE,
            "title": "Test Title",
            "summary": None,
            "source": "user",
            "tags": ["test"],
            "confidence": 0.8,
            "vector": None,
            "is_valid": True,
            "created_at": datetime.now(UTC),
            "expires_at": None,
            "supersedes": None,
            "superseded_by": None,
            "task_status": None,
            "task_priority": None,
            "assignee": None,
            "due_date": None,
        }
        return Memory(**{**defaults, **kwargs})

    return _create_memory


@pytest.fixture
def tmp_env(monkeypatch):
    """Fixture for temporarily setting environment variables."""
    original_env = {}

    def _set_env(key: str, value: str):
        if key in os.environ:
            original_env[key] = os.environ[key]
        monkeypatch.setenv(key, value)

    yield _set_env

    # Restore original environment
    for key, value in original_env.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def neighbor_cap() -> int:
    """Fixture for neighbor cap constant."""
    return 5
