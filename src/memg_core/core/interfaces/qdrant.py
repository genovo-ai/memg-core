"""Pure CRUD Qdrant interface wrapper - NO DDL operations."""

from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
)

from ..exceptions import DatabaseError


class QdrantInterface:
    """Pure CRUD wrapper around QdrantClient - NO DDL operations.

    Attributes:
        client: Pre-initialized QdrantClient.
        collection_name: Name of the Qdrant collection.
    """

    def __init__(self, client: QdrantClient, collection_name: str):
        """Initialize with pre-created client and collection.

        Args:
            client: Pre-initialized QdrantClient from DatabaseClients.
            collection_name: Name of pre-created collection.
        """
        self.client = client
        self.collection_name = collection_name

    def add_point(
        self,
        vector: list[float],
        payload: dict[str, Any],
        point_id: str | None = None,
        collection: str | None = None,
    ) -> tuple[bool, str]:
        """Add a single point to collection - pure CRUD operation.

        Args:
            vector: Embedding vector.
            payload: Point payload data.
            point_id: Optional point ID (auto-generated if None).
            collection: Optional collection name override.

        Returns:
            tuple[bool, str]: (success, point_id) where success indicates if operation succeeded.

        Raises:
            DatabaseError: If point addition fails.
        """
        try:
            collection = collection or self.collection_name

            if point_id is None:
                point_id = str(uuid.uuid4())

            # Create PointStruct with VectorStruct
            point = PointStruct(id=point_id, vector=vector, payload=payload)
            result = self.client.upsert(collection_name=collection, points=[point])

            # print("Qdrant result", result)

            # Determine success from returned UpdateResult status
            success = True
            status = getattr(result, "status", None)
            if status is not None:
                status_str = (
                    getattr(status, "value", None) or getattr(status, "name", None) or str(status)
                )
                status_str = str(status_str).lower()
                success = status_str in ("acknowledged", "completed")

            return success, point_id

        except Exception as e:
            raise DatabaseError(
                "Qdrant add_point error",
                operation="add_point",
                original_error=e,
            ) from e

    def search_points(
        self,
        vector: list[float],
        limit: int = 5,
        collection: str | None = None,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar points with mandatory user isolation - pure CRUD operation.

        Args:
            vector: Query embedding vector.
            limit: Maximum number of results.
            collection: Optional collection name override.
            filters: Search filters (must include user_id for security).
            score_threshold: Minimum similarity score threshold (0.0-1.0).

        Returns:
            list[dict[str, Any]]: List of search results with id, score, and payload.

        Raises:
            DatabaseError: If search fails or user_id is missing from filters.
        """
        try:
            # CRITICAL SECURITY: Validate user_id is present in filters
            if not filters or "user_id" not in filters:
                raise DatabaseError(
                    "user_id is mandatory in filters for data isolation",
                    operation="search_points_validation",
                    context={"filters": filters},
                )

            user_id = filters["user_id"]
            if not user_id or not isinstance(user_id, str) or not user_id.strip():
                raise DatabaseError(
                    "user_id must be a non-empty string",
                    operation="search_points_validation",
                    context={"user_id": user_id},
                )

            collection = collection or self.collection_name

            # Build query filter
            query_filter = None
            filter_conditions = []

            # Add user_id filter - flat payload structure (always required)
            filter_conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))

            # Add additional filters (skip user_id since it's already added)
            for key, value in filters.items():
                if key == "user_id" or value is None:
                    continue
                # Handle range filters
                if isinstance(value, dict):
                    range_kwargs = {}
                    for bound_key in ("gt", "gte", "lt", "lte"):
                        if bound_key in value and value[bound_key] is not None:
                            range_kwargs[bound_key] = value[bound_key]
                    if range_kwargs:
                        filter_conditions.append(
                            FieldCondition(key=key, range=Range(**range_kwargs))
                        )
                        continue
                # Handle list values
                if isinstance(value, list):
                    filter_conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
                elif not isinstance(value, dict):  # Skip dict values that weren't handled as ranges
                    filter_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

            if filter_conditions:
                # Use type ignore for the Filter argument type mismatch
                query_filter = Filter(must=filter_conditions)  # type: ignore

            # Search using modern API
            results = self.client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
            ).points

            # Convert to simplified results (score_threshold already applied by Qdrant)
            return [
                {
                    "id": str(result.id),
                    "score": result.score,
                    "payload": result.payload,
                }
                for result in results
            ]

        except Exception as e:
            raise DatabaseError(
                "Qdrant search_points error",
                operation="search_points",
                original_error=e,
            ) from e

    def get_point(self, point_id: str, collection: str | None = None) -> dict[str, Any] | None:
        """Get a single point by ID - pure CRUD operation.

        Args:
            point_id: ID of the point to retrieve.
            collection: Optional collection name override.

        Returns:
            dict[str, Any] | None: Point data including id, vector, and payload, or None if not found.

        Raises:
            DatabaseError: If retrieval fails.
        """
        try:
            collection = collection or self.collection_name

            result = self.client.retrieve(
                collection_name=collection,
                ids=[point_id],
            )

            if result:
                point = result[0]
                return {
                    "id": str(point.id),
                    "vector": point.vector,
                    "payload": point.payload,
                }
            return None
        except Exception as e:
            raise DatabaseError(
                "Qdrant get_point error",
                operation="get_point",
                original_error=e,
            ) from e

    def delete_points(
        self, point_ids: list[str], user_id: str, collection: str | None = None
    ) -> bool:
        """Delete points by IDs with user ownership verification.

        Args:
            point_ids: List of point IDs to delete.
            user_id: User ID for ownership verification.
            collection: Optional collection name override.

        Returns:
            bool: True if deletion succeeded.

        Raises:
            DatabaseError: If points not found or don't belong to user, or deletion fails.
        """
        try:
            collection = collection or self.collection_name

            # CRITICAL: Verify user ownership before deletion
            # First, verify all points belong to the user
            for point_id in point_ids:
                points = self.client.retrieve(
                    collection_name=collection, ids=[point_id], with_payload=True
                )

                if not points or not (
                    points[0].payload and points[0].payload.get("user_id") == user_id
                ):
                    raise DatabaseError(
                        f"Point {point_id} not found or doesn't belong to user {user_id}",
                        operation="delete_points",
                        context={"point_id": point_id, "user_id": user_id},
                    )

            # If all points belong to user, proceed with deletion
            self.client.delete(
                collection_name=collection,
                points_selector=PointIdsList(points=[str(pid) for pid in point_ids]),
            )
            return True
        except Exception as e:
            raise DatabaseError(
                "Qdrant delete_points error",
                operation="delete_points",
                original_error=e,
            ) from e

    def get_collection_info(self, collection: str | None = None) -> dict[str, Any]:
        """Get collection information - pure read operation.

        Args:
            collection: Optional collection name override.

        Returns:
            dict[str, Any]: Collection information including existence, vector count, point count, and config.

        Raises:
            DatabaseError: If collection info retrieval fails.
        """
        try:
            collection = collection or self.collection_name

            info = self.client.get_collection(collection_name=collection)
            # Handle different types of vector params
            vector_size = None
            vector_distance = None

            vectors_param = info.config.params.vectors
            if vectors_param is not None:
                if hasattr(vectors_param, "size"):
                    vector_size = vectors_param.size  # type: ignore
                    vector_distance = vectors_param.distance  # type: ignore
                elif isinstance(vectors_param, dict):
                    # For multi-vector collections, use the first vector's params
                    if vectors_param:
                        vector_values = list(vectors_param.values())
                        if vector_values:
                            first_vector = vector_values[0]
                            vector_size = first_vector.size
                            vector_distance = first_vector.distance

            return {
                "exists": True,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "config": {
                    "vector_size": vector_size,
                    "distance": vector_distance,
                },
            }
        except Exception as e:
            raise DatabaseError(
                "Qdrant get_collection_info error",
                operation="get_collection_info",
                original_error=e,
            ) from e
