from abc import ABC, abstractmethod
from typing import Dict, Any, List

class ManagedKnowledgeBase(ABC):
    @abstractmethod
    def sync_asset(self, asset_uri: str, metadata: Dict[str, Any]) -> str:
        """Syncs an asset to the knowledge base."""
        pass

    @abstractmethod
    def retrieve(self, query: str, filters: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieves knowledge based on a query."""
        pass
