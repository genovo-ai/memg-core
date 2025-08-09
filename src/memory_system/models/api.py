"""Minimal API models for MCP integration"""

from typing import Any

from pydantic import BaseModel, Field

from .core import Memory, SearchResult


class MemoryResultItem(BaseModel):
    """API response item for memory search results"""

    memory: Memory
    score: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(..., description="Search source")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "MemoryResultItem":
        """Convert SearchResult to API format"""
        return cls(
            memory=result.memory,
            score=result.score,
            source=result.source,
            metadata=result.metadata,
        )


class SearchMemoriesResponse(BaseModel):
    """API response for memory search"""

    result: list[MemoryResultItem] = Field(default_factory=list)
    query: str = Field(..., description="Original search query")
    total_count: int = Field(default=0, description="Total results found")
    filters_applied: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        if self.total_count == 0:
            self.total_count = len(self.result)
