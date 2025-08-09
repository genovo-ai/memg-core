"""Memory system data models."""

from .api import (
    CreateMemoryFromMessagePairRequest,
    CreateMemoryRequest,
    MemoryStatsResponse,
    ProcessingResponse,
    SearchRequest,
    SearchResponse,
)

# Template-aware models with backward compatibility
# Keep original models available for legacy code
from .core import Entity as CoreEntity
from .core import EntityType
from .core import EntityType as CoreEntityType
from .core import ImportanceLevel, Memory, MemoryType, ProcessingResult
from .core import Relationship as CoreRelationship
from .core import RelationshipStrength
from .core import RelationshipType
from .core import RelationshipType as CoreRelationshipType
from .core import SearchResult
from .extraction import (
    ContentAnalysis,
    EntityRelationshipExtraction,
    MemoryExtraction,
    TextAnalysis,
)
from .template_models import TemplateAwareEntity as Entity
from .template_models import TemplateAwareRelationship as Relationship

__all__ = [
    # Core models
    "MemoryType",
    "Memory",
    "Entity",
    "Relationship",
    "SearchResult",
    "ProcessingResult",
    # Enums
    "EntityType",
    "ImportanceLevel",
    "RelationshipStrength",
    "RelationshipType",
    # Legacy/backward compatibility aliases
    "CoreEntity",
    "CoreEntityType",
    "CoreRelationship",
    "CoreRelationshipType",
    # API models
    "CreateMemoryRequest",
    "CreateMemoryFromMessagePairRequest",
    "ProcessingResponse",
    "SearchRequest",
    "SearchResponse",
    "MemoryStatsResponse",
    # Extraction models
    "TextAnalysis",
    "MemoryExtraction",
    "EntityRelationshipExtraction",
    "ContentAnalysis",
]
