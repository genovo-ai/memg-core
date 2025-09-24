"""Clean GraphRAG retrieval pipelines - vector seeds → graph expansion → semantic enhancement.

True GraphRAG architecture:
1. Query → Qdrant vector search → seeds (full payloads)
2. Seeds → Kuzu graph expansion → neighbors (anchor-only payloads)
3. Optional semantic expansion using seed anchor text
4. Dedupe by ID, deterministic sorting

NO modes, NO fallbacks, NO backward compatibility.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from ...core.exceptions import DatabaseError
from ...utils.db_clients import DatabaseClients
from ...utils.hrid_tracker import HridTracker
from ...utils.scoring import calculate_neighbor_relevance
from ..config import get_config
from ..models import Memory, MemoryNeighbor, MemorySeed, RelationshipInfo, SearchResult
from ..yaml_translator import YamlTranslator

# System fields that are stored flat in Qdrant but should be separated from entity payload
SYSTEM_FIELD_NAMES = {
    "user_id",
    "memory_type",
    "created_at",
    "updated_at",
    "id",
    "hrid",
}

# Internal database fields that should never be exposed to users
INTERNAL_DB_FIELDS = {
    "_id",
    "_label",
    "vector",
}


class PayloadProjector:
    """Handles payload projection and filtering based on include_details and projection settings."""

    def __init__(self, yaml_translator: YamlTranslator):
        """Initialize with YAML translator for anchor field lookup.

        Args:
            yaml_translator: YAML translator instance for schema operations.
        """
        self.yaml_translator = yaml_translator

    def project(
        self,
        memory_type: str,
        payload: dict[str, Any],
        *,
        include_details: str,
        projection: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """Project payload based on include_details setting and optional projection.

        Args:
            memory_type: Entity type for YAML schema lookup.
            payload: Original payload dict.
            include_details: "none" (display field only), "self" (full payload for seeds), or "all" (full payload for both seeds and neighbors).
            projection: Optional per-type field allowlist.

        Returns:
            dict[str, Any]: Projected payload dict with display field always included (defaults to anchor field).
        """
        if not payload:
            return {}

        # Get anchor field from YAML schema - crash if missing
        anchor_field = self.yaml_translator.get_anchor_field(memory_type)

        # Get override field lists from YAML schema (not from payload)
        force_display_fields = self.yaml_translator.get_force_display_fields(memory_type)
        exclude_display_fields = self.yaml_translator.get_exclude_display_fields(memory_type)

        # Get display field from YAML (defaults to anchor_field if not overridden)
        display_field = self.yaml_translator.get_display_field_name(memory_type)
        if not display_field:
            display_field = anchor_field

        if include_details == "none":
            # Show only the display field (which is anchor_field by default)
            result = {display_field: payload[display_field]} if display_field in payload else {}
        else:
            # include_details in ["self", "all"] - show all fields except internal DB fields
            result = {k: v for k, v in payload.items() if k not in INTERNAL_DB_FIELDS}

            # Apply projection filtering if provided
            if projection and memory_type in projection:
                allowed_fields = set(projection[memory_type])
                # Always include display field
                allowed_fields.add(display_field)
                result = {k: v for k, v in result.items() if k in allowed_fields}

        # Apply force_display: add any fields from the force list that exist in payload (except internal DB fields)
        for field_name in force_display_fields:
            if field_name in payload and field_name not in INTERNAL_DB_FIELDS:
                result[field_name] = payload[field_name]

        # Apply exclude_display: remove any fields from the exclude list
        for field_name in exclude_display_fields:
            result.pop(field_name, None)

        # Always ensure display field is present (unless explicitly excluded or internal DB field)
        if (
            display_field not in exclude_display_fields
            and display_field in payload
            and display_field not in INTERNAL_DB_FIELDS
        ):
            result[display_field] = payload[display_field]

        return result


class MemorySerializer:
    """Centralized memory serialization - handles packing/unpacking for all storage formats."""

    def __init__(self, hrid_tracker: HridTracker):
        """Initialize with HRID tracker for UUID↔HRID translation.

        Args:
            hrid_tracker: HRID tracker instance for ID management.
        """
        self.hrid_tracker = hrid_tracker

    def to_qdrant_payload(self, memory: Memory, hrid: str) -> dict[str, Any]:
        """Pack Memory object into flat Qdrant payload format.

        Args:
            memory: Memory object to serialize.
            hrid: Human-readable ID for the memory.

        Returns:
            dict[str, Any]: Flat payload for Qdrant storage with system + entity fields.
        """
        return {
            "user_id": memory.user_id,  # Required for user filtering
            "memory_type": memory.memory_type,  # Required for type filtering
            "created_at": memory.created_at.isoformat()
            if memory.created_at
            else datetime.now(UTC).isoformat(),  # Required for time filtering
            "updated_at": memory.updated_at.isoformat()
            if memory.updated_at
            else datetime.now(UTC).isoformat(),  # Required for time filtering
            "hrid": hrid,  # Include HRID for user-facing operations
            **memory.payload,  # Include all YAML-validated entity fields
        }

    def to_kuzu_data(self, memory: Memory) -> dict[str, Any]:
        """Pack Memory object into Kuzu node data format.

        Args:
            memory: Memory object to serialize.

        Returns:
            dict[str, Any]: Node data for Kuzu storage with system + entity fields.
        """
        return {
            "id": memory.id,
            "user_id": memory.user_id,
            "memory_type": memory.memory_type,
            "created_at": memory.created_at.isoformat()
            if memory.created_at
            else datetime.now(UTC).isoformat(),
            "updated_at": memory.updated_at.isoformat()
            if memory.updated_at
            else datetime.now(UTC).isoformat(),
            **memory.payload,  # Include all YAML-validated fields
        }

    def from_qdrant_point(self, point_id: str, payload: dict[str, Any]) -> Memory:
        """Build Memory object from flat Qdrant payload.

        Args:
            point_id: Point ID from Qdrant (UUID).
            payload: Flat payload from Qdrant.

        Returns:
            Memory: Memory object with proper field separation.
        """
        # Get HRID from tracker if available (extract user_id from payload)
        user_id = payload.get("user_id", "")
        memory_hrid = self.hrid_tracker.get_hrid(point_id, user_id)

        # Extract entity fields (everything except system fields)
        entity_fields = {k: v for k, v in payload.items() if k not in SYSTEM_FIELD_NAMES}

        # Build Memory object with proper ID separation
        return Memory(
            id=point_id,  # Always UUID for internal operations
            user_id=payload.get("user_id") or "",  # Ensure string type
            memory_type=payload.get("memory_type") or "",  # Ensure string type
            payload=entity_fields,
            created_at=(
                _parse_datetime(payload["created_at"])
                if payload.get("created_at")
                else datetime.now()
            ),
            updated_at=(
                _parse_datetime(payload["updated_at"])
                if payload.get("updated_at")
                else datetime.now()
            ),
            hrid=memory_hrid,  # HRID for external API
        )

    def from_kuzu_row(self, row: dict[str, Any]) -> Memory:
        """Build Memory object from Kuzu row data.

        Args:
            row: Row data from Kuzu query result.

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
        memory_hrid = self.hrid_tracker.get_hrid(neighbor_id, user_id_for_hrid)

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

    def to_memory_seed(
        self, memory: Memory, score: float, datetime_format: str | None = None
    ) -> MemorySeed:
        """Convert Memory object to MemorySeed.

        Args:
            memory: Memory object to convert.
            score: Relevance score for this seed.
            datetime_format: Optional datetime format string for timestamps.

        Returns:
            MemorySeed: Seed object for search results.
        """
        # Format datetime fields if custom format is provided
        created_at = memory.created_at
        updated_at = memory.updated_at

        if datetime_format:
            # Convert datetime objects to formatted strings
            created_at_str = _format_datetime(memory.created_at, datetime_format)
            updated_at_str = (
                _format_datetime(memory.updated_at, datetime_format) if memory.updated_at else None
            )

            # Create a modified payload with formatted timestamps
            formatted_payload = dict(memory.payload)
            formatted_payload["created_at"] = created_at_str
            if updated_at_str:
                formatted_payload["updated_at"] = updated_at_str

            return MemorySeed(
                user_id=memory.user_id,
                hrid=memory.hrid or memory.id,
                memory_type=memory.memory_type,
                created_at=created_at_str,  # Use formatted string
                updated_at=updated_at_str,  # Use formatted string
                payload=formatted_payload,
                score=score,
                relationships=[],  # Will be populated by graph expansion
            )

        return MemorySeed(
            user_id=memory.user_id,
            hrid=memory.hrid or memory.id,
            memory_type=memory.memory_type,
            created_at=created_at,
            updated_at=updated_at,
            payload=memory.payload,
            score=score,
            relationships=[],  # Will be populated by graph expansion
        )

    def to_memory_neighbor(
        self, memory: Memory, score: float, datetime_format: str | None = None
    ) -> MemoryNeighbor:
        """Convert Memory object to MemoryNeighbor.

        Args:
            memory: Memory object to convert.
            score: Relevance score for this neighbor.
            datetime_format: Optional datetime format string for timestamps.

        Returns:
            MemoryNeighbor: Neighbor object for search results.
        """
        # Format datetime fields if custom format is provided
        created_at = memory.created_at
        updated_at = memory.updated_at

        if datetime_format:
            # Convert datetime objects to formatted strings
            created_at_str = _format_datetime(memory.created_at, datetime_format)
            updated_at_str = (
                _format_datetime(memory.updated_at, datetime_format) if memory.updated_at else None
            )

            # Create a modified payload with formatted timestamps
            formatted_payload = dict(memory.payload)
            formatted_payload["created_at"] = created_at_str
            if updated_at_str:
                formatted_payload["updated_at"] = updated_at_str

            return MemoryNeighbor(
                user_id=memory.user_id,
                hrid=memory.hrid or memory.id,
                memory_type=memory.memory_type,
                created_at=created_at_str,  # Use formatted string
                updated_at=updated_at_str,  # Use formatted string
                payload=formatted_payload,
                score=score,
            )

        return MemoryNeighbor(
            user_id=memory.user_id,
            hrid=memory.hrid or memory.id,
            memory_type=memory.memory_type,
            created_at=created_at,
            updated_at=updated_at,
            payload=memory.payload,  # Should already be projected
            score=score,
        )


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


def _format_datetime(dt: datetime, format_string: str | None = None) -> str:
    """Format datetime object to string using specified format.

    Args:
        dt: Datetime object to format.
        format_string: Format string (e.g., "%Y-%m-%d %H:%M:%S"). If None, uses ISO format.

    Returns:
        str: Formatted datetime string.
    """
    if format_string is None:
        return dt.isoformat()

    try:
        return dt.strftime(format_string)
    except (ValueError, TypeError):
        # Fall back to ISO format if custom format fails
        return dt.isoformat()


class VectorSearchHandler:
    """Handles Qdrant vector search operations and seed generation."""

    def __init__(
        self,
        qdrant,
        embedder,
        memory_serializer: MemorySerializer,
        payload_projector: PayloadProjector,
    ):
        """Initialize with required interfaces and utilities.

        Args:
            qdrant: Qdrant interface for vector operations.
            embedder: Embedder for query vectorization.
            memory_serializer: MemorySerializer utility for object construction.
            payload_projector: PayloadProjector utility for payload filtering.
        """
        self.qdrant = qdrant
        self.embedder = embedder
        self.memory_serializer = memory_serializer
        self.payload_projector = payload_projector

    def search_seeds(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        *,
        memory_type: str | None = None,
        modified_within_days: int | None = None,
        filters: dict[str, Any] | None = None,
        projection: dict[str, list[str]] | None = None,
        score_threshold: float | None = None,
        include_details: str = "self",
        datetime_format: str | None = None,
    ) -> list[MemorySeed]:
        """Search for vector seeds using Qdrant.

        Args:
            query: Search query text.
            user_id: User ID for filtering.
            limit: Maximum results to return.
            memory_type: Optional memory type filter.
            modified_within_days: Filter by recency.
            filters: Custom field-based filtering.
            projection: Control which fields to return per memory type.
            score_threshold: Minimum similarity score threshold.
            include_details: "self" (full payload) or "none" (anchor only).

        Returns:
            list[MemorySeed]: Vector search seeds with projected payloads.
        """
        if not query or not query.strip():
            return []

        # Generate query vector
        query_vector = self.embedder.get_embedding(query)

        # Build filters for Qdrant
        qdrant_filters = self._build_qdrant_filters(
            user_id=user_id,
            memory_type=memory_type,
            modified_within_days=modified_within_days,
            extra_filters=filters,
        )

        # Search Qdrant for vector seeds
        vector_points = self.qdrant.search_points(
            vector=query_vector,
            limit=limit,
            filters=qdrant_filters,
            score_threshold=score_threshold,
        )

        # Convert Qdrant points to MemorySeeds
        seeds: list[MemorySeed] = []
        for point in vector_points:
            payload = point["payload"]
            point_id = point["id"]

            # Build Memory object
            memory = self.memory_serializer.from_qdrant_point(point_id, payload)

            # Project payload based on include_details and projection
            memory.payload = self.payload_projector.project(
                memory.memory_type,
                memory.payload,
                include_details=include_details,
                projection=projection,
            )

            # Convert to MemorySeed
            seed_result = self.memory_serializer.to_memory_seed(
                memory, float(point["score"]), datetime_format
            )
            seeds.append(seed_result)

        return seeds

    def _build_qdrant_filters(
        self,
        user_id: str,
        memory_type: str | None,
        modified_within_days: int | None,
        extra_filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build Qdrant filters from parameters with mandatory user isolation.

        Args:
            user_id: User ID for filtering (CRITICAL: included in filters dict).
            memory_type: Optional memory type filter.
            modified_within_days: Filter by recency (days).
            extra_filters: Additional custom filters.

        Returns:
            dict[str, Any]: Combined filters dictionary for Qdrant with user_id always included.

        Note:
            user_id is now included in filters dict for security validation.
        """
        # CRITICAL SECURITY: Always start with user_id
        filters: dict[str, Any] = {"user_id": user_id}

        # Add extra filters (user_id will be overridden if present, which is fine)
        if extra_filters:
            filters.update(extra_filters)

        # memory_type filter - use flat structure
        if memory_type:
            filters["memory_type"] = memory_type

        # Time-based filtering - use flat structure
        if modified_within_days and modified_within_days > 0:
            cutoff_date = datetime.now(UTC) - timedelta(days=modified_within_days)
            filters["updated_at_from"] = cutoff_date.isoformat()

        return filters


class GraphExpansionHandler:
    """Handles Kuzu graph traversal and neighbor expansion."""

    def __init__(
        self,
        kuzu,
        embedder,
        yaml_translator,
        memory_serializer: MemorySerializer,
        payload_projector: PayloadProjector,
        hrid_tracker,
    ):
        """Initialize with required interfaces and utilities.

        Args:
            kuzu: Kuzu interface for graph operations.
            embedder: Embedder for neighbor relevance scoring.
            yaml_translator: YAML translator for anchor field lookup.
            memory_serializer: MemorySerializer utility for object construction.
            payload_projector: PayloadProjector utility for payload filtering.
            hrid_tracker: HRID tracker for UUID↔HRID translation.
        """
        self.kuzu = kuzu
        self.embedder = embedder
        self.yaml_translator = yaml_translator
        self.memory_serializer = memory_serializer
        self.payload_projector = payload_projector
        self.hrid_tracker = hrid_tracker

    def expand_neighbors(
        self,
        seeds: list[MemorySeed],
        user_id: str,
        relation_names: list[str] | None,
        neighbor_limit: int,
        hops: int = 1,
        projection: dict[str, list[str]] | None = None,
        neighbor_threshold: float | None = None,
        include_details: str = "self",
        datetime_format: str | None = None,
    ) -> list[MemoryNeighbor]:
        """Expand neighbors from Kuzu graph with progressive score decay.

        Args:
            seeds: Initial seed results from vector search.
            user_id: User ID for isolation.
            relation_names: Specific relation types to expand (None = all relations).
            neighbor_limit: Max neighbors per seed.
            hops: Number of hops to expand (progressive score decay).
            projection: Optional field projection.
            neighbor_threshold: Minimum score threshold for neighbors (None = no filtering).
            include_details: Detail level for neighbor payloads ("self" = anchor only, "all" = full payload).

        Returns:
            list[MemoryNeighbor]: Neighbors with payloads based on include_details setting and populated seed relationships.
        """
        all_neighbors: list[MemoryNeighbor] = []  # Collect all neighbors
        current_hop_seeds = seeds
        original_seeds = seeds  # Keep reference to original seeds for relationship tree building

        # Track all seed HRIDs to prevent them from appearing in neighbors
        seed_hrids = {seed.hrid for seed in seeds}

        for _ in range(hops):
            next_hop_results: list[MemoryNeighbor] = []
            # Track processed nodes per hop to avoid cycles within the same hop
            hop_processed_ids: set[str] = set()

            for seed in current_hop_seeds:
                # Get UUID from HRID for Kuzu queries
                seed_uuid = self.hrid_tracker.get_uuid(seed.hrid, user_id)
                if not seed_uuid or seed_uuid in hop_processed_ids:
                    continue

                hop_processed_ids.add(seed_uuid)

                # Schema-driven predicate filtering: only query predicates valid for this entity type
                if relation_names is None:
                    # Get predicates that this entity type can actually participate in from YAML schema
                    relations = self.yaml_translator.get_relations_for_source(seed.memory_type)
                    schema_filtered_predicates = [rel["predicate"] for rel in relations]

                    if not schema_filtered_predicates:
                        # No relationships defined for this entity type in YAML - skip
                        continue
                else:
                    schema_filtered_predicates = relation_names

                # Get neighbors from Kuzu - using Memory table with schema-driven predicates
                neighbor_rows = self.kuzu.neighbors(
                    node_label=seed.memory_type,  # Memory type for filtering
                    node_uuid=seed_uuid,  # Use UUID for Kuzu queries
                    user_id=user_id,  # CRITICAL: User isolation
                    rel_types=schema_filtered_predicates,  # Schema-filtered predicates only
                    direction="any",
                    limit=neighbor_limit,
                    neighbor_label=None,  # Accept neighbors from any entity table
                )

                for row in neighbor_rows:
                    # Extract neighbor memory from row
                    neighbor_id = row["id"]
                    if not neighbor_id or neighbor_id in hop_processed_ids:
                        continue

                    # Get full entity data from specific entity table
                    neighbor_memory_type = row["memory_type"]
                    entity_rows = self.kuzu.get_nodes(
                        user_id=user_id,
                        node_type=neighbor_memory_type,
                        filters={"id": neighbor_id},
                        limit=1,
                    )

                    if not entity_rows:
                        # Entity not found in specific table - skip
                        continue

                    # Build neighbor Memory object using full entity data
                    neighbor_memory = self.memory_serializer.from_kuzu_row(entity_rows[0])

                    # Project payload based on include_details setting
                    # For neighbors: "self" means anchor-only, "all" means full payload
                    neighbor_detail_level = "none" if include_details == "self" else include_details
                    neighbor_memory.payload = self.payload_projector.project(
                        neighbor_memory.memory_type,
                        neighbor_memory.payload,
                        include_details=neighbor_detail_level,
                        projection=projection,
                    )

                    # Calculate recursive relevance score
                    neighbor_score = self._calculate_neighbor_score(neighbor_memory, seed)

                    # Apply neighbor threshold filtering
                    if neighbor_threshold is not None and neighbor_score < neighbor_threshold:
                        continue  # Skip neighbors below threshold

                    # Skip if this neighbor is actually one of the original seeds
                    if neighbor_memory.hrid in seed_hrids:
                        continue  # Don't include seeds in neighbors list

                    # Extract relationship info and add to relationship tree
                    rel_type = row.get("rel_type")
                    target_hrid = neighbor_memory.hrid or neighbor_memory.id

                    if rel_type and target_hrid:
                        # Create RelationshipInfo with nested structure support
                        relationship_info = RelationshipInfo(
                            relation_type=rel_type,
                            target_hrid=target_hrid,
                            score=neighbor_score,
                        )

                        # Add to relationship tree - find the right place to nest this relationship
                        self._add_to_relationship_tree(original_seeds, seed.hrid, relationship_info)

                    # Create MemoryNeighbor object using utility method
                    neighbor_result = self.memory_serializer.to_memory_neighbor(
                        neighbor_memory, neighbor_score, datetime_format
                    )
                    next_hop_results.append(neighbor_result)

            # Add this hop's results to all neighbors
            all_neighbors.extend(next_hop_results)

            # Prepare for next hop (if any) - convert neighbors back to seeds for next iteration
            next_hop_seeds = []
            for neighbor in next_hop_results:
                # Convert MemoryNeighbor back to MemorySeed for next hop expansion
                seed_for_next_hop = MemorySeed(
                    user_id=neighbor.user_id,
                    hrid=neighbor.hrid,
                    memory_type=neighbor.memory_type,
                    created_at=neighbor.created_at,
                    updated_at=neighbor.updated_at,
                    payload=neighbor.payload,
                    score=neighbor.score,  # Use the neighbor's score
                    relationships=[],  # No relationships needed for expansion
                )
                next_hop_seeds.append(seed_for_next_hop)

            current_hop_seeds = next_hop_seeds

            # Stop if no more neighbors found
            if not next_hop_results:
                break

        # Deduplicate neighbors by HRID, keeping the highest score
        return self._deduplicate_neighbors(all_neighbors)

    def _add_to_relationship_tree(
        self, seeds: list[MemorySeed], source_hrid: str, relationship_info: RelationshipInfo
    ) -> None:
        """Add relationship to the correct place in the relationship tree.

        This method recursively searches through the relationship tree to find
        where the new relationship should be nested based on the source HRID.

        Args:
            seeds: Original seeds that contain the relationship tree roots
            source_hrid: HRID of the memory that has this relationship
            relationship_info: Relationship to add to the tree
        """
        # First, try to add to direct seeds
        for seed in seeds:
            if seed.hrid == source_hrid:
                seed.relationships.append(relationship_info)
                return

        # If not found in seeds, search recursively in relationship trees
        for seed in seeds:
            if self._add_to_nested_relationships(
                seed.relationships, source_hrid, relationship_info
            ):
                return

    def _add_to_nested_relationships(
        self,
        relationships: list[RelationshipInfo],
        source_hrid: str,
        relationship_info: RelationshipInfo,
    ) -> bool:
        """Recursively search and add to nested relationships.

        Args:
            relationships: List of relationships to search
            source_hrid: HRID of the memory that has this relationship
            relationship_info: Relationship to add

        Returns:
            bool: True if relationship was added, False if not found
        """
        for rel in relationships:
            # Check if this relationship target matches our source
            if rel.target_hrid == source_hrid:
                rel.relationships.append(relationship_info)
                return True

            # Recursively search nested relationships
            if self._add_to_nested_relationships(rel.relationships, source_hrid, relationship_info):
                return True

        return False

    def _deduplicate_neighbors(self, neighbors: list[MemoryNeighbor]) -> list[MemoryNeighbor]:
        """Deduplicate neighbors by HRID, keeping the one with the highest score.

        Args:
            neighbors: List of neighbors that may contain duplicates

        Returns:
            list[MemoryNeighbor]: Deduplicated neighbors with highest scores
        """
        if not neighbors:
            return neighbors

        # Group neighbors by HRID and keep the one with highest score
        best_neighbors: dict[str, MemoryNeighbor] = {}

        for neighbor in neighbors:
            hrid = neighbor.hrid
            if hrid not in best_neighbors or neighbor.score > best_neighbors[hrid].score:
                best_neighbors[hrid] = neighbor

        # Return deduplicated list, preserving original order where possible
        seen_hrids = set()
        deduplicated = []

        for neighbor in neighbors:
            if neighbor.hrid not in seen_hrids:
                deduplicated.append(best_neighbors[neighbor.hrid])
                seen_hrids.add(neighbor.hrid)

        return deduplicated

    def _calculate_neighbor_score(self, neighbor_memory: Memory, seed: MemorySeed) -> float:
        """Calculate recursive neighbor relevance score.

        Args:
            neighbor_memory: The neighbor memory object.
            seed: The seed that led to this neighbor.

        Returns:
            float: Recursive relevance score.
        """
        # Get anchor fields from YAML schema instead of hardcoding "statement"
        neighbor_anchor_field = self.yaml_translator.get_anchor_field(neighbor_memory.memory_type)
        seed_anchor_field = self.yaml_translator.get_anchor_field(seed.memory_type)
        neighbor_anchor = neighbor_memory.payload.get(neighbor_anchor_field, "")
        seed_anchor = seed.payload.get(seed_anchor_field, "")

        return calculate_neighbor_relevance(
            neighbor_anchor=neighbor_anchor,
            seed_anchor=seed_anchor,
            seed_score=seed.score,
            embedder=self.embedder,
        )


class SearchService:
    """Search orchestration service - coordinates specialized handlers for GraphRAG operations.

    Clean orchestration layer that delegates to specialized handlers:
    - VectorSearchHandler: Qdrant vector search and seed generation
    - GraphExpansionHandler: Kuzu graph traversal and neighbor expansion
    - MemorySerializer: Memory object packing/unpacking and conversion
    - PayloadProjector: Payload filtering and projection

    Attributes:
        vector_handler: Handles vector search operations.
        graph_handler: Handles graph expansion operations.
        memory_serializer: Handles memory serialization and construction.
        payload_projector: Handles payload projection.
    """

    def __init__(self, db_clients):
        """Initialize SearchService with DatabaseClients.

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
        self.config = get_config()

        # Initialize utility classes
        self.memory_serializer = MemorySerializer(self.hrid_tracker)
        self.payload_projector = PayloadProjector(self.yaml_translator)

        # Initialize handler classes
        self.vector_handler = VectorSearchHandler(
            self.qdrant, self.embedder, self.memory_serializer, self.payload_projector
        )
        self.graph_handler = GraphExpansionHandler(
            self.kuzu,
            self.embedder,
            self.yaml_translator,
            self.memory_serializer,
            self.payload_projector,
            self.hrid_tracker,
        )

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
        *,
        memory_type: str | None = None,
        relation_names: list[str] | None = None,
        neighbor_limit: int = 5,
        hops: int = 1,
        include_details: str = "self",
        modified_within_days: int | None = None,
        filters: dict[str, Any] | None = None,
        projection: dict[str, list[str]] | None = None,
        score_threshold: float | None = None,
        decay_rate: float | None = None,
        decay_threshold: float | None = None,
        datetime_format: str | None = None,
    ) -> SearchResult:
        """GraphRAG search orchestration: vector seeds → graph expansion → result composition.

        Pure orchestration method that delegates to specialized handlers for clean separation of concerns.

        Args:
            query: Search query text (required).
            user_id: User ID for filtering (required).
            limit: Maximum results to return (default: 5).
            memory_type: Optional memory type filter.
            relation_names: Specific relations to expand (None = all relations).
            neighbor_limit: Max neighbors per seed (default: 5).
            hops: Number of graph hops to expand (default: 1).
            include_details: "self" (full payload for seeds, anchor only for neighbors), "all" (full payload for both), or "none" (anchor only for both).
            modified_within_days: Filter by recency (e.g., last 7 days).
            filters: Custom field-based filtering (e.g., {"project": "memg-core"}).
            projection: Control which fields to return per memory type.
            score_threshold: Minimum similarity score threshold (0.0-1.0).
            decay_rate: Score decay factor per hop (default: 1.0 = no decay).
            decay_threshold: Explicit neighbor score threshold (overrides decay_rate).
            datetime_format: Optional datetime format string. If None, uses YAML schema default.

        Returns:
            SearchResult: Search result with explicit seed/neighbor separation.
        """
        # Use YAML default datetime format if none provided
        if datetime_format is None:
            datetime_format = self.yaml_translator.get_default_datetime_format()
        # 1. Get seeds from vector search using handler
        seeds = self.vector_handler.search_seeds(
            query=query,
            user_id=user_id,
            limit=limit,
            memory_type=memory_type,
            modified_within_days=modified_within_days,
            filters=filters,
            projection=projection,
            score_threshold=score_threshold,
            include_details=include_details,
            datetime_format=datetime_format,
        )

        if not seeds:
            return SearchResult()

        # 2. Graph expansion (neighbors with anchor-only payloads)
        neighbors: list[MemoryNeighbor] = []
        if hops > 0:
            # Calculate neighbor filtering threshold
            neighbor_threshold = self._calculate_neighbor_threshold(
                score_threshold, decay_rate, decay_threshold, hops
            )

            neighbors = self.graph_handler.expand_neighbors(
                seeds=seeds,
                user_id=user_id,
                relation_names=relation_names,
                neighbor_limit=neighbor_limit,
                hops=hops,
                projection=projection,
                neighbor_threshold=neighbor_threshold,
                include_details=include_details,
                datetime_format=datetime_format,
            )

        # Compose final SearchResult with seeds and neighbors
        return SearchResult(
            memories=seeds,
            neighbors=neighbors,
        )

    def _calculate_neighbor_threshold(
        self,
        score_threshold: float | None,
        decay_rate: float | None,
        decay_threshold: float | None,
        hops: int,
    ) -> float | None:
        """Calculate neighbor filtering threshold using elegant hierarchy.

        Args:
            score_threshold: Minimum similarity score for seeds.
            decay_rate: Score decay factor per hop (1.0 = no decay).
            decay_threshold: Explicit neighbor threshold (overrides decay_rate).
            hops: Number of graph hops.

        Returns:
            float | None: Neighbor threshold or None (no filtering).
        """
        # 1. Most explicit: User specified exact neighbor threshold
        if decay_threshold is not None:
            return decay_threshold

        # 2. Dynamic decay: Calculate threshold based on hops
        if score_threshold is not None and decay_rate is not None:
            return score_threshold * (decay_rate**hops)

        # 3. Conservative default: Same threshold for neighbors as seeds
        if score_threshold is not None:
            return score_threshold

        # 4. No filtering
        return None

    def get_memory(
        self,
        hrid: str,
        user_id: str,
        memory_type: str | None = None,
        include_neighbors: bool = False,
        hops: int = 1,
        relation_types: list[str] | None = None,
        neighbor_limit: int = 5,
        datetime_format: str | None = None,
    ) -> SearchResult | None:
        """Get a single memory by HRID with optional neighbor expansion.

        Args:
            hrid: Human-readable identifier of the memory.
            user_id: User ID for ownership verification.
            memory_type: Optional memory type hint (inferred from HRID if not provided).
            include_neighbors: Whether to include neighbor nodes via graph traversal.
            hops: Number of hops for neighbor expansion (default 1).
            relation_types: Filter by specific relationship types (None = all relations).
            neighbor_limit: Maximum neighbors to return per hop (default 5).
            datetime_format: Optional datetime format string. If None, uses YAML schema default.

        Returns:
            SearchResult | None: SearchResult with single memory as seed and optional neighbors, or None if not found.
        """
        try:
            # Use YAML default datetime format if none provided
            if datetime_format is None:
                datetime_format = self.yaml_translator.get_default_datetime_format()
            # Infer memory type from HRID if not provided
            if memory_type is None:
                memory_type = "_".join(hrid.split("_")[:-1])

            # Get UUID from HRID
            uuid = self.hrid_tracker.get_uuid(hrid, user_id)
            if not uuid:
                return None

            # Get memory data from Qdrant
            point_data = self.qdrant.get_point(uuid)
            if not point_data:
                return None

            # Verify user ownership
            payload = point_data.get("payload", {})
            if payload.get("user_id") != user_id:
                return None

            # Build Memory object using existing serializer
            memory = self.memory_serializer.from_qdrant_point(uuid, payload)

            # Convert to MemorySeed using existing infrastructure
            memory_seed = self.memory_serializer.to_memory_seed(
                memory, 1.0, datetime_format
            )  # Score 1.0 for direct retrieval

            # Handle neighbor expansion if requested
            neighbors: list[MemoryNeighbor] = []
            if include_neighbors and hops > 0:
                neighbors = self.graph_handler.expand_neighbors(
                    seeds=[memory_seed],
                    user_id=user_id,
                    relation_names=relation_types,
                    neighbor_limit=neighbor_limit,
                    hops=hops,
                    projection=None,  # No projection needed for get_memory
                    neighbor_threshold=None,  # No threshold filtering
                    include_details="all",  # Full details for get_memory neighbors
                )

            # Return unified SearchResult
            return SearchResult(
                memories=[memory_seed],
                neighbors=neighbors,
            )

        except (DatabaseError, ValueError, KeyError):
            return None

    def get_memories(
        self,
        user_id: str,
        memory_type: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
        include_neighbors: bool = False,
        hops: int = 1,
        datetime_format: str | None = None,
    ) -> SearchResult:
        """Get multiple memories with filtering and optional graph expansion.

        Args:
            user_id: User ID for ownership verification.
            memory_type: Optional memory type filter (e.g., "task", "note").
            filters: Optional field filters (e.g., {"status": "open", "priority": "high"}).
            limit: Maximum number of memories to return (default 50).
            offset: Number of memories to skip for pagination (default 0).
            include_neighbors: Whether to include neighbor nodes via graph traversal.
            hops: Number of hops for neighbor expansion (default 1).
            datetime_format: Optional datetime format string. If None, uses YAML schema default.

        Returns:
            SearchResult: SearchResult with memories as seeds and optional neighbors.
        """
        try:
            # Use YAML default datetime format if none provided
            if datetime_format is None:
                datetime_format = self.yaml_translator.get_default_datetime_format()
            # Use KuzuInterface to get nodes with filtering
            results = self.kuzu.get_nodes(
                user_id=user_id,
                node_type=memory_type,
                filters=filters,
                limit=limit,
                offset=offset,
            )

            # Convert Kuzu results to MemorySeeds using existing infrastructure
            memory_seeds: list[MemorySeed] = []
            for result in results:
                # Get UUID and HRID
                uuid = result.get("id")
                hrid = self.hrid_tracker.get_hrid(uuid, user_id) if uuid else None
                if not hrid:
                    continue

                # Build Memory object using existing serializer
                memory = self.memory_serializer.from_kuzu_row(result)

                # Convert to MemorySeed using existing infrastructure
                memory_seed = self.memory_serializer.to_memory_seed(
                    memory, 1.0, datetime_format
                )  # Score 1.0 for direct retrieval
                memory_seeds.append(memory_seed)

            # Handle neighbor expansion if requested
            neighbors: list[MemoryNeighbor] = []
            if include_neighbors and memory_seeds and hops > 0:
                neighbors = self.graph_handler.expand_neighbors(
                    seeds=memory_seeds,
                    user_id=user_id,
                    relation_names=None,  # All relations
                    neighbor_limit=5,  # Default limit
                    hops=hops,
                    projection=None,
                    neighbor_threshold=None,  # No threshold filtering
                    include_details="all",  # Full details for get_memories neighbors
                )

            # Return unified SearchResult
            return SearchResult(
                memories=memory_seeds,
                neighbors=neighbors,
            )

        except (DatabaseError, ValueError, KeyError) as e:
            # Log the error instead of silently failing
            logging.error(f"get_memories() failed: {type(e).__name__}: {e}", exc_info=True)
            return SearchResult()  # Return empty SearchResult instead of empty list


def create_search_service(db_clients) -> SearchService:
    """Factory function to create a SearchService instance.

    Args:
        db_clients: DatabaseClients instance (after init_dbs() called).

    Returns:
        SearchService: Configured SearchService instance.
    """
    return SearchService(db_clients)
