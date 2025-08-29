"""HRID generator and parser for MEMG Core.

Format: {TYPE_UPPER}_{AAA000}
- TYPE: uppercase alphanumeric type name (no spaces)
- AAA: base26 letters A–Z (wraps after ZZZ)
- 000–999: numeric suffix
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from ..core.exceptions import DatabaseError
from ..core.logging import get_logger

# Matches HRIDs like TASK_AAA001, NOTE_ZZZ999
_HRID_RE = re.compile(r"^(?P<type>[A-Z0-9_]+)_(?P<alpha>[A-Z]{3})(?P<num>\d{3})$")

# Monotonic counters per type (in-memory; persistent store should be used in production)
_COUNTERS: dict[tuple[str, str], tuple[int, int]] = {}  # {(type, user_id): (alpha_idx, num)}


class StorageQueryInterface(Protocol):
    """Protocol for storage backends that can query for existing HRIDs.

    Attributes:
        vector: Query embedding vector.
        limit: Maximum number of results.
        collection: Optional collection name.
        user_id: User ID for filtering.
        filters: Additional search filters.
    """

    def search_points(
        self,
        vector: list[float],
        limit: int = 5,
        collection: str | None = None,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for points with optional filtering.

        Args:
            vector: Query embedding vector.
            limit: Maximum number of results.
            collection: Optional collection name.
            user_id: User ID for filtering.
            filters: Additional search filters.

        Returns:
            list[dict[str, Any]]: List of search results.
        """
        raise NotImplementedError("Subclasses must implement search_points method")


def _alpha_to_idx(alpha: str) -> int:
    """Convert alpha string to index: AAA -> 0, AAB -> 1, ..., ZZZ -> 17575.

    Args:
        alpha: Three-letter alpha string (AAA-ZZZ).

    Returns:
        int: Numeric index.
    """
    idx = 0
    for char in alpha:
        idx = idx * 26 + (ord(char) - ord("A"))
    return idx


def _idx_to_alpha(idx: int) -> str:
    """Convert index to alpha string: 0 -> AAA, 1 -> AAB, ..., 17575 -> ZZZ.

    Args:
        idx: Numeric index (0-17575).

    Returns:
        str: Three-letter alpha string.
    """
    chars = []
    for _ in range(3):
        chars.append(chr(ord("A") + idx % 26))
        idx //= 26
    return "".join(reversed(chars))


def _initialize_counter_from_storage(
    type_name: str, user_id: str, storage: StorageQueryInterface | None = None
) -> tuple[int, int]:
    """Initialize counter by querying storage for highest existing HRID of this type.

    Args:
        type_name: The memory type to check (e.g., 'note', 'task')
        user_id: User ID for scoped HRID lookup
        storage: Storage interface to query for existing HRIDs

    Returns:
        tuple[int, int]: (alpha_idx, num) representing the next available counter position

    Notes:
        - If no storage provided or no existing HRIDs found, returns (0, -1) for fresh start
        - Queries storage for memories of the given type and finds the highest HRID
        - Parses the highest HRID to determine the next counter position
    """
    if not storage:
        return (0, -1)  # Fresh start if no storage interface

    try:
        # Query storage for memories of this type, with high limit to catch all
        # We use a dummy vector since we're filtering by memory_type, not doing vector search
        dummy_vector = [0.0] * 384  # Default embedding size

        # Search with memory_type and user_id filters to get all memories of this type for this user
        results = storage.search_points(
            vector=dummy_vector,
            limit=10000,  # High limit to get all existing memories of this type
            filters={
                "user_id": user_id,  # CRITICAL: Include user_id for proper isolation
                "memory_type": type_name.lower(),
            },
        )

        if not results:
            return (0, -1)  # No existing memories of this type

        # Find the highest HRID among results
        highest_hrid = None
        highest_alpha_idx = -1
        highest_num = -1

        for result in results:
            payload = result.get("payload", {})
            # Updated for flat payload structure
            hrid = payload.get("hrid")

            if not hrid or not isinstance(hrid, str):
                continue

            try:
                parsed_type, alpha, num = parse_hrid(hrid)
                if parsed_type.upper() != type_name.upper():
                    continue  # Skip HRIDs of different types

                alpha_idx = _alpha_to_idx(alpha)

                # Check if this is the highest HRID so far
                if alpha_idx > highest_alpha_idx or (
                    alpha_idx == highest_alpha_idx and num > highest_num
                ):
                    highest_alpha_idx = alpha_idx
                    highest_num = num
                    highest_hrid = hrid

            except ValueError as e:
                # Skip invalid HRIDs but log for transparency
                logger = get_logger("hrid")
                logger.debug(f"Skipping invalid HRID format '{hrid}': {e}")
                continue

        if highest_hrid is None:
            return (0, -1)  # No valid HRIDs found

        # Return the next position after the highest found
        next_num = highest_num + 1
        if next_num > 999:
            next_num = 0
            highest_alpha_idx += 1

        return (
            highest_alpha_idx,
            next_num - 1,
        )  # -1 because generate_hrid will increment

    except (DatabaseError, ConnectionError, TimeoutError) as e:
        # If storage query fails, fall back to fresh start but log the issue
        logger = get_logger("hrid")
        logger.warning(f"HRID storage query failed, falling back to fresh start: {e}")
        return (0, -1)


def _initialize_counter_from_tracker(type_name: str, user_id: str, hrid_tracker) -> tuple[int, int]:
    """Initialize counter by querying HridTracker for highest existing HRID.

    Args:
        type_name: The memory type to check (e.g., 'note', 'task')
        user_id: User ID for scoped HRID lookup
        hrid_tracker: HridTracker instance to query

    Returns:
        tuple[int, int]: (alpha_idx, num) representing the next available counter position
    """
    try:
        highest = hrid_tracker.get_highest_hrid(type_name, user_id)

        if highest is None:
            return (0, -1)  # No existing HRIDs for this type

        _highest_hrid, highest_alpha_idx, highest_num = highest

        # Return the next position after the highest found
        next_num = highest_num + 1
        if next_num > 999:
            next_num = 0
            highest_alpha_idx += 1

        return (
            highest_alpha_idx,
            next_num - 1,
        )  # -1 because generate_hrid will increment

    except Exception as e:
        # DO NOT FALL BACK SILENTLY - this causes duplicate HRID bugs!
        # If we can't initialize from existing data, the system should fail fast
        raise DatabaseError(
            f"Failed to initialize HRID counter for type '{type_name}' from existing data. "
            f"This is critical - cannot generate HRIDs without knowing existing ones.",
            operation="initialize_counter_from_tracker",
            context={"type_name": type_name},
            original_error=e,
        ) from e


def generate_hrid(type_name: str, user_id: str, hrid_tracker=None) -> str:
    """Generate the next HRID for the given type.

    Args:
        type_name: The memory type (e.g., 'note', 'task').
        user_id: User ID for scoped HRID generation.
        hrid_tracker: Optional HridTracker instance for querying existing HRIDs.

    Returns:
        str: The next HRID in format TYPE_AAA000.

    Notes:
        - Uses HridTracker to query HridMapping table for existing HRIDs.
        - Falls back to in-memory counter if no tracker provided.
        - Ensures no duplicates by checking complete HRID history.
    """
    t = type_name.strip().upper()

    # Initialize counter from HridTracker on first use of this type+user combination
    counter_key = (t, user_id)
    if counter_key not in _COUNTERS and hrid_tracker is not None:
        _COUNTERS[counter_key] = _initialize_counter_from_tracker(t, user_id, hrid_tracker)

    # Get current counter or default to fresh start
    alpha_idx, num = _COUNTERS.get(counter_key, (0, -1))
    num += 1
    if num > 999:
        num = 0
        alpha_idx += 1
        if alpha_idx > 26**3 - 1:
            raise ValueError(f"HRID space exhausted for type {t}")
    _COUNTERS[counter_key] = (alpha_idx, num)
    return f"{t}_{_idx_to_alpha(alpha_idx)}{num:03d}"


def parse_hrid(hrid: str) -> tuple[str, str, int]:
    """Parse HRID into (type, alpha, num).

    Args:
        hrid: HRID string to parse.

    Returns:
        tuple[str, str, int]: (type, alpha, num) components.

    Raises:
        ValueError: If HRID format is invalid.
    """
    m = _HRID_RE.match(hrid.strip().upper())
    if not m:
        raise ValueError(f"Invalid HRID format: {hrid}")
    return m.group("type"), m.group("alpha"), int(m.group("num"))


def _type_key(t: str) -> int:
    """
    Deterministic numeric key for type names to enable cross-type ordering.
    Encodes up to the first 8 chars in base-37 (A–Z=1–26, 0–9=27–36).
    """
    t = t.upper()
    key = 0
    for c in t[:8]:
        if "A" <= c <= "Z":
            v = 1 + (ord(c) - ord("A"))
        elif "0" <= c <= "9":
            v = 27 + (ord(c) - ord("0"))
        else:
            v = 0
        key = key * 37 + v
    return key


def hrid_to_index(hrid: str) -> int:
    """Convert HRID into a single integer index for ordering across types.

    Args:
        hrid: HRID string to convert.

    Returns:
        int: Single integer index for cross-type ordering.
    """
    type_, alpha, num = parse_hrid(hrid)
    intra = _alpha_to_idx(alpha) * 1000 + num  # 0 .. 17,575,999  (needs 25 bits)
    return (_type_key(type_) << 25) | intra


def reset_counters():
    """Reset all in-memory HRID counters.

    This is used for testing to simulate system restarts.
    In production, counters are automatically initialized from database.
    """
    global _COUNTERS
    _COUNTERS.clear()
