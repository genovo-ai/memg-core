from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Memory(BaseModel):
    """Core memory model with YAML-driven payload validation."""

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
        if not v or not v.strip():
            raise ValueError("memory_type cannot be empty")
        return v.strip()

    # (properties removed – dynamic __getattr__ handles field access)

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Serializes to a strict {'core': ..., 'entity': ...} structure."""
        core = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "created_at": self.created_at.isoformat(),
        }
        if self.updated_at:
            core["updated_at"] = self.updated_at.isoformat()
        if self.hrid:
            core["hrid"] = self.hrid

        # Entity payload contains only YAML-defined fields
        entity = dict(self.payload)

        return {"core": core, "entity": entity}

    def to_kuzu_node(self) -> dict[str, Any]:
        """
        Exports a minimal node for Kuzu, containing only core fields.
        NO hardcoded fields - only system fields stored in graph.
        """
        node = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "created_at": self.created_at.isoformat(),
        }
        if self.updated_at:
            node["updated_at"] = self.updated_at.isoformat()
        if self.hrid:
            node["hrid"] = self.hrid

        return node

    def __getattr__(self, item: str):
        """Dynamic attribute access for YAML-defined payload fields ONLY.

        No fallback logic, no backward compatibility. If the field is not
        in the payload dictionary, raises AttributeError immediately.
        This enforces strict YAML schema compliance.
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
        """
        from .types import get_entity_model  # Use TypeRegistry directly

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
    """Memory with embedding vector for Qdrant"""

    memory: Memory
    vector: list[float] = Field(..., description="Embedding vector")
    point_id: str | None = Field(None, description="Qdrant point ID")

    @field_validator("vector")
    @classmethod
    def vector_not_empty(cls, v):
        if not v:
            raise ValueError("Vector cannot be empty")
        return v


class SearchResult(BaseModel):
    """Search result from vector/graph search"""

    memory: Memory
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    distance: float | None = Field(None, description="Vector distance")
    source: str = Field(..., description="Search source (qdrant/kuzu/hybrid)")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ProcessingResult(BaseModel):
    """Result from memory processing pipeline - type-agnostic"""

    success: bool
    memories_created: list[Memory] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    processing_time_ms: float | None = Field(None)

    @property
    def total_created(self) -> int:
        """Total memories created (all types)"""
        return len(self.memories_created)
