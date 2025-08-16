"""
HRID generator and parser for MEMG Core.

Format: {TYPE_UPPER}_{AAA000}
- TYPE: uppercase alphanumeric type name (no spaces)
- AAA: base26 letters A–Z (wraps after ZZZ)
- 000–999: numeric suffix
"""

from __future__ import annotations

import re
from typing import Any, Protocol

# Matches HRIDs like TASK_AAA001, NOTE_ZZZ999
_HRID_RE = re.compile(r"^(?P<type>[A-Z0-9_]+)_(?P<alpha>[A-Z]{3})(?P<num>\d{3})$")

# Monotonic counters per type (in-memory; persistent store should be used in production)
_COUNTERS: dict[str, tuple[int, int]] = {}  # {type: (alpha_idx, num)}


class StorageQueryInterface(Protocol):
    """Protocol for storage backends that can query for existing HRIDs."""

    def search_points(
        self,
        vector: list[float],
        limit: int = 5,
        collection: str | None = None,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for points with optional filtering."""
        ...


def _alpha_to_idx(alpha: str) -> int:
    """AAA -> 0, AAB -> 1, ..., ZZZ -> 17575."""
    idx = 0
    for char in alpha:
        idx = idx * 26 + (ord(char) - ord("A"))
    return idx


def _idx_to_alpha(idx: int) -> str:
    """0 -> AAA, 1 -> AAB, ..., 17575 -> ZZZ."""
    chars = []
    for _ in range(3):
        chars.append(chr(ord("A") + idx % 26))
        idx //= 26
    return "".join(reversed(chars))


def _initialize_counter_from_storage(
    type_name: str, storage: StorageQueryInterface | None = None
) -> tuple[int, int]:
    """Initialize counter by querying storage for highest existing HRID of this type.

    Args:
        type_name: The memory type to check (e.g., 'note', 'task')
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

        # Search with memory_type filter to get all memories of this type
        results = storage.search_points(
            vector=dummy_vector,
            limit=10000,  # High limit to get all existing memories of this type
            filters={"core.memory_type": type_name.lower()},
        )

        if not results:
            return (0, -1)  # No existing memories of this type

        # Find the highest HRID among results
        highest_hrid = None
        highest_alpha_idx = -1
        highest_num = -1

        for result in results:
            payload = result.get("payload", {})
            core = payload.get("core", {})
            hrid = core.get("hrid")

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
                from ..core.logging import get_logger

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

        return (highest_alpha_idx, next_num - 1)  # -1 because generate_hrid will increment

    except Exception as e:
        # If storage query fails, fall back to fresh start but log the issue
        from ..core.logging import get_logger

        logger = get_logger("hrid")
        logger.warning(f"HRID storage query failed, falling back to fresh start: {e}")
        return (0, -1)


def generate_hrid(type_name: str, storage: StorageQueryInterface | None = None) -> str:
    """Generate the next HRID for the given type.

    Args:
        type_name: The memory type (e.g., 'note', 'task')
        storage: Optional storage interface to query for existing HRIDs

    Returns:
        str: The next HRID in format TYPE_AAA000

    Notes:
        - On first call per type, initializes counter from storage if provided
        - Subsequent calls use cached in-memory counter for performance
        - Falls back to fresh counter if storage query fails
    """
    t = type_name.strip().upper()

    # Initialize counter from storage on first use of this type
    if t not in _COUNTERS and storage is not None:
        _COUNTERS[t] = _initialize_counter_from_storage(t, storage)

    # Get current counter or default to fresh start
    alpha_idx, num = _COUNTERS.get(t, (0, -1))
    num += 1
    if num > 999:
        num = 0
        alpha_idx += 1
        if alpha_idx > 26**3 - 1:
            raise ValueError(f"HRID space exhausted for type {t}")
    _COUNTERS[t] = (alpha_idx, num)
    return f"{t}_{_idx_to_alpha(alpha_idx)}{num:03d}"


def parse_hrid(hrid: str) -> tuple[str, str, int]:
    """Parse HRID into (type, alpha, num)."""
    m = _HRID_RE.match(hrid.strip().upper())
    if not m:
        raise ValueError(f"Invalid HRID format: {hrid}")
    return m.group("type"), m.group("alpha"), int(m.group("num"))


def reset_counters() -> None:
    """Reset in-memory counters (mainly for testing)."""
    _COUNTERS.clear()


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
    """Convert HRID into a single integer index for ordering across types."""
    type_, alpha, num = parse_hrid(hrid)
    intra = _alpha_to_idx(alpha) * 1000 + num  # 0 .. 17,575,999  (needs 25 bits)
    return (_type_key(type_) << 25) | intra
