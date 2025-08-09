#!/usr/bin/env python3
"""
Graph Database Validation Tools for MEMG GraphRAG Stage 1
Validates entity storage, coding entities, and relationships in Kuzu
"""

import logging
from typing import Any, Dict, Optional

from ..kuzu_graph.interface import KuzuInterface
from ..logging_config import get_logger

logger = get_logger("graph_validator")


class GraphValidator:
    """
    Validator for GraphRAG Stage 1 - Entity extraction and graph storage
    """

    def __init__(self, kuzu_interface: Optional[KuzuInterface] = None):
        """
        Initialize the Graph Validator.

        Args:
            kuzu_interface: Optional Kuzu interface (creates new one if not provided)
        """
        self.kuzu = kuzu_interface or KuzuInterface()
        logger.info("GraphValidator initialized")

    def validate_entity_storage(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """
        Verify entities are being stored correctly in Kuzu

        Args:
            user_id: Optional user ID to filter results

        Returns:
            Dictionary with entity count statistics
        """
        try:
            # Build query with optional user filtering
            if user_id:
                query = "MATCH (e:Entity {user_id: $user_id}) RETURN count(e) as entity_count"
                params = {"user_id": user_id}
            else:
                query = "MATCH (e:Entity) RETURN count(e) as entity_count"
                params = {}

            results = self.kuzu.query(query, params)
            entity_count = results[0]["entity_count"] if results else 0

            logger.info(f"Entity storage validation: {entity_count} entities found")
            return {"entity_count": entity_count}

        except Exception as e:
            logger.error(f"Entity storage validation failed: {e}")
            return {"entity_count": 0, "error": str(e)}

    def validate_coding_entities(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify coding-specific entities are captured correctly

        Args:
            user_id: Optional user ID to filter results

        Returns:
            Dictionary with coding entity statistics
        """
        try:
            # Common coding entity types
            coding_types = {
                "technology": "MATCH (e:Entity {type: 'technology'}) RETURN count(e) as count",
                "error": "MATCH (e:Entity {type: 'error'}) RETURN count(e) as count",
                "solution": "MATCH (e:Entity {type: 'solution'}) RETURN count(e) as count",
                "component": "MATCH (e:Entity {type: 'component'}) RETURN count(e) as count",
                "library": "MATCH (e:Entity {type: 'library'}) RETURN count(e) as count",
                "framework": "MATCH (e:Entity {type: 'framework'}) RETURN count(e) as count",
            }

            results = {}
            for entity_type, base_query in coding_types.items():
                # Add user filtering if specified
                if user_id:
                    query = base_query.replace(
                        "Entity {type:",
                        f"Entity {{type: '{entity_type}', user_id: $user_id",
                    )
                    params = {"user_id": user_id}
                else:
                    query = base_query
                    params = {}

                try:
                    result = self.kuzu.query(query, params)
                    results[entity_type] = result[0]["count"] if result else 0
                except Exception as e:
                    logger.warning(f"Failed to query {entity_type} entities: {e}")
                    results[entity_type] = 0

            total_coding_entities = sum(results.values())
            logger.info(
                f"Coding entities validation: {total_coding_entities} total coding entities"
            )

            results["total_coding_entities"] = total_coding_entities
            return results

        except Exception as e:
            logger.error(f"Coding entities validation failed: {e}")
            return {"error": str(e)}

    def validate_relationships(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """
        Verify relationships are being created between entities

        Args:
            user_id: Optional user ID to filter results

        Returns:
            Dictionary with relationship count statistics
        """
        try:
            # Count all relationships
            if user_id:
                query = (
                    "MATCH ()-[r {user_id: $user_id}]->() RETURN count(r) as rel_count"
                )
                params = {"user_id": user_id}
            else:
                query = "MATCH ()-[r]->() RETURN count(r) as rel_count"
                params = {}

            results = self.kuzu.query(query, params)
            rel_count = results[0]["rel_count"] if results else 0

            logger.info(f"Relationships validation: {rel_count} relationships found")
            return {"relationship_count": rel_count}

        except Exception as e:
            logger.error(f"Relationships validation failed: {e}")
            return {"relationship_count": 0, "error": str(e)}

    def validate_memory_entity_connections(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify memories are properly connected to entities

        Args:
            user_id: Optional user ID to filter results

        Returns:
            Dictionary with connection statistics
        """
        try:
            # Count memories with entities
            if user_id:
                query = """
                MATCH (m:Memory {user_id: $user_id})-[:MENTIONS]->(e:Entity)
                RETURN count(DISTINCT m) as memories_with_entities, count(e) as total_connections
                """
                params = {"user_id": user_id}
            else:
                query = """
                MATCH (m:Memory)-[:MENTIONS]->(e:Entity)
                RETURN count(DISTINCT m) as memories_with_entities, count(e) as total_connections
                """
                params = {}

            results = self.kuzu.query(query, params)

            if results:
                memories_with_entities = results[0]["memories_with_entities"]
                total_connections = results[0]["total_connections"]
            else:
                memories_with_entities = 0
                total_connections = 0

            # Count total memories for comparison
            if user_id:
                total_query = (
                    "MATCH (m:Memory {user_id: $user_id}) RETURN count(m) as total_memories"
                )
                total_params = {"user_id": user_id}
            else:
                total_query = "MATCH (m:Memory) RETURN count(m) as total_memories"
                total_params = {}

            total_results = self.kuzu.query(total_query, total_params)
            total_memories = total_results[0]["total_memories"] if total_results else 0

            connection_rate = (
                (memories_with_entities / total_memories * 100)
                if total_memories > 0
                else 0
            )

            logger.info(
                f"Memory-entity connections: {memories_with_entities}/{total_memories} "
                f"memories have entities ({connection_rate:.1f}%)"
            )

            return {
                "memories_with_entities": memories_with_entities,
                "total_memories": total_memories,
                "total_connections": total_connections,
                "connection_rate_percent": round(connection_rate, 1),
            }

        except Exception as e:
            logger.error(f"Memory-entity connections validation failed: {e}")
            return {"error": str(e)}

    def run_comprehensive_validation(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run all validation checks and return comprehensive report

        Args:
            user_id: Optional user ID to filter results

        Returns:
            Complete validation report
        """
        logger.info(
            f"Running comprehensive GraphRAG validation for user: {user_id or 'all'}"
        )

        report = {
            "user_id": user_id,
            "timestamp": logging.Formatter().formatTime(
                logging.LogRecord("", 0, "", 0, "", (), None)
            ),
            "validation_results": {},
        }

        # Run all validation checks
        report["validation_results"]["entity_storage"] = self.validate_entity_storage(
            user_id
        )
        report["validation_results"]["coding_entities"] = self.validate_coding_entities(
            user_id
        )
        report["validation_results"]["relationships"] = self.validate_relationships(
            user_id
        )
        report["validation_results"]["memory_connections"] = (
            self.validate_memory_entity_connections(user_id)
        )

        # Calculate overall health score
        health_score = self._calculate_health_score(report["validation_results"])
        report["overall_health_score"] = health_score

        logger.info(
            f"Comprehensive validation complete. Health score: {health_score}/100"
        )
        return report

    def _calculate_health_score(self, results: Dict[str, Any]) -> int:
        """
        Calculate overall health score based on validation results

        Args:
            results: Validation results dictionary

        Returns:
            Health score from 0-100
        """
        score = 0
        max_score = 100

        # Entity storage (25 points)
        entity_count = results.get("entity_storage", {}).get("entity_count", 0)
        if entity_count > 0:
            score += 25

        # Coding entities (25 points)
        coding_entities = results.get("coding_entities", {}).get(
            "total_coding_entities", 0
        )
        if coding_entities > 0:
            score += 25

        # Relationships (25 points)
        rel_count = results.get("relationships", {}).get("relationship_count", 0)
        if rel_count > 0:
            score += 25

        # Memory connections (25 points)
        connection_rate = results.get("memory_connections", {}).get(
            "connection_rate_percent", 0
        )
        if connection_rate > 0:
            score += min(
                25, int(connection_rate / 4)
            )  # Up to 25 points for 100% connection rate

        return min(score, max_score)
