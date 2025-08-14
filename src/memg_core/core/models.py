"""Core data models for memory system - minimal and stable"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Memory(BaseModel):
    """Type-agnostic Memory model - core fields only"""

    # Core identification
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for memory isolation")
    memory_type: str = Field(..., description="Entity type name from YAML schema")

    # Generic payload for entity-specific fields
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Entity-specific fields from YAML"
    )

    # Core metadata (minimal but stable)
    tags: list[str] = Field(default_factory=list, description="Flexible tagging")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Storage confidence")
    vector: list[float] | None = Field(None, description="Embedding vector")

    # Temporal fields
    is_valid: bool = Field(True, description="Whether memory is currently valid")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Version tracking
    supersedes: str | None = Field(None, description="ID of memory this supersedes")
    superseded_by: str | None = Field(None, description="ID of memory that supersedes this")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Convert memory to Qdrant point payload with nested structure"""
        return {
            "core": {
                "id": self.id,
                "user_id": self.user_id,
                "memory_type": self.memory_type,
                "tags": self.tags,
                "confidence": self.confidence,
                "is_valid": self.is_valid,
                "created_at": self.created_at.isoformat(),
                "supersedes": self.supersedes,
                "superseded_by": self.superseded_by,
            },
            "entity": self.payload,  # All entity-specific fields from YAML
        }

    def to_kuzu_node(self) -> dict[str, Any]:
        """Convert memory to Kuzu node properties - core metadata only"""
        kuzu_data = {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "tags": ",".join(self.tags),
            "confidence": self.confidence,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat(),
            "supersedes": self.supersedes or "",
            "superseded_by": self.superseded_by or "",
        }

        # Add specific fields that are useful for graph queries
        # Title for display purposes
        if "title" in self.payload:
            kuzu_data["title"] = str(self.payload["title"])[:200] or ""
        else:
            kuzu_data["title"] = ""

        # Task-specific fields for relationship potential
        if self.memory_type == "task":
            kuzu_data["task_status"] = self.payload.get("task_status", "")
            kuzu_data["assignee"] = self.payload.get("assignee", "")
            if "due_date" in self.payload and self.payload["due_date"]:
                kuzu_data["due_date"] = str(self.payload["due_date"])
            else:
                kuzu_data["due_date"] = ""

        return kuzu_data

    @field_validator("memory_type")
    @classmethod
    def memory_type_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Memory type cannot be empty")
        return v.strip()


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
