"""Test fixtures and test doubles for memg_core tests."""

from collections.abc import Callable
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory


@pytest.fixture(scope="session", autouse=True)
def setup_yaml_schema():
    """Global YAML schema fixture that uses the test config file."""
    # Use the test config that includes memo and memo_test types
    config_path = Path(__file__).parent.parent / "config" / "core.test.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at: {config_path}")

    os.environ["MEMG_YAML_SCHEMA"] = str(config_path)

    # Initialize the TypeRegistry with the test config
    from memg_core.core.types import initialize_types_from_yaml

    initialize_types_from_yaml(str(config_path))

    return config_path


class DummyEmbedder:
    """Test double for Embedder that returns deterministic vectors."""

    def __init__(self, vector_size: int = 384):
        """Initialize with configurable vector size."""
        self.vector_size = vector_size
        # Skip parent initialization to avoid API key requirements

    def get_embedding(self, text: str) -> list[float]:
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
        self.collections: dict[str, dict[str, dict]] = {}
        self.points: dict[str, dict[str, Any]] = {}  # collection_name -> {id: {vector, payload}}

    def collection_exists(self, collection: str | None = None) -> bool:
        """Check if collection exists."""
        collection = collection or self.collection_name
        return collection in self.collections

    def create_collection(self, collection: str | None = None, vector_size: int = 384) -> bool:
        """Create a new collection."""
        collection = collection or self.collection_name
        if collection not in self.collections:
            self.collections[collection] = {}
            self.points[collection] = {}
        return True

    def ensure_collection(self, collection: str | None = None, vector_size: int = 384) -> bool:
        """Ensure collection exists, create if it doesn't."""
        collection = collection or self.collection_name
        if collection not in self.collections:
            return self.create_collection(collection, vector_size)
        return True

    def add_point(
        self,
        vector: list[float],
        payload: dict[str, Any],
        point_id: str | None = None,
        collection: str | None = None,
    ) -> tuple[bool, str]:
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

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            # Handle different vector sizes by padding the shorter one
            if len(vec1) < len(vec2):
                vec1 = vec1 + [0.0] * (len(vec2) - len(vec1))
            else:
                vec2 = vec2 + [0.0] * (len(vec1) - len(vec2))

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm_a = sum(a * a for a in vec1) ** 0.5
        norm_b = sum(b * b for b in vec2) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def search_points(
        self,
        vector: list[float],
        limit: int = 5,
        collection: str | None = None,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar points with optional filtering."""
        collection = collection or self.collection_name
        if collection not in self.points:
            return []

        def _dig(data: dict, path: str):
            """Helper to access nested dict values using dot notation"""
            keys = path.split(".")
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            return current

        def _passes_filters(payload: dict[str, Any]) -> bool:
            # support both nested payload {"core": {...}, "entity": {...}}
            # and dotted filter keys like "core.user_id"
            if user_id:
                # core user_id lives at core.user_id
                core_uid = _dig(payload, "core.user_id") or payload.get("user_id")
                if core_uid != user_id:
                    return False

            if not filters:
                return True

            for k, expected in filters.items():
                # Prefer dotted lookup, then direct top-level
                actual = _dig(payload, k)
                if actual is None:
                    actual = payload.get(k)

                # Ranges (gte/gt/lte/lt)
                if isinstance(expected, dict):
                    if "gt" in expected and not (actual > expected["gt"]):
                        return False
                    if "gte" in expected and not (actual >= expected["gte"]):
                        return False
                    if "lt" in expected and not (actual < expected["lt"]):
                        return False
                    if "lte" in expected and not (actual <= expected["lte"]):
                        return False
                    continue

                # List membership (e.g., tags)
                if isinstance(expected, list):
                    if isinstance(actual, list):
                        if not any(v in actual for v in expected):
                            return False
                    else:
                        if actual not in expected:
                            return False
                    continue

                # Simple equality
                if actual != expected:
                    return False

            return True

        # Calculate similarities for all points
        sims: list[tuple[str, float]] = []
        for point_id, point_data in self.points[collection].items():
            payload = point_data["payload"]
            if not _passes_filters(payload):
                continue

            # cosine similarity, normalized to [0, 1]
            similarity = self._cosine_similarity(vector, point_data["vector"])
            normalized = (similarity + 1.0) / 2.0
            sims.append((point_id, normalized))

        sims.sort(key=lambda x: x[1], reverse=True)
        sims = sims[:limit]

        results = []
        for pid, score in sims:
            pd = self.points[collection][pid]
            results.append({"id": pid, "score": score, "payload": pd["payload"]})
        return results

    def get_point(self, point_id: str, collection: str | None = None) -> dict[str, Any] | None:
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

    def delete_points(self, point_ids: list[str], collection: str | None = None) -> bool:
        """Delete points by IDs."""
        collection = collection or self.collection_name
        if collection not in self.points:
            return True  # Nothing to delete

        for point_id in point_ids:
            if point_id in self.points[collection]:
                del self.points[collection][point_id]

        return True

    def get_collection_info(self, collection: str | None = None) -> dict[str, Any]:
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

    def __init__(self, db_path: str | None = None):
        """Initialize with in-memory storage."""
        # Skip parent initialization to avoid database requirements
        self.nodes: dict[str, dict[str, dict[str, Any]]] = {
            "Memory": {},
        }
        self.relationships: list[dict[str, Any]] = []

    def add_node(self, table: str, properties: dict[str, Any]) -> None:
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
        props: dict[str, Any] | None = None,
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
        self.relationships.append(
            {
                "from_table": from_table,
                "to_table": to_table,
                "rel_type": rel_type,
                "from_id": from_id,
                "to_id": to_id,
                "props": props or {},
            }
        )

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Return rows shaped like the lean core expects (m.statement, m.hrid, etc.)."""
        params = params or {}
        if "MATCH (m:Memory)" not in cypher:
            return []

        user_id = params.get("user_id")
        limit = params.get("limit", 10)

        rows: list[dict[str, Any]] = []
        for _node_id, node in self.nodes["Memory"].items():
            if user_id and node.get("user_id") != user_id:
                continue

            # For memo and memo_test types, anchor field is always 'statement'
            anchor_field_value = node.get("statement") or ""

            # Use a placeholder if the anchor is still empty or not found
            if not anchor_field_value:
                anchor_field_value = (
                    f"missing-anchor-for-{node.get('memory_type')}-{node.get('hrid')}"
                )

            rows.append(
                {
                    "node": node,  # Return the full node object under 'node' key
                }
            )
        rows.sort(
            key=lambda r: r.get("node", {}).get("created_at") or "", reverse=True
        )  # Sort by created_at in node
        return rows[:limit]

    def neighbors(
        self,
        node_label: str,
        node_id: str,
        rel_types: list[str] | None = None,
        direction: str = "any",
        limit: int = 10,
        neighbor_label: str | None = None,
        id_type: str = "UUID",
    ) -> list[dict[str, Any]]:
        """Return neighbor Memory nodes — anchors-only (statement) to match v1 policy."""
        out: list[dict[str, Any]] = []

        # Find the actual node ID to use for relationship matching
        actual_node_id = node_id
        id_type_upper = id_type.upper()

        if id_type_upper == "HRID" and node_label in self.nodes:
            # Search for node by HRID and get its UUID for relationship matching
            for uuid, node in self.nodes[node_label].items():
                if node.get("hrid") == node_id:
                    actual_node_id = uuid
                    break

        for rel in self.relationships:
            if rel_types and rel["rel_type"] not in rel_types:
                continue

            is_out = rel["from_table"] == node_label and rel["from_id"] == actual_node_id
            is_in = rel["to_table"] == node_label and rel["to_id"] == actual_node_id
            if not (
                (direction == "out" and is_out)
                or (direction == "in" and is_in)
                or (direction == "any" and (is_out or is_in))
            ):
                continue

            # choose the neighbor side
            neighbor_table, neighbor_id = (
                (rel["to_table"], rel["to_id"]) if is_out else (rel["from_table"], rel["from_id"])
            )
            if neighbor_label and neighbor_table != neighbor_label:
                continue
            neighbor = self.nodes.get(neighbor_table, {}).get(neighbor_id)
            if not neighbor or neighbor_table != "Memory":
                continue

            # For memo and memo_test types, anchor field is always 'statement'
            anchor_field_value = neighbor.get("statement") or ""

            if not anchor_field_value:
                anchor_field_value = (
                    f"missing-anchor-for-{neighbor.get('memory_type')}-{neighbor.get('hrid')}"
                )

            # Return all fields from neighbor, not just selected ones
            neighbor_data = dict(neighbor)
            neighbor_data["rel_type"] = rel["rel_type"]  # Add relationship type for tests
            out.append(neighbor_data)
        return out[:limit]

    def delete_node(self, table: str, node_id: str) -> bool:
        """Delete a single node by ID from fake storage."""
        if table in self.nodes and node_id in self.nodes[table]:
            # Remove all relationships involving this node
            self.relationships = [
                rel
                for rel in self.relationships
                if not (
                    (rel["from_table"] == table and rel["from_id"] == node_id)
                    or (rel["to_table"] == table and rel["to_id"] == node_id)
                )
            ]
            # Remove the node
            del self.nodes[table][node_id]
            return True
        return False


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
        memory_type = kwargs.get("memory_type", kwargs.get("type", "memo"))

        # Build payload with statement inside it
        payload = {
            "statement": f"This is a test statement for {memory_type}.",
        }

        # Add type-specific fields to payload
        if memory_type == "memo_test":
            payload["details"] = "This is additional detail for the memo_test."
            payload["status"] = "todo"
            payload["priority"] = "medium"
            payload["assignee"] = "test-assignee"

        defaults = {
            "id": str(uuid4()),
            "user_id": "test-user",
            "memory_type": memory_type,
            "payload": payload,
            "confidence": 0.8,
            "is_valid": True,
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }

        # Allow kwargs to override defaults, but merge payload properly
        final_attrs = {**defaults, **kwargs}

        # Handle explicit statement parameter by putting it in payload
        if "statement" in kwargs:
            # Remove statement from top-level attrs since it belongs in payload
            explicit_statement = final_attrs.pop("statement", None)
            if "payload" in final_attrs:
                final_attrs["payload"] = {**final_attrs["payload"], "statement": explicit_statement}
            else:
                final_attrs["payload"] = {"statement": explicit_statement}

        # Merge explicit payload last to ensure it takes precedence
        if "payload" in kwargs:
            final_attrs["payload"] = {**final_attrs["payload"], **kwargs["payload"]}

        return Memory(**final_attrs)

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
