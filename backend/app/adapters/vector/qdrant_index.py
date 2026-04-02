from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.domain.interfaces import KnowledgeIndex

class QdrantKnowledgeIndex(KnowledgeIndex):
    def __init__(self, collection_name: str = "knowledge_base", location: str = ":memory:"):
        self.client = QdrantClient(location=location)
        self.collection_name = collection_name
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        # Default fallback vector size, should ideally be configurable based on embedding model
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    def index_chunks(self, chunks: List[Dict[str, Any]], asset_id: str) -> None:
        """Stores knowledge chunks into the Qdrant index."""
        points = []
        for i, chunk in enumerate(chunks):
            # Assumes chunk dict has a 'vector' or 'embedding' key.
            # In a real app we'd compute this if not present.
            vector = chunk.get("vector", [0.0] * 384) # Placeholder
            points.append(
                PointStruct(
                    id=f"{asset_id}-{i}",
                    vector=vector,
                    payload={"asset_id": asset_id, **chunk}
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches the Qdrant index."""
        # Note: Query requires a vector, so in practice we'd need to embed 'query' here.
        # For the mock/adapter interface, we'll do a placeholder zero-vector search.
        query_vector = [0.0] * 384

        # Build Qdrant filter from simple dict if provided
        qdrant_filter = None
        if filters:
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue
            conditions = []
            for k, v in filters.items():
                conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))
            qdrant_filter = Filter(must=conditions)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=top_k
        )

        return [{"id": r.id, "score": r.score, **r.payload} for r in results]
