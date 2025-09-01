"""HRID Tracker: UUID ↔ HRID translation and lifecycle management.

Handles all HRID mapping operations using the existing KuzuInterface.
Provides transparent translation between user-facing HRIDs and internal UUIDs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..core.exceptions import DatabaseError
from ..core.interfaces.kuzu import KuzuInterface
from .hrid import _alpha_to_idx, parse_hrid


class HridTracker:
    """Manages HRID ↔ UUID mappings using KuzuInterface.

    Attributes:
        kuzu: Pre-configured Kuzu interface for database operations.
    """

    def __init__(self, kuzu_interface: KuzuInterface):
        """Initialize with existing KuzuInterface.

        Args:
            kuzu_interface: Pre-configured Kuzu interface for database operations.
        """
        self.kuzu = kuzu_interface

    def get_uuid(self, hrid: str, user_id: str) -> str:
        """Translate HRID to UUID.

        Args:
            hrid: Human-readable ID (e.g., 'TASK_AAA001').
            user_id: User ID for scoped lookup.

        Returns:
            str: UUID string for internal operations.

        Raises:
            DatabaseError: If HRID not found or is deleted.
        """
        try:
            query = """
            MATCH (m:HridMapping {hrid: $hrid, user_id: $user_id})
            WHERE m.deleted_at IS NULL
            RETURN m.uuid as uuid
            """
            results = self.kuzu.query(query, {"hrid": hrid, "user_id": user_id})

            if not results:
                raise DatabaseError(
                    f"HRID '{hrid}' not found or has been deleted",
                    operation="get_uuid",
                    context={"hrid": hrid},
                )

            return results[0]["uuid"]

        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(
                f"Failed to lookup UUID for HRID '{hrid}'",
                operation="get_uuid",
                context={"hrid": hrid},
                original_error=e,
            ) from e

    def get_hrid(self, uuid: str, user_id: str) -> str:
        """Translate UUID to HRID with user verification.

        Args:
            uuid: Internal UUID.
            user_id: User ID for ownership verification.

        Returns:
            str: Human-readable ID string.

        Raises:
            DatabaseError: If UUID not found, deleted, or doesn't belong to user.
        """
        try:
            query = """
            MATCH (m:HridMapping {uuid: $uuid, user_id: $user_id})
            WHERE m.deleted_at IS NULL
            RETURN m.hrid as hrid
            """
            results = self.kuzu.query(query, {"uuid": uuid, "user_id": user_id})

            if not results:
                raise DatabaseError(
                    f"UUID '{uuid}' not found or has been deleted",
                    operation="get_hrid",
                    context={"uuid": uuid},
                )

            return results[0]["hrid"]

        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(
                f"Failed to lookup HRID for UUID '{uuid}'",
                operation="get_hrid",
                context={"uuid": uuid},
                original_error=e,
            ) from e

    def create_mapping(self, hrid: str, uuid: str, memory_type: str, user_id: str) -> None:
        """Create new HRID ↔ UUID mapping.

        Args:
            hrid: Human-readable ID.
            uuid: Internal UUID.
            memory_type: Entity type (e.g., 'task', 'note').
            user_id: User ID for scoped mapping.

        Raises:
            DatabaseError: If mapping creation fails.
        """
        try:
            now = datetime.now(UTC).isoformat()

            mapping_data = {
                "hrid_user_key": f"{hrid}#{user_id}",  # Composite key
                "hrid": hrid,
                "uuid": uuid,
                "memory_type": memory_type,
                "user_id": user_id,
                "created_at": now,
                "deleted_at": None,  # NULL for active mappings
            }

            self.kuzu.add_node("HridMapping", mapping_data)

        except Exception as e:
            raise DatabaseError(
                f"Failed to create HRID mapping: {hrid} → {uuid}",
                operation="create_mapping",
                context={"hrid": hrid, "uuid": uuid, "memory_type": memory_type},
                original_error=e,
            ) from e

    def mark_deleted(self, hrid: str) -> None:
        """Mark HRID mapping as deleted (soft delete)

        Args:
            hrid: Human-readable ID to mark as deleted

        Raises:
            DatabaseError: If marking as deleted fails
        """
        try:
            now = datetime.now(UTC).isoformat()

            query = """
            MATCH (m:HridMapping {hrid: $hrid})
            SET m.deleted_at = $deleted_at
            RETURN m.hrid as hrid
            """

            results = self.kuzu.query(query, {"hrid": hrid, "deleted_at": now})

            if not results:
                raise DatabaseError(
                    f"HRID '{hrid}' not found for deletion",
                    operation="mark_deleted",
                    context={"hrid": hrid},
                )

        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(
                f"Failed to mark HRID '{hrid}' as deleted",
                operation="mark_deleted",
                context={"hrid": hrid},
                original_error=e,
            ) from e

    def get_highest_hrid(self, memory_type: str, user_id: str) -> tuple[str, int, int] | None:
        """Get highest HRID for a memory type (for generation).

        Args:
            memory_type: Entity type to check (case insensitive).
            user_id: User ID for scoped HRID lookup.

        Returns:
            tuple[str, int, int] | None: (hrid, alpha_idx, num) or None if no HRIDs exist.
        """
        try:
            # Normalize to lowercase for database query (YAML types are lowercase)
            normalized_type = memory_type.lower()

            query = """
            MATCH (m:HridMapping {memory_type: $memory_type, user_id: $user_id})
            RETURN m.hrid as hrid
            ORDER BY m.created_at DESC
            LIMIT 1000
            """

            results = self.kuzu.query(query, {"memory_type": normalized_type, "user_id": user_id})

            if not results:
                return None

            # Find the highest HRID by parsing all results
            highest_hrid = None
            highest_alpha_idx = -1
            highest_num = -1

            for result in results:
                hrid = result["hrid"]
                try:
                    # TODO: parsed_type available for future use (e.g., type validation)
                    _, alpha, num = parse_hrid(hrid)
                    alpha_idx = _alpha_to_idx(alpha)

                    if alpha_idx > highest_alpha_idx or (
                        alpha_idx == highest_alpha_idx and num > highest_num
                    ):
                        highest_alpha_idx = alpha_idx
                        highest_num = num
                        highest_hrid = hrid

                except ValueError:
                    continue  # Skip invalid HRIDs

            if highest_hrid is None:
                return None

            return (highest_hrid, highest_alpha_idx, highest_num)

        except Exception as e:
            raise DatabaseError(
                f"Failed to get highest HRID for type '{memory_type}' and user '{user_id}'",
                operation="get_highest_hrid",
                context={"memory_type": memory_type, "user_id": user_id},
                original_error=e,
            ) from e

    def exists(self, hrid: str) -> bool:
        """Check if HRID exists (active, not deleted).

        Args:
            hrid: Human-readable ID to check.

        Returns:
            bool: True if HRID exists and is active.
        """
        try:
            query = """
            MATCH (m:HridMapping {hrid: $hrid})
            WHERE m.deleted_at IS NULL
            RETURN COUNT(m) as count
            """
            results = self.kuzu.query(query, {"hrid": hrid})
            return results[0]["count"] > 0 if results else False

        except (DatabaseError, ValueError, KeyError):
            return False  # Assume doesn't exist on any error
