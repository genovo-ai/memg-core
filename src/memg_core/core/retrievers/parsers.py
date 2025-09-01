"""Memory parsing and projection utilities."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ...utils.hrid import hrid_to_index
from ..models import Memory, SearchResult
from ..yaml_translator import YamlTranslator


def _project_payload(
    memory_type: str,
    payload: dict[str, Any],
    *,
    include_details: str,
    projection: dict[str, list[str]] | None = None,
    yaml_translator: YamlTranslator | None = None,
) -> dict[str, Any]:
    """Project payload based on include_details setting and optional projection.

    Args:
        memory_type: Entity type for YAML anchor field lookup.
        payload: Original payload dict.
        include_details: "none" (anchor only) or "self" (full payload).
        projection: Optional per-type field allowlist.
        yaml_translator: YAML translator instance.

    Returns:
        dict[str, Any]: Projected payload dict with anchor field always included.
    """
    if not payload:
        return {}

    # Get anchor field from YAML schema - crash if missing
    if not yaml_translator:
        yaml_translator = YamlTranslator()
    anchor_field = yaml_translator.get_anchor_field(memory_type)

    if include_details == "none":
        # Return only anchor field - crash if missing
        return {anchor_field: payload[anchor_field]}

    # include_details == "self" - apply projection if provided
    result_payload = dict(payload)

    # Apply projection filtering if provided
    if projection and memory_type in projection:
        allowed_fields = set(projection[memory_type])
        # Always include anchor field
        allowed_fields.add(anchor_field)
        result_payload = {k: v for k, v in result_payload.items() if k in allowed_fields}

    return result_payload


def _dedupe_and_sort(results: list[SearchResult]) -> list[SearchResult]:
    """Merge results by ID, keep highest score, then sort deterministically.

    Sort order: score DESC, then hrid index ASC, then id ASC.

    Args:
        results: List of search results to deduplicate and sort.

    Returns:
        list[SearchResult]: Deduplicated and sorted results.
    """
    # Dedupe by memory ID, keeping highest score
    by_id: dict[str, SearchResult] = {}
    for result in results:
        memory_id = result.memory.id
        if memory_id not in by_id or result.score > by_id[memory_id].score:
            by_id[memory_id] = result

    # Sort deterministically
    deduped = list(by_id.values())
    deduped.sort(key=_sort_key)
    return deduped


def _sort_key(result: SearchResult) -> tuple:
    """Stable ordering: score DESC, then hrid index ASC, then id ASC.

    Args:
        result: Search result to generate sort key for.

    Returns:
        tuple: Sort key components.
    """
    memory = result.memory
    hrid = getattr(memory, "hrid", None) or "ZZZ_ZZZ999"

    # Handle case where hrid is actually a UUID (fallback for compatibility)
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    if uuid_pattern.match(hrid):
        # Use a high index for UUIDs to sort them after proper HRIDs
        idx = 999999999
    else:
        # Parse HRID index. Raises ValueError if format is invalid,
        # intentionally crashing to expose data quality issues early.
        idx = hrid_to_index(hrid)

    return (-float(result.score), idx, memory.id)


def _parse_datetime(date_str: str) -> datetime:
    """Parse datetime string - crash if invalid.

    Args:
        date_str: ISO format datetime string.

    Returns:
        datetime: Parsed datetime object.

    Raises:
        ValueError: If datetime string is invalid.
    """
    return datetime.fromisoformat(date_str)


# System fields that are stored flat in Qdrant but should be separated from entity payload
SYSTEM_FIELD_NAMES = {
    "user_id",
    "memory_type",
    "created_at",
    "updated_at",
    "id",
    "hrid",
}


def build_memory_from_flat_payload(
    point_id: str, payload: dict[str, Any], hrid_tracker=None
) -> Memory:
    """Build Memory object from flat Qdrant payload.

    Args:
        point_id: Point ID from Qdrant (UUID).
        payload: Flat payload from Qdrant.
        hrid_tracker: Optional HridTracker for UUID→HRID translation.

    Returns:
        Memory: Memory object with proper field separation.
    """
    # Get HRID from tracker if available (extract user_id from payload)
    user_id = payload.get("user_id", "")
    memory_hrid = hrid_tracker.get_hrid(point_id, user_id) if hrid_tracker else None

    # Extract entity fields (everything except system fields)
    entity_fields = {k: v for k, v in payload.items() if k not in SYSTEM_FIELD_NAMES}

    # Build Memory object with proper ID separation
    return Memory(
        id=point_id,  # Always UUID for internal operations
        user_id=payload.get("user_id") or "",  # Ensure string type
        memory_type=payload.get("memory_type") or "",  # Ensure string type
        payload=entity_fields,
        created_at=(
            _parse_datetime(payload["created_at"]) if payload.get("created_at") else datetime.now()
        ),
        updated_at=(
            _parse_datetime(payload["updated_at"]) if payload.get("updated_at") else datetime.now()
        ),
        hrid=memory_hrid,  # HRID for external API
    )


def build_memory_from_kuzu_row(row: dict[str, Any], hrid_tracker=None) -> Memory:
    """Build Memory object from Kuzu row data.

    Args:
        row: Row data from Kuzu query result.
        hrid_tracker: Optional HridTracker for UUID→HRID translation.

    Returns:
        Memory: Memory object with proper field separation.

    Note:
        This handles the complex Kuzu row format that can have nested node objects.
    """
    # Extract neighbor memory from row - handle both formats
    neighbor_id = row["id"]

    # Handle both node object and flat row formats
    if "node" in row:
        node_data = row["node"]
        if hasattr(node_data, "__dict__"):
            node_data = node_data.__dict__
        elif not isinstance(node_data, dict):
            node_data = {}
    else:
        node_data = row

    # Get HRID from tracker if available (extract user_id from node_data)
    user_id_for_hrid = node_data.get("user_id", "")
    memory_hrid = hrid_tracker.get_hrid(neighbor_id, user_id_for_hrid) if hrid_tracker else None

    # Extract system fields with fallback logic
    user_id = node_data.get("user_id") or row.get("user_id")
    memory_type = node_data.get("memory_type") or row.get("memory_type")
    created_at_str = node_data.get("created_at") or row.get("created_at")
    updated_at_str = node_data.get("updated_at") or row.get("updated_at")

    # Create entity payload by excluding system fields
    entity_payload = {k: v for k, v in node_data.items() if k not in SYSTEM_FIELD_NAMES}

    # Build Memory object with proper ID separation
    return Memory(
        id=neighbor_id,  # Always UUID for internal operations
        user_id=user_id or "",  # Ensure string type
        memory_type=memory_type or "",  # Ensure string type
        payload=entity_payload,
        created_at=(_parse_datetime(created_at_str) if created_at_str else datetime.now()),
        updated_at=(_parse_datetime(updated_at_str) if updated_at_str else datetime.now()),
        hrid=memory_hrid,  # HRID for external API
    )
