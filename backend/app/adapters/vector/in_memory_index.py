from typing import List, Dict, Any, Optional
from app.domain.interfaces import KnowledgeIndex

class InMemoryKnowledgeIndex(KnowledgeIndex):
    def __init__(self):
        self.chunks = []

    def index_chunks(self, chunks: List[Dict[str, Any]], asset_id: str) -> None:
        """Stores knowledge chunks into the memory list."""
        for chunk in chunks:
            chunk_copy = chunk.copy()
            chunk_copy["asset_id"] = asset_id
            self.chunks.append(chunk_copy)

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches the memory list. This is a very naive substring match."""
        results = []
        for chunk in self.chunks:
            # Apply basic filtering
            if filters:
                match = True
                for k, v in filters.items():
                    if chunk.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            # Simple substring matching
            text = chunk.get("text", "")
            if query.lower() in str(text).lower() or not query:
                results.append(chunk)
                if len(results) >= top_k:
                    break

        return results
