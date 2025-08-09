#!/usr/bin/env python3
"""Simple Qdrant interface wrapper"""

import os
from typing import Any
import uuid

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ..exceptions import DatabaseError, NetworkError, StorageError
from ..logging_config import log_error


class QdrantInterface:
    """Simple wrapper around QdrantClient"""

    def __init__(self, host: str = None, port: int = None, collection_name: str = None):
        # Load environment variables
        load_dotenv()

        # Use .env values or defaults
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        self.collection_name = collection_name or os.getenv(
            "QDRANT_COLLECTION", "memory_collection"
        )

        # Use file-based storage - CRASH if no env variable set
        storage_path = os.getenv("QDRANT_STORAGE_PATH")
        if not storage_path:
            raise RuntimeError(
                "QDRANT_STORAGE_PATH environment variable must be set! No defaults allowed."
            )

        # Expand $HOME and ensure directory exists
        storage_path = os.path.expandvars(storage_path)
        os.makedirs(storage_path, exist_ok=True)
        self.client = QdrantClient(path=storage_path)

    def collection_exists(self, collection: str = None) -> bool:
        """Check if collection exists"""
        try:
            collection = collection or self.collection_name
            collections = self.client.get_collections()
            return any(col.name == collection for col in collections.collections)
        except (ConnectionError, TimeoutError) as e:
            log_error("qdrant_interface", "collection_exists", e, collection=collection)
            raise NetworkError(
                "Failed to connect to Qdrant",
                operation="collection_exists",
                original_error=e,
            )
        except Exception as e:
            log_error("qdrant_interface", "collection_exists", e, collection=collection)
            raise DatabaseError(
                "Critical Qdrant collection_exists error",
                operation="collection_exists",
                original_error=e,
            )

    def create_collection(self, collection: str = None, vector_size: int = 768) -> bool:
        """Create a new collection"""
        try:
            collection = collection or self.collection_name
            if self.collection_exists(collection):
                return True  # Already exists

            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            return True
        except (ConnectionError, TimeoutError) as e:
            log_error(
                "qdrant_interface",
                "create_collection",
                e,
                collection=collection,
                vector_size=vector_size,
            )
            raise NetworkError(
                "Failed to connect to Qdrant for collection creation",
                operation="create_collection",
                original_error=e,
            )
        except PermissionError as e:
            log_error(
                "qdrant_interface",
                "create_collection",
                e,
                collection=collection,
                vector_size=vector_size,
            )
            raise StorageError(
                "Permission denied creating collection",
                operation="create_collection",
                original_error=e,
            )
        except Exception as e:
            log_error(
                "qdrant_interface",
                "create_collection",
                e,
                collection=collection,
                vector_size=vector_size,
            )
            raise DatabaseError(
                "Critical Qdrant create_collection error",
                operation="create_collection",
                original_error=e,
            )

    def delete_collection(self, collection: str = None) -> bool:
        """Delete a collection"""
        try:
            collection = collection or self.collection_name
            if not self.collection_exists(collection):
                return True  # Already doesn't exist

            self.client.delete_collection(collection_name=collection)
            return True
        except (ConnectionError, TimeoutError) as e:
            log_error("qdrant_interface", "delete_collection", e, collection=collection)
            raise NetworkError(
                "Failed to connect to Qdrant for collection deletion",
                operation="delete_collection",
                original_error=e,
            )
        except PermissionError as e:
            log_error("qdrant_interface", "delete_collection", e, collection=collection)
            raise StorageError(
                "Permission denied deleting collection",
                operation="delete_collection",
                original_error=e,
            )
        except Exception as e:
            log_error("qdrant_interface", "delete_collection", e, collection=collection)
            raise DatabaseError(
                "Critical Qdrant delete_collection error",
                operation="delete_collection",
                original_error=e,
            )

    def ensure_collection(self, collection: str = None, vector_size: int = 768) -> bool:
        """Ensure collection exists, create if it doesn't"""
        collection = collection or self.collection_name
        if not self.collection_exists(collection):
            return self.create_collection(collection, vector_size)
        return True

    def add_point(
        self,
        vector: list[float],
        payload: dict[str, Any],
        point_id: str = None,
        collection: str = None,
    ) -> tuple[bool, str]:
        """Add a single point to collection"""
        try:
            # Use default collection if not specified
            collection = collection or self.collection_name

            # Ensure collection exists
            self.ensure_collection(collection, len(vector))

            # Ensure point_id is a valid UUID string
            if point_id is None:
                point_id = str(uuid.uuid4())
            elif not isinstance(point_id, str):
                point_id = str(point_id)

            point = PointStruct(id=point_id, vector=vector, payload=payload)
            result = self.client.upsert(collection_name=collection, points=[point])

            # Determine success from returned UpdateResult status when available
            success = True
            try:
                status = getattr(result, "status", None)
                # status may be an enum; prefer its value/name, fall back to string
                if status is not None:
                    status_str = (
                        getattr(status, "value", None)
                        or getattr(status, "name", None)
                        or str(status)
                    )
                    status_str = str(status_str).lower()
                    success = status_str in ("acknowledged", "completed")
            except Exception:
                # If anything goes wrong determining status, assume success if no exception raised
                success = True

            return success, point_id
        except (ConnectionError, TimeoutError) as e:
            log_error(
                "qdrant_interface",
                "add_point",
                e,
                collection=collection,
                vector_size=len(vector),
                point_id=point_id,
            )
            raise NetworkError(
                "Failed to connect to Qdrant for point insertion",
                operation="add_point",
                original_error=e,
            )
        except ValueError as e:
            log_error(
                "qdrant_interface",
                "add_point",
                e,
                collection=collection,
                vector_size=len(vector),
                point_id=point_id,
            )
            raise DatabaseError(
                "Invalid vector data for point insertion",
                operation="add_point",
                original_error=e,
            )
        except Exception as e:
            # CRASH on critical errors - don't hide database problems!
            log_error(
                "qdrant_interface",
                "add_point",
                e,
                collection=collection,
                vector_size=len(vector),
                point_id=point_id,
            )
            raise DatabaseError(
                "Critical Qdrant add_point error",
                operation="add_point",
                original_error=e,
            )

    def search_points(
        self,
        vector: list[float],
        limit: int = 5,
        collection: str = None,
        user_id: str = None,
        filters: dict[str, Any] = None,
    ) -> list[dict[str, Any]]:
        """Search for similar points with optional user_id filtering"""
        try:
            # Use default collection if not specified
            collection = collection or self.collection_name

            # Ensure collection exists
            if not self.collection_exists(collection):
                # Auto-create collection with default vector size
                self.ensure_collection(collection, 768)  # Default to Google AI embedding size

            # Build query filter combining user_id and additional filters (including ranges)
            query_filter = None
            filter_conditions = []

            if user_id or filters:
                from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

                # Add user_id filter
                if user_id:
                    filter_conditions.append(
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    )

                # Add additional filters
                if filters:
                    for key, value in filters.items():
                        if value is None:
                            continue
                        # Special handling for created_at lower bound (e.g., days_back)
                        if key == "created_at" and isinstance(value, str):
                            # Use Range gte for ISO timestamps
                            filter_conditions.append(
                                FieldCondition(key="created_at", range=Range(gte=value))
                            )
                            continue
                        # Handle list values (like entity_types) with MatchAny
                        if isinstance(value, list):
                            from qdrant_client.models import MatchAny

                            filter_conditions.append(
                                FieldCondition(key=key, match=MatchAny(any=value))
                            )
                        else:
                            filter_conditions.append(
                                FieldCondition(key=key, match=MatchValue(value=value))
                            )

                # Create combined filter
                if filter_conditions:
                    query_filter = Filter(must=filter_conditions)

            results = self.client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                with_payload=True,
                query_filter=query_filter,
            )
            return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]
        except (ConnectionError, TimeoutError) as e:
            log_error(
                "qdrant_interface",
                "search_points",
                e,
                collection=collection,
                vector_size=len(vector),
                limit=limit,
            )
            raise NetworkError(
                "Failed to connect to Qdrant for search",
                operation="search_points",
                original_error=e,
            )
        except ValueError as e:
            log_error(
                "qdrant_interface",
                "search_points",
                e,
                collection=collection,
                vector_size=len(vector),
                limit=limit,
            )
            raise DatabaseError(
                "Invalid search vector data",
                operation="search_points",
                original_error=e,
            )
        except Exception as e:
            # CRASH on critical errors - don't hide database problems!
            log_error(
                "qdrant_interface",
                "search_points",
                e,
                collection=collection,
                vector_size=len(vector),
                limit=limit,
            )
            raise DatabaseError(
                "Critical Qdrant search error",
                operation="search_points",
                original_error=e,
            )

    def get_stats(self, collection: str = None) -> dict[str, Any]:
        """Get collection statistics"""
        try:
            # Use default collection if not specified
            collection = collection or self.collection_name

            if not self.collection_exists(collection):
                return {"points": 0, "vector_size": 0, "exists": False}

            info = self.client.get_collection(collection)
            return {
                "points": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "exists": True,
            }
        except (ConnectionError, TimeoutError) as e:
            log_error("qdrant_interface", "get_stats", e, collection=collection)
            raise NetworkError(
                "Failed to connect to Qdrant for stats",
                operation="get_stats",
                original_error=e,
            )
        except Exception as e:
            log_error("qdrant_interface", "get_stats", e, collection=collection)
            raise DatabaseError(
                "Critical Qdrant get_stats error",
                operation="get_stats",
                original_error=e,
            )

    def update_point_payload(
        self, point_id: str, payload: dict[str, Any], collection: str = None
    ) -> bool:
        """Update the payload of an existing point"""
        try:
            collection = collection or self.collection_name

            # Ensure collection exists
            if not self.collection_exists(collection):
                return False

            # Update the point payload
            self.client.set_payload(collection_name=collection, payload=payload, points=[point_id])

            return True

        except Exception as e:
            log_error(
                "qdrant_interface",
                "update_point_payload",
                e,
                collection=collection,
                point_id=point_id,
            )
            return False
