from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from app.domain.interfaces import KnowledgeIndex
import uuid

class ChromaKnowledgeIndex(KnowledgeIndex):
    def __init__(self, collection_name: str = "knowledge_base"):
        self.client = chromadb.Client(Settings(is_persistent=False))
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def index_chunks(self, chunks: List[Dict[str, Any]], asset_id: str) -> None:
        """Stores knowledge chunks into the Chroma index."""
        ids = []
        embeddings = []
        metadatas = []
        documents = []

        for i, chunk in enumerate(chunks):
            ids.append(f"{asset_id}-{i}")

            # Extract vector if present, else chroma handles it if embedding fn is set
            if "vector" in chunk:
                embeddings.append(chunk["vector"])

            documents.append(chunk.get("text", ""))

            # Chroma metadata values must be str, int, float or bool
            safe_metadata = {"asset_id": asset_id}
            for k, v in chunk.items():
                if k not in ["vector", "text"]:
                    if isinstance(v, (str, int, float, bool)):
                        safe_metadata[k] = v
                    else:
                        safe_metadata[k] = str(v)
            metadatas.append(safe_metadata)

        kwargs = {
            "ids": ids,
            "metadatas": metadatas,
            "documents": documents
        }
        if embeddings:
            kwargs["embeddings"] = embeddings

        self.collection.add(**kwargs)

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches the Chroma index."""
        kwargs = {
            "query_texts": [query],
            "n_results": top_k
        }

        if filters:
            # Simple conversion, assuming basic equality filters
            chroma_where = {}
            for k, v in filters.items():
                if isinstance(v, (str, int, float, bool)):
                    chroma_where[k] = v
            if chroma_where:
                kwargs["where"] = chroma_where

        results = self.collection.query(**kwargs)

        formatted_results = []
        if results and results["ids"] and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                item = {
                    "id": results["ids"][0][i]
                }
                if results["documents"] and results["documents"][0]:
                    item["text"] = results["documents"][0][i]
                if results["metadatas"] and results["metadatas"][0]:
                    item.update(results["metadatas"][0][i])
                if results["distances"] and results["distances"][0]:
                    item["distance"] = results["distances"][0][i]
                formatted_results.append(item)

        return formatted_results
