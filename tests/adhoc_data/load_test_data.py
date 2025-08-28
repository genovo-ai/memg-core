#!/usr/bin/env python3
"""
Load rich test data for memg-core E2E testing.

This script loads the software_dev.json dataset and creates all memories
with their relationships, tracking HRIDs for proper relationship linking.
"""

import json
from pathlib import Path
import sys
import tempfile
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from memg_core.api.public import MemgServices, add_memory, add_relationship, delete_memory, search


def load_test_dataset(json_path: str) -> dict[str, Any]:
    """Load test dataset from JSON file."""
    with open(json_path) as f:
        return json.load(f)


def create_memories(services: MemgServices, dataset: dict[str, Any]) -> dict[str, str]:
    """Create all memories and return HRID mapping."""
    hrid_map = {}
    user_id = dataset["user_id"]

    print(f"🚀 Creating {len(dataset['memories'])} memories for user '{user_id}'...")

    for i, memory_data in enumerate(dataset["memories"], 1):
        memory_type = memory_data["type"]
        payload = memory_data["payload"]
        hrid_key = memory_data["hrid_key"]

        # Use public API for testing
        memory = add_memory(
            memory_service=services.memory_service,
            yaml_translator=services.yaml_translator,
            memory_type=memory_type,
            payload=payload,
            user_id=user_id,
        )

        # Track HRID for relationships
        hrid_map[hrid_key] = memory.hrid

        print(f"  {i:2d}. {memory_type:8s} | {memory.hrid:12s} | {payload['statement'][:50]}...")

    return hrid_map


def create_relationships(
    services: MemgServices, dataset: dict[str, Any], hrid_map: dict[str, str]
) -> None:
    """Create all relationships using tracked HRIDs."""
    user_id = dataset["user_id"]
    relationships = dataset.get("relationships", [])

    print(f"\n🔗 Creating {len(relationships)} relationships...")

    for i, rel_data in enumerate(relationships, 1):
        source_key = rel_data["source_key"]
        target_key = rel_data["target_key"]
        relation_type = rel_data["relation_type"]
        description = rel_data["description"]

        source_hrid = hrid_map.get(source_key)
        target_hrid = hrid_map.get(target_key)

        if not source_hrid or not target_hrid:
            print(f"  ❌ {i:2d}. Missing HRID for {source_key} -> {target_key}")
            continue

        try:
            # Use public API add_relationship
            success = add_relationship(
                memory_service=services.memory_service,
                from_memory_id=source_hrid,
                to_memory_id=target_hrid,
                relation_type=relation_type,
                user_id=user_id,
            )

            if success:
                print(f"  ✅ {i:2d}. {relation_type:10s} | {source_hrid} -> {target_hrid}")
                print(f"      {description}")
            else:
                print(f"  ❌ {i:2d}. Failed to create relationship: {source_hrid} -> {target_hrid}")

        except Exception as e:
            print(f"  ❌ {i:2d}. Exception creating relationship: {e}")


def test_search(services: MemgServices, dataset: dict[str, Any]) -> None:
    """Test search functionality with the loaded data."""
    user_id = dataset["user_id"]

    print("\n🔍 Testing search functionality...")

    test_queries = [
        "HRID duplication bug",
        "architecture documentation",
        "YAML inheritance",
        "performance optimization",
        "vector embeddings",
    ]

    for query in test_queries:
        try:
            results = search(
                search_service=services.search_service, query=query, user_id=user_id, limit=3
            )

            print(f"\n  Query: '{query}'")
            print(f"  Found {len(results)} results:")

            for j, result in enumerate(results, 1):
                memory = result.memory
                statement = memory.payload.get("statement", "N/A")[:40]
                print(f"    {j}. {memory.memory_type:8s} | {result.score:.3f} | {statement}...")

        except Exception as e:
            print(f"  ❌ Search failed for '{query}': {e}")


def test_user_isolation(services: MemgServices) -> None:
    """Test user isolation by creating memories for different users."""
    print("\n🔒 Testing user isolation...")

    # Create memories for two different users
    alice_memory = add_memory(
        memory_service=services.memory_service,
        yaml_translator=services.yaml_translator,
        memory_type="note",
        payload={"statement": "Alice's private note", "project": "alice-project", "origin": "user"},
        user_id="alice",
    )

    bob_memory = add_memory(
        memory_service=services.memory_service,
        yaml_translator=services.yaml_translator,
        memory_type="note",
        payload={"statement": "Bob's private note", "project": "bob-project", "origin": "user"},
        user_id="bob",
    )

    print(f"  ✅ Alice's memory: {alice_memory.hrid}")
    print(f"  ✅ Bob's memory: {bob_memory.hrid}")

    # Test HRID uniqueness per user (both should be NOTE_AAA000)
    if alice_memory.hrid == bob_memory.hrid:
        print(f"  ✅ HRID isolation working: Both users have {alice_memory.hrid}")
    else:
        print(f"  ❌ HRID isolation failed: Alice={alice_memory.hrid}, Bob={bob_memory.hrid}")

    # Test search isolation - Alice should only see her memory
    alice_results = search(
        search_service=services.search_service, query="private note", user_id="alice", limit=10
    )

    bob_results = search(
        search_service=services.search_service, query="private note", user_id="bob", limit=10
    )

    print(f"  Alice sees {len(alice_results)} results (should be 1)")
    print(f"  Bob sees {len(bob_results)} results (should be 1)")

    # Verify isolation
    alice_sees_only_hers = (
        len(alice_results) == 1 and alice_results[0].memory.hrid == alice_memory.hrid
    )
    bob_sees_only_his = len(bob_results) == 1 and bob_results[0].memory.hrid == bob_memory.hrid

    if alice_sees_only_hers and bob_sees_only_his:
        print("  ✅ Search isolation working correctly")
    else:
        print("  ❌ Search isolation failed")

    # Test delete isolation - Alice can only delete her own memories
    # Since both have NOTE_AAA000, Alice will delete her own memory, not Bob's
    alice_count_before = len(search(services.search_service, "private note", "alice", limit=10))
    bob_count_before = len(search(services.search_service, "private note", "bob", limit=10))

    try:
        delete_memory(
            memory_service=services.memory_service,
            hrid_tracker=services.hrid_tracker,
            memory_id=bob_memory.hrid,  # Same HRID as Alice's (NOTE_AAA000)
            user_id="alice",
        )

        alice_count_after = len(search(services.search_service, "private note", "alice", limit=10))
        bob_count_after = len(search(services.search_service, "private note", "bob", limit=10))

        if alice_count_after == 0 and bob_count_after == 1:
            print("  ✅ Delete isolation working: Alice deleted her own memory, Bob's is safe")
        else:
            print(
                f"  ❌ Unexpected result: Alice {alice_count_before}→{alice_count_after}, Bob {bob_count_before}→{bob_count_after}"
            )

    except Exception as e:
        print(f"  ❌ Delete failed with exception: {e}")


def test_relationship_isolation(services: MemgServices) -> None:
    """Test relationship isolation between users."""
    print("\n🔗 Testing relationship isolation...")

    # Create memories for different users
    alice_task = add_memory(
        memory_service=services.memory_service,
        yaml_translator=services.yaml_translator,
        memory_type="task",
        payload={"statement": "Alice's task", "status": "todo", "priority": "medium"},
        user_id="alice",
    )

    bob_task = add_memory(
        memory_service=services.memory_service,
        yaml_translator=services.yaml_translator,
        memory_type="task",
        payload={"statement": "Bob's task", "status": "todo", "priority": "medium"},
        user_id="bob",
    )

    # Alice tries to create relationship with "Bob's memory" (same HRID)
    # Since both have TASK_AAA000, Alice will create relationship with her own memories
    try:
        success = add_relationship(
            memory_service=services.memory_service,
            from_memory_id=alice_task.hrid,
            to_memory_id=bob_task.hrid,  # Same HRID as Alice's (TASK_AAA000)
            relation_type="BLOCKS",
            user_id="alice",
        )

        if success:
            print(
                "  ✅ Relationship isolation working: Alice created relationship with her own memories"
            )
        else:
            print("  ❌ Same-user relationship failed unexpectedly")

    except Exception as e:
        print(f"  ❌ Relationship failed with exception: {e}")

    # Alice creates relationship with her own memories (should work)
    alice_task2 = add_memory(
        memory_service=services.memory_service,
        yaml_translator=services.yaml_translator,
        memory_type="task",
        payload={"statement": "Alice's second task", "status": "todo", "priority": "low"},
        user_id="alice",
    )

    try:
        success = add_relationship(
            memory_service=services.memory_service,
            from_memory_id=alice_task.hrid,
            to_memory_id=alice_task2.hrid,
            relation_type="BLOCKS",  # task->task relationship (explicit in YAML)
            user_id="alice",
        )

        if success:
            print("  ✅ Same-user relationship created successfully")
        else:
            print("  ❌ Same-user relationship failed")

    except Exception as e:
        print(f"  ❌ Same-user relationship failed with exception: {e}")


def main():
    """Main execution function."""
    # Paths
    script_dir = Path(__file__).parent
    json_path = script_dir / "software_dev.json"
    yaml_path = script_dir.parent.parent / "config" / "software_dev.yaml"

    print("📊 MEMG-Core E2E Test Data Loader")
    print("=" * 50)

    # Load dataset
    try:
        dataset = load_test_dataset(str(json_path))
        print(f"✅ Loaded dataset: {dataset['description']}")
        print(f"   Project: {dataset['project']}")
        print(f"   User: {dataset['user_id']}")
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        return 1

    # Create temporary database
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary database: {temp_dir}")

        try:
            # Initialize services
            services = MemgServices(
                yaml_path=str(yaml_path), db_path=temp_dir, db_name="memg_e2e_test"
            )

            print("✅ Services initialized successfully!")

            # Create memories
            hrid_map = create_memories(services, dataset)

            # Create relationships (when implemented)
            create_relationships(services, dataset, hrid_map)

            # Test search
            test_search(services, dataset)

            # Test user isolation
            test_user_isolation(services)

            # Test relationship isolation
            test_relationship_isolation(services)

            # Summary
            print("\n🎉 E2E Test Complete!")
            print(f"   Created: {len(dataset['memories'])} memories")
            print(f"   Relationships: {len(dataset.get('relationships', []))} defined")
            print(f"   HRID Mapping: {len(hrid_map)} tracked")
            print("   User isolation: Tested with multi-user scenarios")

            # Clean up
            services.close()
            print("✅ Services closed successfully!")

        except Exception as e:
            print(f"❌ E2E test failed: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
