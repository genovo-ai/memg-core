"""Core data models for memory system - minimal and stable"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryType(str, Enum):
    """Simple, stable memory types for production system"""

    DOCUMENT = "document"  # Technical documentation, articles, guides with AI summary
    NOTE = "note"  # Brief notes, observations, ideas
    TASK = "task"  # Task-related memories with status tracking


class TaskStatus(str, Enum):
    """Task status for workflow management"""

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Memory(BaseModel):
    """Simple, stable Memory model for production system"""

    # Core identification
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for memory isolation")
    content: str = Field(..., description="The actual memory content")

    # Type classification (simple 3-type system)
    memory_type: MemoryType = Field(MemoryType.NOTE, description="Type of memory")

    # AI-generated fields (based on type)
    summary: str | None = Field(None, description="AI-generated summary (for documents)")

    # Metadata (minimal but flexible)
    title: str | None = Field(None, description="Optional title")
    source: str = Field("user", description="Source of memory")
    tags: list[str] = Field(default_factory=list, description="Flexible tagging")

    # Processing metadata
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Storage confidence")
    vector: list[float] | None = Field(None, description="Embedding vector")

    # Temporal fields (simplified)
    is_valid: bool = Field(True, description="Whether memory is currently valid")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = Field(None, description="Optional expiration for documents")

    # Version tracking (for document supersession)
    supersedes: str | None = Field(None, description="ID of memory this supersedes")
    superseded_by: str | None = Field(None, description="ID of memory that supersedes this")

    # Task-specific optional fields (only used when memory_type = TASK)
    task_status: TaskStatus | None = Field(None, description="Task status for TASK memory type")
    task_priority: TaskPriority | None = Field(None, description="Task priority level")
    assignee: str | None = Field(None, description="Task assignee username/email")
    due_date: datetime | None = Field(None, description="Task due date")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Convert memory to Qdrant point payload"""
        payload = {
            "user_id": self.user_id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "summary": self.summary,
            "title": self.title,
            "source": self.source,
            "tags": self.tags,
            "confidence": self.confidence,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }

        # Add task-specific fields if this is a task memory
        if self.memory_type == MemoryType.TASK:
            payload.update(
                {
                    "task_status": self.task_status.value if self.task_status else None,
                    "task_priority": (self.task_priority.value if self.task_priority else None),
                    "assignee": self.assignee,
                    "due_date": self.due_date.isoformat() if self.due_date else None,
                }
            )

        return payload

    def to_kuzu_node(self) -> dict[str, Any]:
        """Convert memory to Kuzu node properties"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content[:500],  # Truncate for graph storage
            "memory_type": self.memory_type.value,
            "summary": self.summary or "",
            "title": self.title or "",
            "source": self.source,
            "tags": ",".join(self.tags),
            "confidence": self.confidence,
            "is_valid": self.is_valid,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else "",
            "supersedes": self.supersedes or "",
            "superseded_by": self.superseded_by or "",
        }

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
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
