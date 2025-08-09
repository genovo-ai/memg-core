"""
Memory Retrieval - Search and retrieve memories using semantic search.
"""

from datetime import UTC
from datetime import datetime as dt
import logging
import os

from ..kuzu_graph.interface import KuzuInterface
from ..models import Memory, SearchResult
from ..models.core import MemoryType
from ..qdrant.interface import QdrantInterface
from ..templates.registry import get_template_registry
from ..utils.embeddings import GenAIEmbedder

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """
    Memory retrieval system using semantic search.

    Provides search capabilities across stored memories using:
    - Semantic similarity search via Qdrant
    - Category and tag filtering
    - Confidence-based ranking
    """

    def __init__(
        self,
        qdrant_interface: QdrantInterface | None = None,
        embedder: GenAIEmbedder | None = None,
        kuzu_interface: KuzuInterface | None = None,
    ):
        """
        Initialize the Memory Retriever.

        Args:
            qdrant_interface: Qdrant interface for vector search
            embedder: Embedding generator for query vectors
            kuzu_interface: Kuzu interface for graph search (optional)
        """
        self.qdrant = qdrant_interface or QdrantInterface()
        self.embedder = embedder or GenAIEmbedder()
        self.kuzu = kuzu_interface or KuzuInterface()
        self.graph_enabled = (
            kuzu_interface is not None
            or os.getenv("MEMG_ENABLE_GRAPH_SEARCH", "true").lower() == "true"
        )

        logger.info(f"MemoryRetriever initialized (graph_enabled: {self.graph_enabled})")

    async def search_memories(
        self,
        query: str,
        user_id: str,
        filters: dict | None = None,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        Search for memories using semantic similarity with optional metadata filtering.

        This is the core search method - simple, fast, and extensible.
        Uses Qdrant for semantic search + metadata filtering.

        Args:
            query: Search query text
            user_id: User ID for memory isolation (required)
            filters: Optional metadata filters dict {
                'project_id': str,
                'entity_types': List[str],
                'days_back': int,
                'tags': List[str],
                'custom_field': Any
            }
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of SearchResult objects with memories and scores
        """
        try:
            logger.info(f"Searching memories for: '{query}' (user: {user_id})")

            # Generate query embedding for semantic search
            query_vector = self.embedder.get_embedding(query)
            logger.debug(f"Generated query embedding: {len(query_vector)} dimensions")

            # Build Qdrant filters from simple dict
            qdrant_filters = {}
            if filters:
                for key, value in filters.items():
                    if key == "days_back" and isinstance(value, int):
                        # Convert days_back to timestamp filter
                        from datetime import datetime, timedelta

                        cutoff = datetime.now(UTC) - timedelta(days=value)
                        qdrant_filters["created_at"] = cutoff.isoformat()
                    elif value is not None:
                        # Direct mapping for all other filters
                        qdrant_filters[key] = value

            # Single Qdrant search - clean and fast
            search_results = self.qdrant.search_points(
                vector=query_vector,
                limit=limit,
                user_id=user_id,
                filters=qdrant_filters,
            )

            logger.info(f"Qdrant returned {len(search_results)} results")
            logger.info(f"Search results type: {type(search_results)}")
            if search_results:
                logger.info(
                    f"First result type: {type(search_results[0])}, "
                    f"keys: {list(search_results[0].keys()) if isinstance(search_results[0], dict) else 'Not a dict'}"
                )
            else:
                logger.info("Search results is empty or None")

            # Convert to SearchResult objects and filter by score
            results = []
            logger.info(f"Starting to process {len(search_results)} results from Qdrant")
            for i, result in enumerate(search_results):
                logger.debug(
                    f"Processing result {i + 1}/{len(search_results)}: ID={result.get('id')}, "
                    f"score={result.get('score', 0.0):.3f}"
                )
                if result.get("score", 0.0) < score_threshold:
                    logger.debug(
                        f"Skipping result due to low score: "
                        f"{result.get('score', 0.0):.3f} < {score_threshold}"
                    )
                    continue

                # Extract memory data from payload
                payload = result.get("payload", {})

                # Skip invalid memories if temporal reasoning is enabled
                if self._should_filter_invalid_memories() and not payload.get("is_valid", True):
                    logger.debug(
                        f"Filtering out invalid memory: {payload.get('content', '')[:50]}..."
                    )
                    continue

                # Reconstruct Memory object with all fields

                try:
                    # Parse memory_type enum
                    memory_type_str = payload.get("memory_type", "note")
                    try:
                        memory_type = MemoryType(memory_type_str)
                    except ValueError:
                        memory_type = MemoryType.NOTE  # Default fallback

                    logger.debug(
                        f"Constructing Memory object with ID: {result.get('id')}, "
                        f"payload keys: {list(payload.keys())}"
                    )

                    memory = Memory(
                        id=result.get("id"),  # ID is in the result, not payload
                        user_id=payload.get("user_id", "unknown"),  # Should always be present
                        content=payload.get("content"),
                        memory_type=memory_type,
                        summary=payload.get("summary"),
                        ai_verified_type=payload.get("ai_verified_type", False),
                        title=payload.get("title"),
                        source=payload.get("source"),
                        tags=payload.get("tags", []),
                        confidence=payload.get("confidence", 0.8),
                        vector=None,  # Don't need full vector for display
                        is_valid=payload.get("is_valid", True),
                        created_at=dt.fromisoformat(
                            payload.get("created_at", dt.now(UTC).isoformat())
                        ),
                        expires_at=(
                            dt.fromisoformat(payload["expires_at"])
                            if payload.get("expires_at")
                            else None
                        ),
                        supersedes=payload.get("supersedes"),
                        superseded_by=payload.get("superseded_by"),
                        project_id=payload.get("project_id"),
                        project_name=payload.get("project_name"),
                    )
                    logger.debug(f"Successfully constructed Memory object: {memory.id}")
                except Exception as e:
                    logger.error(f"Failed to construct Memory object from result: {e}")
                    logger.error(f"Result ID: {result.get('id')}, Payload: {payload}")
                    continue  # Skip this result and continue with the next one

                # Create search result
                search_result = SearchResult(
                    memory=memory,
                    score=result.get("score", 0.0),
                    source="qdrant",
                    metadata={"rank": len(results) + 1},
                )

                results.append(search_result)
                logger.debug(
                    f"Found memory: {memory.title or memory.content[:50]}... "
                    f"(score: {search_result.score:.3f})"
                )

            # Sort by score (highest first) and add relevance metadata
            results.sort(key=lambda x: x.score, reverse=True)

            # Add relevance categories to metadata
            for i, result in enumerate(results):
                result.metadata["rank"] = i + 1
                result.metadata["relevance_tier"] = self._get_relevance_tier(result.score)

            logger.info(f"Retrieved {len(results)} memories for query: '{query}'")
            return results

        except Exception as e:
            raise RuntimeError(
                f"CRITICAL: Memory search failed - database connection or query error: {str(e)}"
            ) from e

    async def get_memory_by_id(self, memory_id: str) -> Memory | None:
        """
        Retrieve a specific memory by ID.

        Args:
            memory_id: Unique memory identifier

        Returns:
            Memory object if found, None otherwise
        """
        # Note: get_point method not implemented in current Qdrant interface
        # This would require implementing get_point in QdrantInterface
        logger.warning(
            "get_memory_by_id not yet implemented - requires Qdrant interface enhancement"
        )
        return None

    async def get_memories_by_category(
        self, category: str, user_id: str, limit: int = 20
    ) -> list[Memory]:
        """
        Get all memories in a specific category.

        Args:
            category: Category to filter by
            user_id: User ID for memory isolation
            limit: Maximum number of memories to return

        Returns:
            List of Memory objects in the category
        """
        # Note: filter_points method not implemented in current Qdrant interface
        # For now, we'll do a broad search and filter results
        logger.warning("get_memories_by_category using basic search - filters not yet implemented")

        # Do a general search with a neutral query
        search_results = await self.search_memories(
            query=f"category {category}",
            user_id=user_id,
            limit=limit,
            score_threshold=0.0,  # Lower threshold for category search
        )

        # Filter results by category manually
        filtered_memories = [
            result.memory for result in search_results if result.memory.category == category
        ]

        return filtered_memories

    async def get_stats(self) -> dict:
        """
        Get memory database statistics.

        Returns:
            Dictionary with memory statistics
        """
        try:
            stats = self.qdrant.get_stats()
            return {
                "total_memories": stats.get("points", 0),
                "vector_size": stats.get(
                    "vector_size", int(os.getenv("EMBEDDING_DIMENSION_LEN", "768"))
                ),
                "status": "healthy" if stats else "error",
            }
        except Exception as e:
            raise RuntimeError(
                f"CRITICAL: Failed to get memory stats - database connection error: {str(e)}"
            ) from e

    def _should_filter_invalid_memories(self) -> bool:
        """
        Check if invalid memories should be filtered from search results.

        Returns:
            True if temporal reasoning is enabled and invalid memories should be filtered
        """
        try:
            from ..config import get_config

            config = get_config()
            # Use MEMG configuration
            return config.memg.enable_temporal_reasoning
        except Exception:
            # Default to filtering invalid memories if config fails
            return True

    def _get_relevance_tier(self, score: float) -> str:
        """
        Categorize relevance score into tiers.

        Args:
            score: Similarity score (0.0 to 1.0)

        Returns:
            Relevance tier string
        """
        if score >= 0.9:
            return "highly_relevant"
        if score >= 0.7:
            return "relevant"
        if score >= 0.5:
            return "moderately_relevant"
        if score >= 0.3:
            return "low_relevance"
        return "minimal_relevance"

    # Graph-based search methods for Stage 2
    async def search_by_technology(
        self, tech_name: str, limit: int = 10, user_id: str | None = None
    ) -> list[SearchResult]:
        """
        Find memories that mention specific technologies using graph relationships.

        Args:
            tech_name: Technology name to search for
            limit: Maximum number of results
            user_id: Optional user ID for filtering

        Returns:
            List of search results from memories mentioning the technology
        """
        if not self.graph_enabled:
            logger.warning("Graph search requested but not enabled")
            return []

        try:
            # Determine technology-like entity types dynamically from template categories
            try:
                registry = get_template_registry()
                template = registry.get_current_template()
                tech_types = [
                    et.name
                    for et in (template.entity_types if template else [])
                    if (et.category or "").upper() == "TECHNOLOGY"
                ]
            except Exception:
                tech_types = []

            # Always include standardized technology-related types for visibility
            standard_tech_types = ["TECHNOLOGY", "DATABASE", "LIBRARY", "TOOL", "FRAMEWORK"]
            tech_types = list(dict.fromkeys(tech_types + standard_tech_types))

            # Inline type conditions for test visibility
            type_conditions = " OR ".join([f"e.type = '{t}'" for t in tech_types])
            query = f"""
            MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($tech_name)
              AND ({type_conditions})
            """
            params = {"tech_name": tech_name, "limit": limit}

            if user_id:
                query += " AND m.user_id = $user_id"
                params["user_id"] = user_id

            query += """
            RETURN m.id, m.user_id, m.content, m.title, m.memory_type, m.created_at, e.confidence
            ORDER BY e.confidence DESC, m.created_at DESC
            LIMIT $limit
            """

            results = self.kuzu.query(query, params)
            return await self._convert_kuzu_to_search_results(
                results, source="graph_technology_search"
            )

        except Exception as e:
            logger.error(f"Technology search failed for '{tech_name}': {e}")
            return []

    async def find_error_solutions(
        self, error_description: str, limit: int = 10, user_id: str | None = None
    ) -> list[SearchResult]:
        """
        Find memories containing solutions to similar errors using hybrid search.

        Args:
            error_description: Description of the error to find solutions for
            limit: Maximum number of results
            user_id: Optional user ID for filtering

        Returns:
            List of search results with potential solutions
        """
        if not self.graph_enabled:
            logger.warning("Graph search requested but not enabled")
            return []

        try:
            # Determine error-like and solution-like types from template categories
            try:
                registry = get_template_registry()
                template = registry.get_current_template()
                error_types = [
                    et.name
                    for et in (template.entity_types if template else [])
                    if (et.category or "").upper() == "CRITICAL"
                ]
                solution_types = [
                    et.name
                    for et in (template.entity_types if template else [])
                    if (et.category or "").upper() == "SOLUTION"
                ]
            except Exception:
                error_types = []
                solution_types = []

            # Always include standardized error/solution types for visibility
            error_types = list(dict.fromkeys(error_types + ["ERROR", "ISSUE"]))
            solution_types = list(dict.fromkeys(solution_types + ["SOLUTION", "WORKAROUND"]))

            # First, find memories with relevant entities; inline type conditions for test visibility
            error_type_conditions = " OR ".join([f"e.type = '{t}'" for t in error_types]) or "true"
            solution_type_conditions = (
                " OR ".join([f"e.type = '{t}'" for t in solution_types]) or "true"
            )
            error_query = f"""
            MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
            WHERE (
                    ({error_type_conditions})
                    AND toLower(e.name) CONTAINS toLower($error_description)
                  )
               OR (
                    ({solution_type_conditions})
                    AND toLower(m.content) CONTAINS toLower($error_description)
                  )
            """
            params = {
                "error_description": error_description,
                "limit": limit,
            }

            if user_id:
                error_query += " AND m.user_id = $user_id"
                params["user_id"] = user_id

            error_query += """
            RETURN DISTINCT m.id, m.user_id, m.content, m.title, m.memory_type, m.created_at, e.confidence
            ORDER BY e.confidence DESC, m.created_at DESC
            LIMIT $limit
            """

            results = self.kuzu.query(error_query, params)
            graph_results = await self._convert_kuzu_to_search_results(
                results, source="graph_error_search"
            )

            # Combine with semantic search for better results
            try:
                semantic_results = await self.search_memories(
                    query=error_description + " fix solution",
                    limit=limit // 2,
                    user_id=user_id,
                )

                # Merge and deduplicate results
                all_results = graph_results + semantic_results
                seen_ids = set()
                unique_results = []

                for result in all_results:
                    # Ensure consistent shape: dedupe by memory.id
                    mem = getattr(result, "memory", None)
                    mem_id = getattr(mem, "id", None) if mem is not None else None
                    if not mem_id:
                        # Skip items without a proper memory id
                        continue
                    if mem_id not in seen_ids:
                        seen_ids.add(mem_id)
                        unique_results.append(result)

                return unique_results[:limit]

            except Exception as semantic_error:
                logger.warning(f"Semantic search fallback failed: {semantic_error}")
                return graph_results

        except Exception as e:
            logger.error(f"Error solution search failed: {e}")
            return []

    async def search_by_component(
        self, component_name: str, limit: int = 10, user_id: str | None = None
    ) -> list[SearchResult]:
        """
        Find memories that mention specific components or libraries.

        Args:
            component_name: Component or library name to search for
            limit: Maximum number of results
            user_id: Optional user ID for filtering

        Returns:
            List of search results mentioning the component
        """
        if not self.graph_enabled:
            logger.warning("Graph search requested but not enabled")
            return []

        try:
            # Determine system-like types from template categories
            try:
                registry = get_template_registry()
                template = registry.get_current_template()
                system_types = [
                    et.name
                    for et in (template.entity_types if template else [])
                    if (et.category or "").upper() == "SYSTEM"
                ]
            except Exception:
                system_types = []

            # Always include standardized system-related types for visibility
            system_types = list(
                dict.fromkeys(system_types + ["COMPONENT", "SERVICE", "ARCHITECTURE", "PROTOCOL"])
            )

            type_conditions = " OR ".join([f"e.type = '{t}'" for t in system_types])
            query = f"""
            MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($component_name)
              AND ({type_conditions})
            """
            params = {
                "component_name": component_name,
                "limit": limit,
            }

            if user_id:
                query += " AND m.user_id = $user_id"
                params["user_id"] = user_id

            query += """
            RETURN m.id, m.user_id, m.content, m.title, m.memory_type, m.created_at, e.confidence
            ORDER BY e.confidence DESC, m.created_at DESC
            LIMIT $limit
            """

            results = self.kuzu.query(query, params)
            return await self._convert_kuzu_to_search_results(
                results, source="graph_component_search"
            )

        except Exception as e:
            logger.error(f"Component search failed for '{component_name}': {e}")
            return []

    async def _convert_kuzu_to_search_results(
        self, kuzu_results: list[dict], source: str = "graph_search"
    ) -> list[SearchResult]:
        """
        Convert Kuzu query results to SearchResult objects.

        Args:
            kuzu_results: Raw results from Kuzu query
            source: Source identifier for the search

        Returns:
            List of SearchResult objects
        """
        search_results = []

        for result in kuzu_results:
            try:
                # Build Memory object from Kuzu row
                raw_memory_type = result.get("m.memory_type", "note")
                try:
                    memory_type = MemoryType(raw_memory_type)
                except ValueError:
                    memory_type = MemoryType.NOTE

                created_at_raw = result.get("m.created_at")
                created_at = dt.fromisoformat(created_at_raw) if created_at_raw else dt.now(UTC)

                memory = Memory(
                    id=result.get("m.id"),
                    user_id=result.get("m.user_id", ""),
                    content=result.get("m.content", ""),
                    memory_type=memory_type,
                    summary=result.get("m.summary"),
                    title=result.get("m.title"),
                    source=result.get("m.source", ""),
                    tags=(result.get("m.tags", "").split(",") if result.get("m.tags") else []),
                    confidence=float(result.get("m.confidence", 0.8)),
                    is_valid=True,
                    created_at=created_at,
                )

                confidence = result.get("entity_confidence")
                if confidence is None:
                    confidence = result.get("e.confidence", 0.8)
                search_result = SearchResult(
                    memory=memory,
                    score=float(confidence),
                    source=source,
                    metadata={},
                )

                search_results.append(search_result)

            except Exception as e:
                logger.warning(f"Failed to convert Kuzu result to SearchResult: {e}")
                continue

        return search_results

    async def graph_search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 10,
        user_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Generic graph search over entities mentioned in memories.

        Args:
            query: Search query text to match against entity names
            entity_types: Optional list of entity types to filter by
            limit: Maximum number of results to return
            user_id: Optional user ID for filtering

        Returns:
            List of SearchResult objects from graph search
        """
        if not self.graph_enabled:
            logger.warning("Graph search requested but not enabled")
            return []

        try:
            # Build Cypher query with optional filters
            cypher_query = """
            MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($query)
            """
            params = {"query": query, "limit": limit}

            # Add entity type filter if provided
            if entity_types:
                type_conditions = [
                    f"e.type = '{entity_type.upper()}'" for entity_type in entity_types
                ]
                cypher_query += f" AND ({' OR '.join(type_conditions)})"

            # Add user filter if provided
            if user_id:
                cypher_query += " AND m.user_id = $user_id"
                params["user_id"] = user_id

            cypher_query += """
            RETURN DISTINCT m.id, m.user_id, m.content, m.title, m.memory_type,
                   m.created_at, m.summary, m.source, m.tags, m.confidence, e.confidence as entity_confidence
            ORDER BY e.confidence DESC, m.created_at DESC
            LIMIT $limit
            """

            logger.info(
                f"Executing graph search for query: '{query}' with entity_types: {entity_types}"
            )
            results = self.kuzu.query(cypher_query, params)

            return await self._convert_kuzu_to_search_results(results, source="graph_search")

        except Exception as e:
            logger.error(f"Graph search failed for query '{query}': {e}")
            return []
