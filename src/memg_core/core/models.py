from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Memory(BaseModel):
    """Core memory model with YAML-driven payload validation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    memory_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.8
    vector: list[float] | None = None
    is_valid: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    supersedes: str | None = None
    superseded_by: str | None = None

    # NEW: human-readable id (e.g., TASK_AAA001)
    hrid: str | None = None

    @field_validator("memory_type")
    @classmethod
    def memory_type_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("memory_type cannot be empty")
        return v.strip()

    # Remove hardcoded properties to rely on dynamic __getattr__
    # (properties removed – dynamic __getattr__ handles field access)

    def to_qdrant_payload(self) -> dict[str, Any]:
        core = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "tags": self.tags,
            "confidence": self.confidence,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat(),
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }
        if self.hrid:
            core["hrid"] = self.hrid

        # entity fields live under "entity"
        entity = dict(self.payload)

        payload = {
            "core": core,
            "entity": entity,
            # Flat mirror: include all entity fields at top-level for vector DB convenience
            **entity,
        }
        return payload

    def to_kuzu_node(self) -> dict[str, Any]:
        """
        Core Kuzu node: minimal metadata + YAML-defined entity fields.
        No hardcoded field names or backward compatibility.
        """
        entity = self.payload or {}
        node = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "tags": ",".join(self.tags) if isinstance(self.tags, list) else (self.tags or ""),
            "created_at": self.created_at.isoformat(),
            "is_valid": self.is_valid,
        }

        # Add core Memory fields if present
        if self.hrid:
            node["hrid"] = self.hrid
        if self.supersedes:
            node["supersedes"] = self.supersedes
        if self.superseded_by:
            node["superseded_by"] = self.superseded_by

        # Include all entity fields from payload (no filtering, no assumptions)
        for k, v in entity.items():
            if k in {"vector"}:
                continue  # skip heavy data
            if isinstance(v, str):
                node[k] = v[:256]  # trim long strings for storage efficiency
            else:
                node[k] = v

        # Store anchor text as statement - YAML schema required, no fallback
        from .yaml_translator import build_anchor_text

        anchor_text = build_anchor_text(self)
        node["statement"] = anchor_text
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
    # YAML → Entity projection helpers
    # ---------------------------------------------------------------------
    def to_entity_model(self):
        """Project this Memory into a dynamic Pydantic entity model.

        Returns an instance of the auto-generated model class that matches
        the entity type defined in the YAML schema. Only non-system fields
        are included.
        """
        from .yaml_translator import get_entity_model  # local import to avoid cycles

        model_cls = get_entity_model(self.memory_type)
        # Pass only fields that the model expects
        model_fields = {
            k: v for k, v in (self.payload or {}).items() if k in model_cls.model_fields
        }
        return model_cls(**model_fields)


class Entity(BaseModel):
    """Entity extracted from memories"""

    id: str | None = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for entity isolation")
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type")
    description: str = Field(..., description="Entity description")
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_valid: bool = Field(True)
    source_memory_id: str | None = Field(None, description="Source memory ID")

    def to_kuzu_node(self) -> dict[str, Any]:
        """Convert to Kuzu node properties"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "confidence": self.confidence,
            "created_at": str(self.created_at.isoformat()),
            "is_valid": self.is_valid,
            "source_memory_id": self.source_memory_id or "",
        }


class Relationship(BaseModel):
    """Relationship between entities or memories"""

    id: str | None = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for relationship isolation")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Type of relationship")
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_valid: bool = Field(True)

    def to_kuzu_props(self) -> dict[str, Any]:
        """Convert to Kuzu relationship properties"""
        return {
            "user_id": self.user_id,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "created_at": str(self.created_at.isoformat()),
            "is_valid": self.is_valid,
        }


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
    """Result from memory processing pipeline"""

    success: bool
    memories_created: list[Memory] = Field(default_factory=list)
    entities_created: list[Entity] = Field(default_factory=list)
    relationships_created: list[Relationship] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    processing_time_ms: float | None = Field(None)

    @property
    def total_created(self) -> int:
        return (
            len(self.memories_created)
            + len(self.entities_created)
            + len(self.relationships_created)
        )
