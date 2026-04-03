from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.domain.interfaces import KnowledgeIndex, EmbeddingProvider

class QdrantKnowledgeIndex(KnowledgeIndex):
    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None, collection_name: str = "knowledge_base", location: str = ":memory:"):
        self.client = QdrantClient(location=location)
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider
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

        # Determine embeddings if we have a provider and chunks have text but no vector
        texts_to_embed = []
        indices_to_embed = []

        for i, chunk in enumerate(chunks):
            if "vector" not in chunk and "text" in chunk and self.embedding_provider:
                texts_to_embed.append(chunk["text"])
                indices_to_embed.append(i)

        embeddings = []
        if texts_to_embed:
            try:
                from app.config import settings
                if settings.vector_search_enabled:
                    embeddings = self.embedding_provider.embed_texts(texts_to_embed)
                else:
                    embeddings = [[0.0] * 384 for _ in texts_to_embed]
            except Exception as e:
                print(f"Error embedding texts: {e}")
                embeddings = [[0.0] * 384 for _ in texts_to_embed]

        for i, chunk in enumerate(chunks):
            vector = chunk.get("vector")
            if not vector:
                if i in indices_to_embed and len(embeddings) > indices_to_embed.index(i):
                    vector = embeddings[indices_to_embed.index(i)]
                else:
                    vector = [0.0] * 384  # Fallback Placeholder

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
        query_vector = [0.0] * 384
        if query and self.embedding_provider:
            try:
                from app.config import settings
                if settings.vector_search_enabled:
                    query_vector = self.embedding_provider.embed_texts([query])[0]
            except Exception as e:
                print(f"Error embedding search query: {e}")

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
