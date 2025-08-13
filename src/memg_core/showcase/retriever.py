"""Memory Retriever showcase - convenience wrappers and specialized searches"""

from datetime import UTC, datetime, timedelta
from typing import Any

from ..api.public import search
from ..core.config import get_config
from ..core.interfaces.embedder import GenAIEmbedder
from ..core.interfaces.kuzu import KuzuInterface
from ..core.interfaces.qdrant import QdrantInterface
from ..core.models import MemoryType, SearchResult


class MemoryRetriever:
    """Convenience wrapper for memory retrieval with specialized search methods"""

    def __init__(
        self,
        qdrant_interface: QdrantInterface | None = None,
        kuzu_interface: KuzuInterface | None = None,
        embedder: GenAIEmbedder | None = None,
    ):
        """Initialize the Memory Retriever with optional interfaces"""
        config = get_config()
        self.qdrant = qdrant_interface or QdrantInterface(
            collection_name=config.memg.qdrant_collection_name
        )
        self.kuzu = kuzu_interface or KuzuInterface(db_path=config.memg.kuzu_database_path)
        self.embedder = embedder or GenAIEmbedder()

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

        Args:
            user_id: User ID for filtering

        Returns:
            Dictionary with memory type counts
        """
        # Query Kuzu for memory type counts
        cypher = """
        MATCH (m:Memory)
        WHERE m.user_id = $user_id
        RETURN m.memory_type as type, COUNT(*) as count
        """

        results = self.kuzu.query(cypher, {"user_id": user_id})

        stats = {}
        for row in results:
            memory_type = row.get("type", "unknown")
            count = row.get("count", 0)
            stats[memory_type] = count

        return stats

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

        Args:
            results: Initial search results
            user_id: User ID for filtering
            neighbor_limit: Max neighbors per result

        Returns:
            Expanded list of SearchResult objects
        """
        expanded = []
        seen_ids = {r.memory.id for r in results}

        for result in results[:5]:  # Limit to top 5 for expansion
            if not result.memory.id:
                continue

            # Get neighbors from graph
            neighbors = self.kuzu.neighbors(
                node_label="Memory",
                node_id=result.memory.id,
                limit=neighbor_limit,
                neighbor_label="Memory",
            )

            for neighbor in neighbors:
                neighbor_id = neighbor.get("id")
                if neighbor_id and neighbor_id not in seen_ids:
                    # Create minimal memory from neighbor data
                    from ..core.models import Memory

                    memory = Memory(
                        id=neighbor_id,
                        user_id=neighbor.get("user_id", user_id),
                        content=neighbor.get("content", ""),
                        memory_type=MemoryType(neighbor.get("memory_type", "note")),
                        title=neighbor.get("title"),
                        created_at=(
                            datetime.fromisoformat(neighbor.get("created_at"))
                            if neighbor.get("created_at")
                            else datetime.now(UTC)
                        ),
                    )

                    expanded.append(
                        SearchResult(
                            memory=memory,
                            score=result.score * 0.8,  # Slightly lower score for neighbors
                            source="graph_neighbor",
                            metadata={"expanded_from": result.memory.id},
                        )
                    )
                    seen_ids.add(neighbor_id)

        # Combine and sort by score
        all_results = results + expanded
        all_results.sort(key=lambda r: r.score, reverse=True)

        return all_results
