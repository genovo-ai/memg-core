"""
Performance benchmarks for MEMG v0.3 release.

These tests validate that the system meets our "Raspberry Pi test" requirements
and can deliver sub-second response times with minimal resource usage.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import psutil
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memory_system.models.core import Entity, EntityType, Memory, MemoryType, Relationship
from memory_system.processing.memory_processor import MemoryProcessor
from memory_system.processing.memory_retriever import MemoryRetriever


class TestPerformanceBenchmarks:
    """Performance benchmarks for v0.3 release."""

    def test_memory_creation_speed(self):
        """Test memory creation meets sub-second requirements."""
        start_time = time.time()
        memories = []

        # Create 100 memories
        for i in range(100):
            memory = Memory(
                user_id="perf_test",
                content=f"Performance test memory {i} with some content to make it realistic",
                memory_type=MemoryType.NOTE,
                title=f"Test Memory {i}",
            )
            memories.append(memory)

        end_time = time.time()
        duration = end_time - start_time

        # Should create 100 memories in under 0.1 seconds
        assert duration < 0.1, f"Memory creation too slow: {duration:.3f}s for 100 memories"

        # Verify all memories were created correctly
        assert len(memories) == 100
        assert all(m.user_id == "perf_test" for m in memories)

    def test_entity_creation_speed(self):
        """Test entity creation meets performance requirements."""
        start_time = time.time()
        entities = []

        # Create 100 entities with different types
        entity_types = list(EntityType)
        for i in range(100):
            entity = Entity(
                user_id="perf_test",
                name=f"Entity_{i}",
                type=entity_types[i % len(entity_types)],
                description=f"Performance test entity {i}",
            )
            entities.append(entity)

        end_time = time.time()
        duration = end_time - start_time

        # Should create 100 entities in under 0.1 seconds
        assert duration < 0.1, f"Entity creation too slow: {duration:.3f}s for 100 entities"

        # Verify entity types are distributed
        type_counts = {}
        for entity in entities:
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1

        # Should have used multiple entity types
        assert len(type_counts) > 10, "Not enough entity type diversity"

    def test_serialization_performance(self):
        """Test serialization to Kuzu/Qdrant is fast."""
        # Create test data
        memories = [
            Memory(
                user_id="perf_test",
                content=f"Test memory {i} with realistic content for serialization testing",
                memory_type=MemoryType.DOCUMENT,
                title=f"Document {i}",
            )
            for i in range(50)
        ]

        entities = [
            Entity(
                user_id="perf_test",
                name=f"Entity_{i}",
                type=EntityType.TECHNOLOGY,
                description=f"Technology entity {i}",
            )
            for i in range(50)
        ]

        # Test memory serialization speed
        start_time = time.time()
        for memory in memories:
            qdrant_payload = memory.to_qdrant_payload()
            kuzu_node = memory.to_kuzu_node()
        end_time = time.time()
        memory_duration = end_time - start_time

        # Test entity serialization speed
        start_time = time.time()
        for entity in entities:
            kuzu_node = entity.to_kuzu_node()
        end_time = time.time()
        entity_duration = end_time - start_time

        # Should serialize 50 memories + 50 entities in under 0.05 seconds total
        total_duration = memory_duration + entity_duration
        assert total_duration < 0.05, f"Serialization too slow: {total_duration:.3f}s"

    def test_enum_performance(self):
        """Test EntityType enum operations are fast."""
        start_time = time.time()

        # Test enum value access (common operation)
        for _ in range(1000):
            tech_value = EntityType.TECHNOLOGY.value
            db_value = EntityType.DATABASE.value
            component_value = EntityType.COMPONENT.value
            error_value = EntityType.ERROR.value

        # Test enum comparison (common in queries)
        for _ in range(1000):
            is_tech = EntityType.TECHNOLOGY == EntityType.TECHNOLOGY
            is_db = EntityType.DATABASE in [EntityType.DATABASE, EntityType.TECHNOLOGY]

        end_time = time.time()
        duration = end_time - start_time

        # Should handle 2000 enum operations in under 0.01 seconds
        assert duration < 0.01, f"Enum operations too slow: {duration:.3f}s"

    def test_memory_footprint(self):
        """Test memory objects have reasonable memory footprint."""
        import sys

        # Test single memory footprint
        memory = Memory(
            user_id="footprint_test",
            content="Test content for memory footprint analysis",
            memory_type=MemoryType.NOTE,
        )
        memory_size = sys.getsizeof(memory)

        # Test single entity footprint
        entity = Entity(
            user_id="footprint_test",
            name="TestEntity",
            type=EntityType.TECHNOLOGY,
            description="Test entity for footprint analysis",
        )
        entity_size = sys.getsizeof(entity)

        # Memory objects should be lightweight (under 1KB each)
        assert memory_size < 1024, f"Memory object too large: {memory_size} bytes"
        assert entity_size < 1024, f"Entity object too large: {entity_size} bytes"

        # Test collection footprint
        memories = [
            Memory(user_id="footprint_test", content=f"Memory {i}", memory_type=MemoryType.NOTE)
            for i in range(100)
        ]

        collection_size = sys.getsizeof(memories) + sum(sys.getsizeof(m) for m in memories)

        # 100 memories should be under 100KB total
        assert collection_size < 100 * 1024, f"Memory collection too large: {collection_size} bytes"

    def test_concurrent_operations_simulation(self):
        """Test system can handle multiple operations efficiently."""
        import queue
        import threading

        results = queue.Queue()

        def create_memories():
            """Worker function to create memories."""
            start = time.time()
            memories = []
            for i in range(20):
                memory = Memory(
                    user_id=f"concurrent_user_{threading.current_thread().ident}",
                    content=f"Concurrent memory {i}",
                    memory_type=MemoryType.NOTE,
                )
                memories.append(memory)
            end = time.time()
            results.put(("memory", end - start, len(memories)))

        def create_entities():
            """Worker function to create entities."""
            start = time.time()
            entities = []
            for i in range(20):
                entity = Entity(
                    user_id=f"concurrent_user_{threading.current_thread().ident}",
                    name=f"Entity_{i}",
                    type=EntityType.COMPONENT,
                    description=f"Concurrent entity {i}",
                )
                entities.append(entity)
            end = time.time()
            results.put(("entity", end - start, len(entities)))

        # Start concurrent operations
        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=create_memories)
            t2 = threading.Thread(target=create_entities)
            threads.extend([t1, t2])

        start_time = time.time()
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.time()
        total_duration = end_time - start_time

        # Collect results
        operation_results = []
        while not results.empty():
            operation_results.append(results.get())

        # Should complete 10 concurrent operations in under 1 second
        assert total_duration < 1.0, f"Concurrent operations too slow: {total_duration:.3f}s"

        # Verify all operations completed
        assert (
            len(operation_results) == 10
        ), f"Not all operations completed: {len(operation_results)}"

        # Verify each operation was reasonably fast
        for op_type, duration, count in operation_results:
            assert duration < 0.5, f"{op_type} operation too slow: {duration:.3f}s"
            assert count == 20, f"Wrong count for {op_type}: {count}"


class TestResourceUsage:
    """Test resource usage for Raspberry Pi compatibility."""

    def test_cpu_usage_during_operations(self):
        """Test CPU usage stays reasonable during operations."""
        # Get baseline CPU usage
        psutil.cpu_percent()  # First call to initialize
        time.sleep(0.1)
        baseline_cpu = psutil.cpu_percent()

        # Perform intensive operations
        start_cpu = psutil.cpu_percent()

        # Create many objects quickly
        memories = []
        entities = []
        for i in range(500):
            memory = Memory(
                user_id="cpu_test",
                content=f"CPU test memory {i} with content",
                memory_type=MemoryType.NOTE,
            )
            memories.append(memory)

            entity = Entity(
                user_id="cpu_test",
                name=f"CPUEntity_{i}",
                type=EntityType.TECHNOLOGY,
                description=f"CPU test entity {i}",
            )
            entities.append(entity)

            # Serialize some objects
            if i % 10 == 0:
                memory.to_qdrant_payload()
                entity.to_kuzu_node()

        time.sleep(0.1)
        end_cpu = psutil.cpu_percent()

        # CPU usage shouldn't spike dramatically
        cpu_increase = end_cpu - baseline_cpu
        assert cpu_increase < 50, f"CPU usage too high: {cpu_increase}% increase"

    def test_memory_usage_growth(self):
        """Test memory usage doesn't grow excessively."""
        import gc

        # Force garbage collection and get baseline
        gc.collect()
        process = psutil.Process()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large number of objects
        memories = []
        entities = []
        relationships = []

        for i in range(1000):
            memory = Memory(
                user_id="memory_test",
                content=f"Memory usage test {i} with some content to make it realistic",
                memory_type=MemoryType.DOCUMENT,
            )
            memories.append(memory)

            entity = Entity(
                user_id="memory_test",
                name=f"MemoryTestEntity_{i}",
                type=EntityType.COMPONENT,
                description=f"Memory test entity {i}",
            )
            entities.append(entity)

            relationship = Relationship(
                user_id="memory_test",
                source_id=memory.id,
                target_id=entity.id,
                relationship_type="MENTIONS",
            )
            relationships.append(relationship)

        # Check memory usage after creation
        current_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = current_memory - baseline_memory

        # Should not use more than 50MB for 1000 objects (very generous limit)
        assert memory_increase < 50, f"Memory usage too high: {memory_increase:.1f}MB increase"

        # Clean up and verify memory is released
        del memories, entities, relationships
        gc.collect()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_retained = final_memory - baseline_memory

        # Should release most memory (allow some overhead)
        assert memory_retained < 10, f"Too much memory retained: {memory_retained:.1f}MB"


class TestRaspberryPiCompatibility:
    """Test specific Raspberry Pi compatibility requirements."""

    def test_import_time_performance(self):
        """Test imports are fast (important for startup time)."""
        import importlib
        import sys

        # Test core module import time
        start_time = time.time()

        # Remove modules if already imported (for clean test)
        modules_to_remove = [name for name in sys.modules if name.startswith('memory_system')]
        for module_name in modules_to_remove:
            if module_name != 'memory_system.models.core':  # Keep this one as it's needed
                sys.modules.pop(module_name, None)

        # Time the imports
        from memory_system.models.core import Entity, EntityType, Memory
        from memory_system.processing.memory_processor import MemoryProcessor
        from memory_system.processing.memory_retriever import MemoryRetriever

        end_time = time.time()
        import_duration = end_time - start_time

        # Imports should be fast (under 2 seconds even on Raspberry Pi)
        assert import_duration < 2.0, f"Imports too slow: {import_duration:.3f}s"

    def test_minimal_dependencies(self):
        """Test that we don't import heavy dependencies unnecessarily."""
        import sys

        # Check that heavy ML/scientific libraries aren't imported
        heavy_libs = ['tensorflow', 'torch', 'sklearn', 'scipy', 'matplotlib']
        imported_heavy = [lib for lib in heavy_libs if lib in sys.modules]

        # Should not have any heavy dependencies loaded
        assert len(imported_heavy) == 0, f"Heavy dependencies detected: {imported_heavy}"

        # Check for reasonable dependency count
        memg_modules = [name for name in sys.modules if 'memory_system' in name]

        # Should have reasonable number of our own modules loaded
        assert len(memg_modules) < 50, f"Too many modules loaded: {len(memg_modules)}"

    def test_startup_simulation(self):
        """Simulate system startup time."""
        start_time = time.time()

        # Simulate typical startup operations
        from memory_system.models.core import Entity, EntityType, Memory, MemoryType

        # Create initial objects (like loading configuration)
        test_memory = Memory(
            user_id="startup_test", content="System startup test", memory_type=MemoryType.NOTE
        )

        test_entity = Entity(
            user_id="startup_test",
            name="StartupEntity",
            type=EntityType.SERVICE,
            description="System startup test entity",
        )

        # Simulate serialization (like initial database setup)
        test_memory.to_qdrant_payload()
        test_entity.to_kuzu_node()

        end_time = time.time()
        startup_duration = end_time - start_time

        # Startup operations should be very fast
        assert startup_duration < 0.5, f"Startup too slow: {startup_duration:.3f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
