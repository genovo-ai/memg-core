"""Memory Retriever showcase - convenience wrappers and specialized searches"""

from datetime import UTC, datetime, timedelta
from typing import Any

from ..api.public import search
from ..core.models import MemoryType, SearchResult


class MemoryRetriever:
    """Convenience wrapper for memory retrieval with specialized search methods"""

    def __init__(self):
        """Initialize the Memory Retriever - uses API layer for all operations"""
        # No direct interface access - all operations go through API
        pass

    def search_memories(
        self,
        query: str,
        user_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """Search for memories with convenience filters

        Args:
            query: Search query text
            user_id: User ID for memory isolation (required)
            filters: Optional metadata filters dict {
                'entity_types': List[str],
                'days_back': int,
                'tags': List[str],
                'memory_type': str,
            }
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of SearchResult objects with memories and scores
        """
        # Convert convenience filters to core filters
        core_filters = {}
        if filters:
            for key, value in filters.items():
                if key == "days_back" and isinstance(value, int):
                    # Convert days_back to timestamp filter
                    cutoff = datetime.now(UTC) - timedelta(days=value)
                    core_filters["created_at"] = {"gte": cutoff.isoformat()}
                elif value is not None:
                    core_filters[key] = value

        # Use core search
        results = search(
            query=query,
            user_id=user_id,
            limit=limit,
            filters=core_filters,
        )

        # Filter by score threshold
        return [r for r in results if r.score >= score_threshold]

    def search_by_technology(
        self,
        technology: str,
        user_id: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search for memories related to a specific technology

        Args:
            technology: Technology name to search for
            user_id: User ID for filtering
            limit: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        # Search with technology-focused query
        query = f"technology {technology} technical documentation implementation"

        # Add entity type filter if supported
        filters = {"entity_types": ["TECHNOLOGY", "LIBRARY", "TOOL", "DATABASE"]}

        return self.search_memories(
            query=query,
            user_id=user_id,
            filters=filters,
            limit=limit,
        )

    def find_error_solutions(
        self,
        error_message: str,
        user_id: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Find solutions for specific errors

        Args:
            error_message: Error message to find solutions for
            user_id: User ID for filtering
            limit: Maximum results to return

        Returns:
            List of SearchResult objects with potential solutions
        """
        # Search with error-focused query
        query = f"error solution fix resolved {error_message}"

        # Add entity type filter for errors and solutions
        filters = {"entity_types": ["ERROR", "ISSUE", "SOLUTION", "WORKAROUND"]}

        return self.search_memories(
            query=query,
            user_id=user_id,
            filters=filters,
            limit=limit,
        )

    def search_by_component(
        self,
        component: str,
        user_id: str,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search for memories related to a specific component

        Args:
            component: Component name to search for
            user_id: User ID for filtering
            limit: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        # Search with component-focused query
        query = f"component service module {component} architecture implementation"

        # Add entity type filter for components
        filters = {"entity_types": ["COMPONENT", "SERVICE", "ARCHITECTURE"]}

        return self.search_memories(
            query=query,
            user_id=user_id,
            filters=filters,
            limit=limit,
        )

    def get_category_stats(self, user_id: str) -> dict[str, int]:
        """Get memory count statistics by category

        Note: This is a placeholder - direct database queries are not supported
        in the showcase layer. Use the system info API for statistics.

        Args:
            user_id: User ID for filtering

        Returns:
            Dictionary with memory type counts (placeholder implementation)
        """
        # Placeholder implementation - real stats would require system API
        return {mt.value: 0 for mt in MemoryType}

    def list_categories(self) -> list[str]:
        """List available memory categories (types)"""
        return [mt.value for mt in MemoryType]

    def expand_with_graph_neighbors(
        self,
        results: list[SearchResult],
        user_id: str,
        neighbor_limit: int = 5,
    ) -> list[SearchResult]:
        """Expand search results with graph neighbors

        Note: This is a placeholder - neighbor expansion is handled automatically
        by the core search pipeline. This method just returns the original results.

        Args:
            results: Initial search results
            user_id: User ID for filtering
            neighbor_limit: Max neighbors per result (ignored)

        Returns:
            Original results (neighbor expansion handled by core pipeline)
        """
        # The core pipeline already handles neighbor expansion
        # This method is kept for API compatibility but does nothing
        return results
