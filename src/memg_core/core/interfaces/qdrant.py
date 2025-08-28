"""Pure CRUD Qdrant interface wrapper - NO DDL operations"""

from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    Range,
)

from ..exceptions import DatabaseError


class QdrantInterface:
    """Pure CRUD wrapper around QdrantClient - NO DDL operations"""

    def __init__(self, client: QdrantClient, collection_name: str):
        """Initialize with pre-created client and collection.

        Args:
            client: Pre-initialized QdrantClient from DatabaseClients
            collection_name: Name of pre-created collection
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
        """Add a single point to collection - pure CRUD operation"""
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
            )

    def search_points(
        self,
        vector: list[float],
        limit: int = 5,
        collection: str | None = None,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar points with optional filtering - pure CRUD operation"""
        try:
            collection = collection or self.collection_name

            # Build query filter
            query_filter = None
            filter_conditions = []

            if user_id or filters:
                # Add user_id filter - flat payload structure
                # TODO: Consider making this field path configurable
                if user_id:
                    filter_conditions.append(
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    )

                # Add additional filters
                if filters:
                    for key, value in filters.items():
                        if value is None:
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
                            filter_conditions.append(
                                FieldCondition(key=key, match=MatchAny(any=value))
                            )
                        elif not isinstance(
                            value, dict
                        ):  # Skip dict values that weren't handled as ranges
                            filter_conditions.append(
                                FieldCondition(key=key, match=MatchValue(value=value))
                            )

                if filter_conditions:
                    # Use type ignore for the Filter argument type mismatch
                    query_filter = Filter(must=filter_conditions)  # type: ignore

            # Search using modern API
            results = self.client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                query_filter=query_filter,
            ).points

            # print("Qdrant results", results)

            # Convert to simplified results
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
            )

    def get_point(self, point_id: str, collection: str | None = None) -> dict[str, Any] | None:
        """Get a single point by ID - pure CRUD operation"""
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
            )

    def delete_points(self, point_ids: list[str], collection: str | None = None) -> bool:
        """Delete points by IDs - pure CRUD operation"""
        try:
            collection = collection or self.collection_name

            from qdrant_client.models import PointIdsList

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
            )

    def get_collection_info(self, collection: str | None = None) -> dict[str, Any]:
        """Get collection information - pure read operation"""
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
            )
