"""Core data models for memory system"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryType(str, Enum):
    """Simple, stable memory types for production system"""

    DOCUMENT = "document"  # Technical documentation, articles, guides with AI summary
    NOTE = "note"  # Brief notes, observations, ideas
    CONVERSATION = "conversation"  # Chat messages, dialogue
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

    # Optional project scoping
    project_id: Optional[str] = Field(None, description="Optional project ID for scoping")
    project_name: Optional[str] = Field(None, description="Optional project name for display")

    # Type classification (simple 3-type system)
    memory_type: MemoryType = Field(MemoryType.NOTE, description="Type of memory")

    # AI-generated fields (based on type)
    summary: Optional[str] = Field(None, description="AI-generated summary (for documents)")
    ai_verified_type: Optional[bool] = Field(
        None, description="AI confirmation of type classification"
    )

    # Metadata (minimal but flexible)
    title: Optional[str] = Field(None, description="Optional title")
    source: str = Field("user", description="Source of memory")
    tags: List[str] = Field(default_factory=list, description="Flexible tagging")

    # Processing metadata
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Storage confidence")
    vector: Optional[List[float]] = Field(None, description="Embedding vector")

    # Temporal fields (simplified)
    is_valid: bool = Field(True, description="Whether memory is currently valid")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Optional expiration for documents")

    # Version tracking (for document supersession)
    supersedes: Optional[str] = Field(None, description="ID of memory this supersedes")
    superseded_by: Optional[str] = Field(None, description="ID of memory that supersedes this")

    # Task-specific optional fields (only used when memory_type = TASK)
    task_status: Optional[TaskStatus] = Field(None, description="Task status for TASK memory type")
    task_priority: Optional[TaskPriority] = Field(None, description="Task priority level")
    assignee: Optional[str] = Field(None, description="Task assignee username/email")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    story_points: Optional[int] = Field(None, ge=0, le=100, description="Effort estimation")
    epic_id: Optional[str] = Field(None, description="Parent epic ID")
    sprint_id: Optional[str] = Field(None, description="Sprint assignment")

    # Code linking (for development tasks)
    code_file_path: Optional[str] = Field(None, description="Associated code file path")
    code_line_range: Optional[str] = Field(None, description="Line range (e.g., '10-25')")
    code_signature: Optional[str] = Field(None, description="Function/class signature")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_qdrant_payload(self) -> Dict[str, Any]:
        """Convert memory to Qdrant point payload"""
        payload = {
            "user_id": self.user_id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "summary": self.summary,
            "ai_verified_type": self.ai_verified_type,
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
                    "story_points": self.story_points,
                    "epic_id": self.epic_id,
                    "sprint_id": self.sprint_id,
                    "code_file_path": self.code_file_path,
                    "code_line_range": self.code_line_range,
                    "code_signature": self.code_signature,
                    "has_code_link": bool(self.code_file_path or self.code_signature),
                }
            )

        return payload

    def to_kuzu_node(self) -> Dict[str, Any]:
        """Convert memory to Kuzu node properties"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "project_id": self.project_id or "",
            "project_name": self.project_name or "",
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

    def mark_superseded_by(self, new_memory_id: str) -> "Memory":
        """Mark this memory as superseded by a newer version"""
        self.is_valid = False
        self.superseded_by = new_memory_id
        return self

    def is_document(self) -> bool:
        """Check if this is a document type memory"""
        return self.memory_type == MemoryType.DOCUMENT

    def is_note(self) -> bool:
        """Check if this is a note type memory"""
        return self.memory_type == MemoryType.NOTE

    def needs_summary(self) -> bool:
        """Check if this memory type should have an AI-generated summary"""
        return self.memory_type == MemoryType.DOCUMENT and self.summary is None

    def word_count(self) -> int:
        """Get approximate word count of content"""
        return len(self.content.split())

    def is_task(self) -> bool:
        """Check if this is a task type memory"""
        return self.memory_type == MemoryType.TASK

    def is_overdue(self) -> bool:
        """Check if this task is overdue"""
        if not self.is_task() or not self.due_date:
            return False

        # Handle timezone comparison
        now = datetime.now(timezone.utc)
        due_date = self.due_date
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)

        return due_date < now and self.task_status not in [
            TaskStatus.DONE,
            TaskStatus.CANCELLED,
        ]

    def is_in_progress(self) -> bool:
        """Check if this task is currently in progress"""
        return self.is_task() and self.task_status == TaskStatus.IN_PROGRESS

    def has_code_link(self) -> bool:
        """Check if this task is linked to code"""
        return bool(self.code_file_path or self.code_signature)

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()


class ImportanceLevel(str, Enum):
    """Entity importance levels"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RelationshipStrength(str, Enum):
    """Relationship strength levels"""

    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    ESSENTIAL = "ESSENTIAL"


class RelationshipType(str, Enum):
    """Common relationship types for memory system"""

    MENTIONED_IN = "MENTIONED_IN"
    RELATES_TO = "RELATES_TO"
    USED_IN = "USED_IN"
    WORKS_WITH = "WORKS_WITH"
    PART_OF = "PART_OF"
    SIMILAR_TO = "SIMILAR_TO"


class EntityType(str, Enum):
    """Standardized entity types for GraphRAG"""

    # Technology Types
    TECHNOLOGY = "TECHNOLOGY"
    DATABASE = "DATABASE"
    LIBRARY = "LIBRARY"
    TOOL = "TOOL"

    # System Types
    COMPONENT = "COMPONENT"
    SERVICE = "SERVICE"
    ARCHITECTURE = "ARCHITECTURE"
    PROTOCOL = "PROTOCOL"

    # Problem/Solution Types
    ERROR = "ERROR"
    ISSUE = "ISSUE"
    SOLUTION = "SOLUTION"
    WORKAROUND = "WORKAROUND"

    # Domain Types
    CONCEPT = "CONCEPT"
    METHOD = "METHOD"
    CONFIGURATION = "CONFIGURATION"
    FILE_TYPE = "FILE_TYPE"

    # Task Management Types
    TICKET = "TICKET"
    EPIC = "EPIC"
    MILESTONE = "MILESTONE"
    SPRINT = "SPRINT"
    BOARD = "BOARD"


class Entity(BaseModel):
    """Entity extracted from memories"""

    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for entity isolation")
    name: str = Field(..., description="Entity name")
    type: EntityType = Field(..., description="Standardized entity type")
    description: str = Field(..., description="Entity description")
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_valid: bool = Field(True)
    source_memory_id: Optional[str] = Field(None, description="Source memory ID")

    # Optional metadata
    importance: Optional[ImportanceLevel] = Field(None)
    context: Optional[str] = Field(None)

    def to_kuzu_node(self) -> Dict[str, Any]:
        """Convert to Kuzu node properties"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "confidence": self.confidence,
            "created_at": str(self.created_at.isoformat()),
            "last_updated": str(self.last_updated.isoformat()),
            "is_valid": self.is_valid,
            "source_memory_id": self.source_memory_id or "",
        }


class Project(BaseModel):
    """Simple project entity for optional memory scoping"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Optional project description")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(True, description="Whether project is active")

    def to_kuzu_node(self) -> Dict[str, Any]:
        """Convert to Kuzu node properties"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description or "",
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "is_active": self.is_active,
        }


class Relationship(BaseModel):
    """Relationship between entities or memories"""

    id: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(..., description="User ID for relationship isolation")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Type of relationship")
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_valid: bool = Field(True)

    # Optional metadata
    strength: Optional[RelationshipStrength] = Field(None)
    context: Optional[str] = Field(None)
    source_memory_id: Optional[str] = Field(None)

    def to_kuzu_props(self) -> Dict[str, Any]:
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
    vector: List[float] = Field(..., description="Embedding vector")
    point_id: Optional[str] = Field(None, description="Qdrant point ID")

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
    distance: Optional[float] = Field(None, description="Vector distance")
    source: str = Field(..., description="Search source (qdrant/kuzu/hybrid)")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ProcessingResult(BaseModel):
    """Result from memory processing pipeline"""

    success: bool
    memories_created: List[Memory] = Field(default_factory=list)
    entities_created: List[Entity] = Field(default_factory=list)
    relationships_created: List[Relationship] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[float] = Field(None)

    @property
    def total_created(self) -> int:
        return (
            len(self.memories_created)
            + len(self.entities_created)
            + len(self.relationships_created)
        )


@dataclass
class ConversationSummary:
    """Conversation summary for context-aware processing"""

    summary: str
    last_updated: datetime
    message_count: int = 0
    participants: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "summary": self.summary,
            "last_updated": self.last_updated.isoformat(),
            "message_count": self.message_count,
            "participants": self.participants,
        }


@dataclass
class Message:
    """Individual message in conversation history"""

    content: str
    timestamp: datetime
    speaker: Optional[str] = None
    message_type: str = "user"  # user, assistant, system

    def to_dict(self) -> dict:
        """Convert to dictionary for storage"""
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "speaker": self.speaker,
            "message_type": self.message_type,
        }


@dataclass
class MessagePair:
    """Message pair for MEM0-style processing (m_t-1, m_t)"""

    previous_message: Optional[Message]
    current_message: Message
    conversation_summary: Optional[str] = None
    recent_messages: List[Message] = field(default_factory=list)

    def to_extraction_context(self) -> str:
        """Convert to context string for memory extraction"""
        context_parts = []

        if self.conversation_summary:
            context_parts.append(f"Conversation Summary: {self.conversation_summary}")

        if self.recent_messages:
            context_parts.append("Recent Messages:")
            for msg in self.recent_messages[-5:]:  # Last 5 messages
                speaker = f"{msg.speaker}: " if msg.speaker else ""
                context_parts.append(f"- {speaker}{msg.content}")

        if self.previous_message:
            prev_speaker = (
                f"{self.previous_message.speaker}: " if self.previous_message.speaker else ""
            )
            context_parts.append(f"Previous Message: {prev_speaker}{self.previous_message.content}")

        curr_speaker = f"{self.current_message.speaker}: " if self.current_message.speaker else ""
        context_parts.append(f"Current Message: {curr_speaker}{self.current_message.content}")

        return "\n\n".join(context_parts)
