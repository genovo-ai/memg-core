"""Data models for AI extraction and analysis"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TextAnalysis(BaseModel):
    """Text analysis result matching text_analysis schema"""

    title: str = Field(..., description="Generated title")
    summary: str = Field(..., description="Content summary")
    topics: List[str] = Field(..., description="Identified topics")
    key_concepts: List[str] = Field(default_factory=list)

    # Additional metadata not in schema
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryExtraction(BaseModel):
    """Memory extraction result matching memory_extraction schema"""

    memories: List[str] = Field(..., description="Extracted memory facts")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    extraction_context: Optional[str] = Field(None)

    # Additional processing metadata
    source_content: Optional[str] = Field(None)
    processing_method: str = Field("ai_extraction")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("memories")
    @classmethod
    def memories_not_empty(cls, v):
        if not v:
            raise ValueError("At least one memory must be extracted")
        return [mem.strip() for mem in v if mem.strip()]


class ExtractedEntity(BaseModel):
    """Single entity from extraction matching schema"""

    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type")
    description: str = Field(..., description="Entity description")
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Optional fields from schema
    importance: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    context: Optional[str] = Field(None)


class ExtractedRelationship(BaseModel):
    """Single relationship from extraction matching schema"""

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    type: str = Field(..., description="Relationship type")
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Optional fields from schema
    strength: Optional[str] = Field(None, pattern="^(WEAK|MODERATE|STRONG|ESSENTIAL)$")
    context: Optional[str] = Field(None)


class EntityRelationshipExtraction(BaseModel):
    """Entity and relationship extraction matching entity_relationship_extraction schema"""

    entities: List[ExtractedEntity] = Field(..., description="Extracted entities")
    relationships: List[ExtractedRelationship] = Field(
        ..., description="Extracted relationships"
    )

    # Additional processing metadata
    source_content: Optional[str] = Field(None)
    processing_method: str = Field("ai_extraction")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContentMetadata(BaseModel):
    """Content metadata from schema"""

    complexity: Optional[str] = Field(
        None, pattern="^(SIMPLE|MODERATE|COMPLEX|EXPERT)$"
    )
    domain: Optional[str] = Field(None)
    priority: Optional[str] = Field(None, pattern="^(LOW|MEDIUM|HIGH|URGENT)$")


class ContentAnalysis(BaseModel):
    """Content analysis result matching content_analysis schema"""

    content_type: str = Field(..., description="Type of content")
    main_themes: List[str] = Field(..., description="Main themes")
    key_insights: List[str] = Field(default_factory=list)
    actionable_items: List[str] = Field(default_factory=list)
    metadata: Optional[ContentMetadata] = Field(None)

    # Additional processing metadata
    source_content: Optional[str] = Field(None)
    processing_method: str = Field("ai_analysis")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractionContext(BaseModel):
    """Context for extraction operations"""

    content: str = Field(..., description="Source content")
    content_type: str = Field("text", description="Type of content")

    # Extraction options
    extract_memories: bool = Field(True)
    extract_entities: bool = Field(True)
    extract_relationships: bool = Field(True)
    analyze_content: bool = Field(True)

    # Processing parameters
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0)
    max_entities: int = Field(50, ge=1, le=200)
    max_relationships: int = Field(100, ge=1, le=500)

    # Metadata
    source: Optional[str] = Field(None)
    user_id: Optional[str] = Field(None)
    session_id: Optional[str] = Field(None)


class ExtractionResult(BaseModel):
    """Complete extraction result"""

    success: bool

    # Extracted data
    text_analysis: Optional[TextAnalysis] = Field(None)
    memory_extraction: Optional[MemoryExtraction] = Field(None)
    entity_extraction: Optional[EntityRelationshipExtraction] = Field(None)
    content_analysis: Optional[ContentAnalysis] = Field(None)

    # Processing metadata
    processing_time_ms: float
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Context
    source_content_length: int
    extraction_method: str = Field("ai_pipeline")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_extractions(self) -> bool:
        """Check if any extractions were successful"""
        return any(
            [
                self.text_analysis,
                self.memory_extraction,
                self.entity_extraction,
                self.content_analysis,
            ]
        )
