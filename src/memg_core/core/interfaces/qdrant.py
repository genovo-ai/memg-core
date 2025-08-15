"""Simple Qdrant interface wrapper - pure I/O operations only"""

import os
from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    Range,
    VectorParams,
)

from memg_core.core.config import get_config
from memg_core.core.exceptions import DatabaseError


class QdrantInterface:
    """Simple wrapper around QdrantClient - CRUD and search only"""

    def __init__(self, collection_name: str = "memories", storage_path: str | None = None):
        # Use provided storage path or read from env
        if storage_path is None:
            storage_path = os.getenv("QDRANT_STORAGE_PATH")
            if not storage_path:
                raise DatabaseError(
                    "QDRANT_STORAGE_PATH environment variable must be set! No defaults allowed.",
                    operation="__init__",
                )

        # Expand $HOME and ensure directory exists
        storage_path = os.path.expandvars(storage_path)
        os.makedirs(storage_path, exist_ok=True)

        self.client = QdrantClient(path=storage_path)
        self.collection_name = collection_name

        # Get vector dimension from config instead of hardcoding
        config = get_config()
        self.vector_dimension = config.memg.vector_dimension

    def collection_exists(self, collection: str | None = None) -> bool:
        """Check if collection exists"""
        try:
            collection = collection or self.collection_name
            collections = self.client.get_collections()
            return any(col.name == collection for col in collections.collections)

        except Exception as e:
            raise DatabaseError(
                "Qdrant collection_exists error",
                operation="collection_exists",
                original_error=e,
            )

    def create_collection(
        self, collection: str | None = None, vector_size: int | None = None
    ) -> bool:
        """Create a new collection"""
        try:
            collection = collection or self.collection_name
            vector_size = vector_size or self.vector_dimension
            if self.collection_exists(collection):
                return True  # Already exists

            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            return True

        except Exception as e:
            raise DatabaseError(
                "Qdrant create_collection error",
                operation="create_collection",
                original_error=e,
            )

    def ensure_collection(
        self, collection: str | None = None, vector_size: int | None = None
    ) -> bool:
        """Ensure collection exists, create if it doesn't"""
        collection = collection or self.collection_name
        if not self.collection_exists(collection):
            return self.create_collection(collection, vector_size)
        return True

    def add_point(
        self,
        vector: list[float],
        payload: dict[str, Any],
        point_id: str | None = None,
        collection: str | None = None,
    ) -> tuple[bool, str]:
        """Add a single point to collection"""
        try:
            collection = collection or self.collection_name
            self.ensure_collection(collection, len(vector))

            if point_id is None:
                point_id = str(uuid.uuid4())
            elif not isinstance(point_id, str):
                point_id = str(point_id)

            point = PointStruct(id=point_id, vector=vector, payload=payload)
            result = self.client.upsert(collection_name=collection, points=[point])

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
        """Search for similar points with optional filtering"""
        try:
            collection = collection or self.collection_name

            if not self.collection_exists(collection):
                self.ensure_collection(collection)

            # Build query filter
            query_filter = None
            filter_conditions = []

            if user_id or filters:
                # Add user_id filter - no hardcoded path assumptions
                if user_id:
                    filter_conditions.append(
                        FieldCondition(key="core.user_id", match=MatchValue(value=user_id))
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
        """Get a single point by ID"""
        try:
            collection = collection or self.collection_name

            if not self.collection_exists(collection):
                return None

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
        """Delete points by IDs"""
        try:
            collection = collection or self.collection_name

            if not self.collection_exists(collection):
                return True  # Nothing to delete

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
        """Get collection information"""
        try:
            collection = collection or self.collection_name

            if not self.collection_exists(collection):
                return {"exists": False}

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
