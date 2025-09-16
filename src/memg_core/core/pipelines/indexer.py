"""MemoryStore: Unified YAML-driven memory storage class.

Clean, class-based interface that handles both graph and vector operations.
Follows Option 3 (Composite Interface) pattern with full YAML schema compliance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...utils import generate_hrid
from ...utils.db_clients import DatabaseClients
from ...utils.hrid_tracker import HridTracker
from ..exceptions import ProcessingError


class MemoryService:
    """Unified memory service - handles indexing, search, and deletion operations.

    Provides a clean, class-based interface for all memory operations using
    DatabaseClients for both DDL initialization and CRUD interface access.
    Eliminates the need for scattered interface creation.

    Attributes:
        qdrant: Qdrant interface instance.
        kuzu: Kuzu interface instance.
        embedder: Embedder instance.
        yaml_translator: YAML translator instance.
        hrid_tracker: HRID tracker instance.
    """

    def __init__(self, db_clients):
        """Initialize MemoryService with DatabaseClients.

        Args:
            db_clients: DatabaseClients instance (after init_dbs() called).
        """
        if not isinstance(db_clients, DatabaseClients):
            raise TypeError("db_clients must be a DatabaseClients instance")

        # Get interfaces from DatabaseClients (reuses DDL-created clients)
        self.qdrant = db_clients.get_qdrant_interface()
        self.kuzu = db_clients.get_kuzu_interface()
        self.embedder = db_clients.get_embedder()
        self.yaml_translator = db_clients.get_yaml_translator()
        self.hrid_tracker = HridTracker(self.kuzu)

        # Initialize memory serializer for packing/unpacking
        from .retrieval import MemorySerializer

        self.memory_serializer = MemorySerializer(self.hrid_tracker)

    def add_memory(
        self,
        memory_type: str,
        payload: dict[str, Any],
        user_id: str,
    ) -> str:
        """Add a memory to both graph and vector storage.

        Args:
            memory_type: Entity type from YAML schema (e.g., 'task', 'note').
            payload: Memory data conforming to YAML schema.
            user_id: Owner of the memory.

        Returns:
            str: Memory HRID (Human-readable ID string).

        Raises:
            ProcessingError: If validation fails or storage operations fail.
        """
        try:
            # Create and validate memory from YAML schema using our instance
            memory = self.yaml_translator.create_memory_from_yaml(memory_type, payload, user_id)

            # Stamp timestamps
            now = datetime.now(UTC)
            if not memory.created_at:
                memory.created_at = now
            memory.updated_at = now

            # Generate HRID using tracker
            hrid = generate_hrid(memory_type, user_id, self.hrid_tracker)

            # Get anchor text from YAML-defined anchor field using our instance
            anchor_text = self.yaml_translator.build_anchor_text(memory)
            if not anchor_text:
                raise ProcessingError(
                    f"Empty anchor text for memory type '{memory_type}'",
                    operation="add_memory",
                    context={"memory_id": memory.id, "memory_type": memory_type},
                )

            # Generate embedding from anchor text
            vector = self.embedder.get_embedding(anchor_text)

            # Use centralized serializer for packing
            flat_payload = self.memory_serializer.to_qdrant_payload(memory, hrid)
            kuzu_data = self.memory_serializer.to_kuzu_data(memory)

            # Add to Qdrant (vector storage) with complete payload
            success, _point_id = self.qdrant.add_point(
                vector=vector,
                payload=flat_payload,
                point_id=memory.id,
            )
            if not success:
                raise ProcessingError(
                    "Failed to add memory to vector storage",
                    operation="add_memory",
                    context={"memory_id": memory.id},
                )

            # Add to Kuzu (graph storage) - use entity-specific table
            self.kuzu.add_node(memory_type, kuzu_data)

            # Create HRID mapping after successful storage
            self.hrid_tracker.create_mapping(hrid, memory.id, memory_type, user_id)

            return hrid  # Return HRID, not UUID

        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(
                "Failed to add memory",
                operation="add_memory",
                context={"memory_type": memory_type, "user_id": user_id},
                original_error=e,
            ) from e

    def update_memory(
        self,
        hrid: str,
        payload_updates: dict[str, Any],
        user_id: str,
        memory_type: str | None = None,
    ) -> bool:
        """Update memory with partial payload changes (patch-style update).

        Args:
            hrid: Memory HRID to update.
            payload_updates: Dictionary of fields to update (only changed fields).
            user_id: User ID for ownership verification.
            memory_type: Optional memory type hint (inferred from HRID if not provided).

        Returns:
            bool: True if update succeeded.

        Raises:
            ProcessingError: If update fails or memory not found.
        """
        try:
            # Infer memory type from HRID if not provided
            if memory_type is None:
                memory_type = "_".join(hrid.split("_")[:-1])

            # Get existing UUID to preserve relationships
            uuid = self.hrid_tracker.get_uuid(hrid, user_id)

            # Get current memory data from Qdrant to merge with updates
            current_point = self.qdrant.get_point(uuid)
            if not current_point:
                raise ProcessingError(
                    f"Memory not found for HRID {hrid}",
                    operation="update_memory",
                    context={"hrid": hrid, "user_id": user_id},
                )

            # Merge current payload with updates
            current_payload = current_point.get("payload", {})
            # Remove system fields from current payload to get user fields only
            user_fields = {
                k: v
                for k, v in current_payload.items()
                if k
                not in (
                    "id",
                    "user_id",
                    "memory_type",
                    "created_at",
                    "updated_at",
                    "hrid",
                )
            }

            # Merge updates into user fields
            updated_user_payload = {**user_fields, **payload_updates}

            # Validate merged payload against YAML schema
            memory = self.yaml_translator.create_memory_from_yaml(
                memory_type, updated_user_payload, user_id
            )
            memory.id = uuid  # Preserve existing UUID for relationships

            # Update timestamps - preserve created_at, update updated_at
            memory.created_at = datetime.fromisoformat(current_payload.get("created_at"))
            memory.updated_at = datetime.now(UTC)

            # Get anchor text for vector update
            anchor_text = self.yaml_translator.build_anchor_text(memory)
            if not anchor_text:
                raise ProcessingError(
                    f"Empty anchor text for memory type '{memory_type}'",
                    operation="update_memory",
                    context={"memory_id": memory.id, "memory_type": memory_type},
                )

            # Generate new embedding from updated anchor text
            vector = self.embedder.get_embedding(anchor_text)

            # Use centralized serializer for packing
            flat_payload = self.memory_serializer.to_qdrant_payload(memory, hrid)
            kuzu_data = self.memory_serializer.to_kuzu_data(memory)

            # Update Qdrant point (upsert with same UUID)
            success, _point_id = self.qdrant.add_point(
                vector=vector,
                payload=flat_payload,
                point_id=memory.id,  # Same UUID preserves relationships
            )
            if not success:
                raise ProcessingError(
                    "Failed to update memory in vector storage",
                    operation="update_memory",
                    context={"memory_id": memory.id, "hrid": hrid},
                )

            # Update Kuzu node using efficient update_node method
            # This preserves relationships and is more efficient than delete+add
            success = self.kuzu.update_node(memory_type, uuid, kuzu_data, user_id)
            if not success:
                raise ProcessingError(
                    "Failed to update memory in graph storage - memory not found",
                    operation="update_memory",
                    context={"memory_id": uuid, "hrid": hrid, "user_id": user_id},
                )

            return True

        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(
                "Failed to update memory",
                operation="update_memory",
                context={"hrid": hrid, "user_id": user_id, "memory_type": memory_type},
                original_error=e,
            ) from e

    def add_relationship(
        self,
        from_memory_hrid: str,
        to_memory_hrid: str,
        relation_type: str,
        from_memory_type: str,
        to_memory_type: str,
        user_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a relationship between two memories using HRIDs.

        Args:
            from_memory_hrid: Source memory HRID.
            to_memory_hrid: Target memory HRID.
            relation_type: Relationship type from YAML schema (e.g., 'ANNOTATES').
            from_memory_type: Source memory entity type.
            to_memory_type: Target memory entity type.
            user_id: User ID for ownership verification.
            properties: Optional relationship properties.

        Raises:
            ProcessingError: If relationship creation fails.
        """
        try:
            # Translate HRIDs to UUIDs
            from_uuid = self.hrid_tracker.get_uuid(from_memory_hrid, user_id)
            to_uuid = self.hrid_tracker.get_uuid(to_memory_hrid, user_id)

            self.kuzu.add_relationship(
                from_table=from_memory_type,
                to_table=to_memory_type,
                rel_type=relation_type,
                from_id=from_uuid,
                to_id=to_uuid,
                user_id=user_id,
                props=properties or {},
            )
        except Exception as e:
            raise ProcessingError(
                "Failed to add relationship",
                operation="add_relationship",
                context={
                    "from_hrid": from_memory_hrid,
                    "to_hrid": to_memory_hrid,
                    "relation_type": relation_type,
                },
                original_error=e,
            ) from e

    def delete_relationship(
        self,
        from_memory_hrid: str,
        to_memory_hrid: str,
        relation_type: str,
        from_memory_type: str | None = None,
        to_memory_type: str | None = None,
        user_id: str | None = None,
    ) -> bool:
        """Delete a relationship between two memories using HRIDs.

        Args:
            from_memory_hrid: Source memory HRID.
            to_memory_hrid: Target memory HRID.
            relation_type: Relationship type from YAML schema (e.g., 'ANNOTATES').
            from_memory_type: Source memory entity type (inferred from HRID if not provided).
            to_memory_type: Target memory entity type (inferred from HRID if not provided).
            user_id: User ID for ownership verification (required).

        Returns:
            bool: True if deletion succeeded, False if relationship not found.

        Raises:
            ProcessingError: If relationship deletion fails or parameters invalid.
        """
        try:
            # Validate required user_id
            if not user_id:
                raise ProcessingError(
                    "user_id is required for relationship deletion",
                    operation="delete_relationship",
                    context={"from_hrid": from_memory_hrid, "to_hrid": to_memory_hrid},
                )

            # Infer memory types from HRIDs if not provided
            if from_memory_type is None:
                from_memory_type = "_".join(from_memory_hrid.split("_")[:-1])
            if to_memory_type is None:
                to_memory_type = "_".join(to_memory_hrid.split("_")[:-1])

            # Translate HRIDs to UUIDs
            from_uuid = self.hrid_tracker.get_uuid(from_memory_hrid, user_id)
            to_uuid = self.hrid_tracker.get_uuid(to_memory_hrid, user_id)

            # Delete relationship using Kuzu interface
            return self.kuzu.delete_relationship(
                from_table=from_memory_type,
                to_table=to_memory_type,
                rel_type=relation_type,
                from_id=from_uuid,
                to_id=to_uuid,
                user_id=user_id,
            )

        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            raise ProcessingError(
                "Failed to delete relationship",
                operation="delete_relationship",
                context={
                    "from_hrid": from_memory_hrid,
                    "to_hrid": to_memory_hrid,
                    "relation_type": relation_type,
                },
                original_error=e,
            ) from e

    def delete_memory(self, memory_hrid: str, memory_type: str, user_id: str) -> bool:
        """Delete a memory from both storages using HRID.

        Args:
            memory_hrid: Memory HRID to delete.
            memory_type: Memory entity type.
            user_id: User ID for ownership verification.

        Returns:
            bool: True if deletion succeeded.
        """
        try:
            # Translate HRID to UUID
            uuid = self.hrid_tracker.get_uuid(memory_hrid, user_id)

            # Delete from Qdrant (with user ownership verification)
            qdrant_success = self.qdrant.delete_points([uuid], user_id)

            # Delete from Kuzu (with user_id verification)
            kuzu_success = self.kuzu.delete_node(memory_type, uuid, user_id)

            # Mark HRID as deleted (soft delete in mapping)
            if qdrant_success and kuzu_success:
                self.hrid_tracker.mark_deleted(memory_hrid)

            return qdrant_success and kuzu_success

        except Exception as e:
            raise ProcessingError(
                "Failed to delete memory",
                operation="delete_memory",
                context={"memory_hrid": memory_hrid, "memory_type": memory_type},
                original_error=e,
            ) from e


def create_memory_service(db_clients) -> MemoryService:
    """Factory function to create a MemoryService instance.

    Args:
        db_clients: DatabaseClients instance (after init_dbs() called).

    Returns:
        MemoryService: Configured MemoryService instance.
    """
    return MemoryService(db_clients)
