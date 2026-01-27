"""
Qdrant service module.

Handles all interactions with Qdrant vector database.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple, cast
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)

from .config import settings

# Namespace UUID for generating deterministic UUIDs from string IDs
NAMESPACE_UUID = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def str_to_uuid(s: str) -> str:
    """Convert string ID to deterministic UUID string."""
    return str(uuid.uuid5(NAMESPACE_UUID, s))


class QdrantService:
    """Service for Qdrant operations."""

    def __init__(self):
        """Initialize Qdrant client."""
        self._client: Optional[AsyncQdrantClient] = None

    @property
    def client(self) -> AsyncQdrantClient:
        """Lazy initialization of async client."""
        if self._client is None:
            self._client = AsyncQdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key,
                https=settings.qdrant_https,
            )
        return self._client

    async def ensure_collections(self) -> None:
        """Create collections if they don't exist."""
        collections = await self.client.get_collections()
        existing = {c.name for c in collections.collections}

        all_collections = [
            settings.knowledge_collection,
            settings.skills_collection,
            settings.projects_collection,
            settings.private_collection,
        ]

        for collection_name in all_collections:
            if collection_name not in existing:
                await self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=settings.vector_size, distance=Distance.COSINE
                    ),
                )

                # Create payload indexes for filtering
                await self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="tags",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )

                if collection_name == settings.knowledge_collection:
                    await self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="knowledge_type",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

                if collection_name == settings.skills_collection:
                    await self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="name",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

                if collection_name == settings.projects_collection:
                    await self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="name",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    await self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="status",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

                if collection_name == settings.private_collection:
                    await self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="private_type",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )

    def _build_filter(self, filters: Dict[str, Any]) -> Optional[Filter]:
        """Build Qdrant filter from dict."""
        if not filters:
            return None

        conditions = []

        for key, value in filters.items():
            if key == "tags" and isinstance(value, list):
                # Match all specified tags (AND logic)
                for tag in value:
                    conditions.append(FieldCondition(key="tags", match=MatchAny(any=[tag])))
            elif isinstance(value, list):
                conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        if not conditions:
            return None

        return Filter(must=cast(Any, conditions))

    async def search(
        self,
        collection: str,
        vector: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            collection: Collection name
            vector: Query vector
            limit: Max results
            filters: Optional filters
            score_threshold: Minimum similarity score

        Returns:
            List of matching documents with scores
        """
        query_filter = self._build_filter(filters) if filters else None

        results = await self.client.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [{**(point.payload or {}), "score": point.score} for point in results.points]

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: Optional[List[float]],
        payload: Dict[str, Any],
        update_vector: bool = True,
    ) -> None:
        """
        Insert or update a point.

        Args:
            collection: Collection name
            id: Point ID
            vector: Vector (optional if update_vector=False)
            payload: Payload data
            update_vector: Whether to update vector
        """
        point_id = str_to_uuid(id)
        if update_vector and vector is not None:
            await self.client.upsert(
                collection_name=collection,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
        else:
            # Update payload only
            await self.client.set_payload(
                collection_name=collection, payload=payload, points=[point_id]
            )

    async def get_by_id(self, collection: str, id: str) -> Optional[Dict[str, Any]]:
        """
        Get a point by ID.

        Args:
            collection: Collection name
            id: Point ID

        Returns:
            Point payload or None if not found
        """
        try:
            point_id = str_to_uuid(id)
            results = await self.client.retrieve(
                collection_name=collection, ids=[point_id], with_payload=True
            )

            if results:
                return results[0].payload
            return None
        except Exception:
            return None

    async def get_by_field(
        self, collection: str, field: str, value: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a point by field value.

        Args:
            collection: Collection name
            field: Field name
            value: Field value

        Returns:
            First matching point payload or None
        """
        results = await self.client.scroll(
            collection_name=collection,
            scroll_filter=Filter(must=[FieldCondition(key=field, match=MatchValue(value=value))]),
            limit=1,
            with_payload=True,
        )

        points, _ = results
        if points:
            return points[0].payload
        return None

    async def delete(self, collection: str, id: str) -> None:
        """
        Delete a point by ID.

        Args:
            collection: Collection name
            id: Point ID
        """
        point_id = str_to_uuid(id)
        await self.client.delete(
            collection_name=collection, points_selector=models.PointIdsList(points=[point_id])
        )

    async def list_all(
        self,
        collection: str,
        limit: int = 20,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List all points with pagination.

        Args:
            collection: Collection name
            limit: Max results
            offset: Number to skip
            filters: Optional filters

        Returns:
            Tuple of (results, total_count)
        """
        query_filter = self._build_filter(filters) if filters else None

        # Get total count
        count_result = await self.client.count(
            collection_name=collection, count_filter=query_filter
        )
        total = count_result.count

        # Get paginated results
        results, _ = await self.client.scroll(
            collection_name=collection,
            scroll_filter=query_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
        )

        return [(point.payload or {}) for point in results], total
