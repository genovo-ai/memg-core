"""Test delete_memory function in public API."""

from uuid import uuid4

import pytest

from memg_core.api.public import add_memory, delete_memory, search
from memg_core.core.exceptions import ValidationError


class TestDeleteMemory:
    """Test delete_memory functionality."""

    def test_delete_memory_success(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test successful memory deletion."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        # Mock the interfaces
        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create a memory first
        memory = add_memory(
            memory_type="memo", payload={"statement": "Test memory to delete"}, user_id="test-user"
        )

        memory_id = memory.id

        # Verify memory exists
        search_results = search("Test memory", user_id="test-user", limit=5)
        assert len(search_results) == 1
        assert search_results[0].memory.id == memory_id

        # Delete the memory
        result = delete_memory(memory_id=memory_id, user_id="test-user")
        assert result is True

        # Verify memory is gone from search
        search_results = search("Test memory", user_id="test-user", limit=5)
        assert len(search_results) == 0

        # Verify memory is gone from Qdrant
        point = qdrant_fake.get_point(memory_id)
        assert point is None

        # Verify memory is gone from Kuzu
        assert memory_id not in kuzu_fake.nodes["Memory"]

    def test_delete_memory_nonexistent(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting non-existent memory."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        fake_id = str(uuid4())

        with pytest.raises(ValidationError, match=f"Memory with ID {fake_id} not found"):
            delete_memory(memory_id=fake_id, user_id="test-user")

    def test_delete_memory_wrong_user(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting memory with wrong user ID."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create a memory with one user
        memory = add_memory(
            memory_type="memo", payload={"statement": "User A's memory"}, user_id="user-a"
        )

        memory_id = memory.id

        # Try to delete with different user
        with pytest.raises(
            ValidationError, match=f"Memory {memory_id} does not belong to user user-b"
        ):
            delete_memory(memory_id=memory_id, user_id="user-b")

        # Verify memory still exists
        search_results = search("User A's memory", user_id="user-a", limit=5)
        assert len(search_results) == 1

    def test_delete_memory_validation_errors(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test validation errors in delete_memory."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Test empty memory_id
        with pytest.raises(ValidationError, match="memory_id is required and cannot be empty"):
            delete_memory(memory_id="", user_id="test-user")

        # Test None memory_id
        with pytest.raises(ValidationError, match="memory_id is required and cannot be empty"):
            delete_memory(memory_id=None, user_id="test-user")

        # Test empty user_id
        with pytest.raises(ValidationError, match="user_id is required and cannot be empty"):
            delete_memory(memory_id=str(uuid4()), user_id="")

        # Test None user_id
        with pytest.raises(ValidationError, match="user_id is required and cannot be empty"):
            delete_memory(memory_id=str(uuid4()), user_id=None)

    def test_delete_memory_with_relationships(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting memory that has relationships."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create two memories
        memory1 = add_memory(
            memory_type="memo", payload={"statement": "First memory"}, user_id="test-user"
        )

        memory2 = add_memory(
            memory_type="memo", payload={"statement": "Second memory"}, user_id="test-user"
        )

        # Add a relationship between them
        kuzu_fake.add_relationship(
            from_table="Memory",
            to_table="Memory",
            rel_type="RELATED_TO",
            from_id=memory1.id,
            to_id=memory2.id,
        )

        # Verify relationship exists
        neighbors = kuzu_fake.neighbors("Memory", memory1.id, rel_types=["RELATED_TO"], limit=5)
        assert len(neighbors) == 1
        assert neighbors[0]["id"] == memory2.id

        # Delete first memory
        result = delete_memory(memory_id=memory1.id, user_id="test-user")
        assert result is True

        # Verify memory is deleted
        assert memory1.id not in kuzu_fake.nodes["Memory"]

        # Verify relationship is also deleted
        neighbors = kuzu_fake.neighbors("Memory", memory2.id, rel_types=["RELATED_TO"], limit=5)
        assert len(neighbors) == 0

        # Verify second memory still exists
        assert memory2.id in kuzu_fake.nodes["Memory"]
        search_results = search("Second memory", user_id="test-user", limit=5)
        assert len(search_results) == 1

    def test_delete_memory_multiple_types(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting memories of different types."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create memories of different types
        memo = add_memory(
            memory_type="memo", payload={"statement": "A simple memo"}, user_id="test-user"
        )

        memo_test = add_memory(
            memory_type="memo_test",
            payload={
                "statement": "A test memo",
                "details": "Test details",
                "status": "todo",
                "priority": "high",
            },
            user_id="test-user",
        )

        # Delete memo
        result = delete_memory(memory_id=memo.id, user_id="test-user")
        assert result is True

        # Verify memo is deleted but memo_test remains
        search_results = search("memo", user_id="test-user", limit=10)
        assert len(search_results) == 1
        assert search_results[0].memory.id == memo_test.id

        # Delete memo_test
        result = delete_memory(memory_id=memo_test.id, user_id="test-user")
        assert result is True

        # Verify all memories deleted
        search_results = search("memo", user_id="test-user", limit=10)
        assert len(search_results) == 0

    def test_delete_memory_by_hrid(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting memory using HRID instead of UUID."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create a memory first
        memory = add_memory(
            memory_type="memo",
            payload={"statement": "Test memory for HRID deletion"},
            user_id="test-user",
        )

        memory_uuid = memory.id
        memory_hrid = memory.hrid

        # Verify memory exists using UUID
        search_results = search("HRID deletion", user_id="test-user", limit=5)
        assert len(search_results) == 1
        assert search_results[0].memory.id == memory_uuid

        # Delete using HRID instead of UUID
        result = delete_memory(memory_id=memory_hrid, user_id="test-user")
        assert result is True

        # Verify memory is gone from search
        search_results = search("HRID deletion", user_id="test-user", limit=5)
        assert len(search_results) == 0

        # Verify memory is gone from Qdrant (using UUID)
        point = qdrant_fake.get_point(memory_uuid)
        assert point is None

        # Verify memory is gone from Kuzu (using UUID)
        assert memory_uuid not in kuzu_fake.nodes["Memory"]

    def test_delete_memory_hrid_vs_uuid_equivalence(
        self, qdrant_fake, kuzu_fake, embedder, monkeypatch
    ):
        """Test that deleting by HRID and UUID are equivalent operations."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create two identical memories
        memory1 = add_memory(
            memory_type="memo",
            payload={"statement": "Memory for UUID deletion"},
            user_id="test-user",
        )
        memory2 = add_memory(
            memory_type="memo",
            payload={"statement": "Memory for HRID deletion"},
            user_id="test-user",
        )

        # Delete first memory by UUID
        result1 = delete_memory(memory_id=memory1.id, user_id="test-user")
        assert result1 is True

        # Delete second memory by HRID
        result2 = delete_memory(memory_id=memory2.hrid, user_id="test-user")
        assert result2 is True

        # Verify both are deleted
        point1 = qdrant_fake.get_point(memory1.id)
        point2 = qdrant_fake.get_point(memory2.id)
        assert point1 is None
        assert point2 is None

    def test_delete_memory_invalid_hrid_format(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting with invalid HRID format."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Try to delete with invalid HRID format
        invalid_hrids = ["INVALID_HRID", "NOT_A_REAL_HRID_123", "FAKE_HRID_XYZ999"]

        for invalid_hrid in invalid_hrids:
            with pytest.raises(ValidationError, match=f"Memory with ID {invalid_hrid} not found"):
                delete_memory(memory_id=invalid_hrid, user_id="test-user")

    def test_delete_memory_hrid_wrong_user(self, qdrant_fake, kuzu_fake, embedder, monkeypatch):
        """Test deleting memory by HRID with wrong user ID."""
        # Setup environment and interfaces
        monkeypatch.setenv("QDRANT_STORAGE_PATH", "/tmp/test_qdrant")
        monkeypatch.setenv("KUZU_DB_PATH", "/tmp/test_kuzu.db")

        from memg_core.api import public

        monkeypatch.setattr(public, "QdrantInterface", lambda **kwargs: qdrant_fake)
        monkeypatch.setattr(public, "KuzuInterface", lambda **kwargs: kuzu_fake)
        monkeypatch.setattr(public, "Embedder", lambda: embedder)

        # Create a memory with one user
        memory = add_memory(
            memory_type="memo", payload={"statement": "User A's memory"}, user_id="user-a"
        )

        memory_hrid = memory.hrid

        # Try to delete with different user using HRID
        with pytest.raises(
            ValidationError, match=f"Memory {memory_hrid} does not belong to user user-b"
        ):
            delete_memory(memory_id=memory_hrid, user_id="user-b")

        # Verify memory still exists using HRID search
        search_results = search("User A's memory", user_id="user-a", limit=5)
        assert len(search_results) == 1
