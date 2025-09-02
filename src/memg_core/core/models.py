"""Core models for the memory system."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
import warnings

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .types import get_entity_model

_MAX_SCORE_TOLERANCE = 1.001


class Memory(BaseModel):
    """Core memory model with YAML-driven payload validation.

    Attributes:
        id: Unique identifier (UUID or HRID).
        user_id: Owner of the memory.
        memory_type: Entity type from YAML schema.
        payload: Entity-specific fields.
        vector: Embedding vector.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        hrid: Human-readable identifier.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core fields only - NO hardcoded entity-specific fields
    # NO DEFAULTS - crash early if required fields missing
    id: str = Field(default_factory=lambda: str(uuid4()))  # System-generated ID only
    user_id: str  # REQUIRED - no default
    memory_type: str  # REQUIRED - no default, must come from YAML
    payload: dict[str, Any] = Field(default_factory=dict)  # Entity fields container
    vector: list[float] | None = None  # System-generated vector
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))  # System timestamp
    updated_at: datetime | None = None

    # Human-readable id (e.g., MEMO_AAA001)
    hrid: str | None = None

    @field_validator("memory_type")
    @classmethod
    def memory_type_not_empty(cls, v: str) -> str:
        """Validate that memory_type is not empty.

        Args:
            v: Memory type value.

        Returns:
            str: Stripped memory type.

        Raises:
            ValueError: If memory_type is empty or whitespace.
        """
        if not v or not v.strip():
            raise ValueError("memory_type cannot be empty")
        return v.strip()

    # (properties removed – dynamic __getattr__ handles field access)

    def to_qdrant_payload(self) -> dict[str, Any]:
        """DEPRECATED: Serializes to a strict {'core': ..., 'entity': ...} structure.

        This method is deprecated and will be removed in a future version.
        The current implementation uses flat payload structure directly in MemoryStore.

        Returns:
            dict[str, Any]: Deprecated payload structure.
        """
        warnings.warn(
            "Memory.to_qdrant_payload() is deprecated. Use flat payload structure directly.",
            DeprecationWarning,
            stacklevel=2,
        )

        core = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "created_at": (
                self.created_at.isoformat()
                if hasattr(self.created_at, "isoformat")
                else str(self.created_at)
            ),
        }
        if self.updated_at:
            core["updated_at"] = (
                self.updated_at.isoformat()
                if hasattr(self.updated_at, "isoformat")
                else str(self.updated_at)
            )
        if self.hrid:
            core["hrid"] = self.hrid

        # Entity payload contains only YAML-defined fields
        entity = dict(self.payload)

        return {"core": core, "entity": entity}

    def to_kuzu_node(self) -> dict[str, Any]:
        """Export a minimal node for Kuzu, containing only core fields.

        NO hardcoded fields - only system fields stored in graph.

        Returns:
            dict[str, Any]: Node data for Kuzu storage.
        """
        node = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "created_at": (
                self.created_at.isoformat()
                if hasattr(self.created_at, "isoformat")
                else str(self.created_at)
            ),
        }
        if self.updated_at:
            node["updated_at"] = (
                self.updated_at.isoformat()
                if hasattr(self.updated_at, "isoformat")
                else str(self.updated_at)
            )
        if self.hrid:
            node["hrid"] = self.hrid

        return node

    def __getattr__(self, item: str):
        """Dynamic attribute access for YAML-defined payload fields ONLY.

        No fallback logic, no backward compatibility. If the field is not
        in the payload dictionary, raises AttributeError immediately.
        This enforces strict YAML schema compliance.

        Args:
            item: Field name to access.

        Returns:
            Any: Field value from payload.

        Raises:
            AttributeError: If field is not in payload.
        """
        payload = self.__dict__.get("payload")
        if isinstance(payload, dict) and item in payload:
            return payload[item]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    # ---------------------------------------------------------------------
    # YAML → Dynamic entity model projection helpers
    # ---------------------------------------------------------------------
    def to_entity_model(self):
        """Project this Memory into a dynamic Pydantic entity model.

        Returns an instance of the auto-generated model class that matches
        the entity type defined in the YAML schema. Only non-system fields
        are included.

        Returns:
            BaseModel: Dynamic Pydantic model instance.
        """
        model_cls = get_entity_model(self.memory_type)
        # Pass only fields that the model expects
        model_fields = {
            k: v for k, v in (self.payload or {}).items() if k in model_cls.model_fields
        }
        return model_cls(**model_fields)


# Entity class removed - entities are now YAML-defined Memory objects
# Use Memory with appropriate memory_type instead of hardcoded Entity class


# Relationship class removed - relationships should be YAML-defined
# Use YAML relations schema instead of hardcoded Relationship class


class MemoryPoint(BaseModel):
    """Memory with embedding vector for Qdrant.

    Attributes:
        memory: Memory instance.
        vector: Embedding vector.
        point_id: Qdrant point ID.
    """

    memory: Memory
    vector: list[float] = Field(..., description="Embedding vector")
    point_id: str | None = Field(None, description="Qdrant point ID")

    @field_validator("vector")
    @classmethod
    def vector_not_empty(cls, v):
        """Validate that vector is not empty.

        Args:
            v: Vector to validate.

        Returns:
            list[float]: Validated vector.

        Raises:
            ValueError: If vector is empty.
        """
        if not v:
            raise ValueError("Vector cannot be empty")
        return v


class RelationshipInfo(BaseModel):
    """Relationship information between memories.

    Attributes:
        relation_type: Type of relationship (e.g., FIXES, ADDRESSES).
        target_hrid: HRID of the target memory.
        scores: Scoring information for the relationship.
    """

    relation_type: str = Field(..., description="Relationship type from YAML schema")
    target_hrid: str = Field(..., description="HRID of target memory")
    scores: dict[str, float] = Field(default_factory=dict, description="Relationship scores")


class MemorySeed(BaseModel):
    """Memory seed with full payload and explicit relationships.

    Attributes:
        hrid: Human-readable identifier.
        memory_type: Entity type from YAML schema.
        payload: Full entity payload.
        score: Vector similarity score to query.
        relationships: List of relationships to other memories.
    """

    hrid: str = Field(..., description="Human-readable identifier")
    memory_type: str = Field(..., description="Entity type from YAML schema")
    payload: dict[str, Any] = Field(..., description="Full entity payload")
    score: float = Field(
        ..., ge=0.0, le=1.0 + _MAX_SCORE_TOLERANCE, description="Vector similarity score"
    )
    relationships: list[RelationshipInfo] = Field(
        default_factory=list, description="Relationships to other memories"
    )

    @field_validator("score")
    @classmethod
    def normalize_score(cls, v: float) -> float:
        """Normalize similarity scores to handle floating-point precision errors."""
        if v < 0.0:
            raise ValueError(f"Similarity score cannot be negative: {v}")
        if v > 1.001:
            raise ValueError(f"Similarity score too high (indicates calculation error): {v}")
        return min(v, 1.0)


class MemoryNeighbor(BaseModel):
    """Memory neighbor with anchor-only payload.

    Attributes:
        hrid: Human-readable identifier.
        memory_type: Entity type from YAML schema.
        payload: Anchor-only payload (statement field only).
    """

    hrid: str = Field(..., description="Human-readable identifier")
    memory_type: str = Field(..., description="Entity type from YAML schema")
    payload: dict[str, Any] = Field(..., description="Anchor-only payload")


class EnhancedSearchResult(BaseModel):
    """Enhanced search result with explicit seed/neighbor separation.

    Attributes:
        memories: List of memory seeds with full payloads and relationships.
        neighbors: List of memory neighbors with anchor-only payloads.
    """

    memories: list[MemorySeed] = Field(
        default_factory=list, description="Memory seeds with full payloads"
    )
    neighbors: list[MemoryNeighbor] = Field(
        default_factory=list, description="Memory neighbors with anchor payloads"
    )


class SearchResult(BaseModel):
    """Legacy search result from vector/graph search - kept for backward compatibility.

    Attributes:
        memory: Memory instance.
        score: Similarity score (0.0-1.0).
        distance: Vector distance (deprecated).
        source: Search source (qdrant/kuzu/hybrid).
        metadata: Additional metadata.
    """

    memory: Memory
    score: float = Field(..., ge=0.0, le=1.0 + _MAX_SCORE_TOLERANCE, description="Similarity score")
    distance: float | None = Field(None, description="Vector distance (deprecated)")
    source: str = Field(..., description="Search source (qdrant/kuzu/hybrid)")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("score")
    @classmethod
    def normalize_score(cls, v: float) -> float:
        """Normalize similarity scores to handle floating-point precision errors.

        Cosine similarity should be in [0, 1] range, but floating-point arithmetic
        can produce values slightly above 1.0 (e.g., 1.0000000025725408).

        This validator:
        - Caps scores > 1.0 to exactly 1.0 (for small floating-point errors)
        - Raises error for scores significantly > 1.0 (indicates real problems)
        - Ensures scores >= 0.0

        Args:
            v: Raw similarity score.

        Returns:
            float: Normalized similarity score.

        Raises:
            ValueError: If score is negative or significantly above 1.0.
        """
        if v < 0.0:
            raise ValueError(f"Similarity score cannot be negative: {v}")

        if v > 1.001:  # Allow small floating-point errors, but catch real issues
            raise ValueError(f"Similarity score too high (indicates calculation error): {v}")

        # Cap to 1.0 for small floating-point precision errors
        return min(v, 1.0)


class ProcessingResult(BaseModel):
    """Result from memory processing pipelines - type-agnostic.

    Attributes:
        success: Whether processing succeeded.
        memories_created: List of created memories.
        errors: List of error messages.
        processing_time_ms: Processing time in milliseconds.
    """

    success: bool
    memories_created: list[Memory] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    processing_time_ms: float | None = Field(None)

    @property
    def total_created(self) -> int:
        """Total memories created (all types).

        Returns:
            int: Number of memories created.
        """
        return len(self.memories_created)
