import boto3
import logging
from typing import Dict, Any, List
from app.domain.interfaces.knowledge import ManagedKnowledgeBase
from app.config import settings

logger = logging.getLogger(__name__)

class BedrockKnowledgeBaseAdapter(ManagedKnowledgeBase):
    def __init__(self, kb_id: str = None):
        self.kb_id = kb_id or settings.bedrock_kb_id
        self.client = boto3.client('bedrock-agent-runtime', region_name=settings.aws_region)

    def sync_asset(self, asset_uri: str, metadata: Dict[str, Any]) -> str:
        # In Bedrock, we usually trigger an ingestion job for a data source.
        # This is a simplification placeholder.
        logger.info(f"Triggering sync for Bedrock KB {self.kb_id} with asset {asset_uri}")
        return "sync_triggered"

    def retrieve(self, query: str, filters: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.kb_id:
            logger.warning("No Bedrock Knowledge Base ID configured. Skipping retrieval.")
            return []
            
        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={
                    'text': query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': top_k
                    }
                }
            )

            results = []
            for result in response.get('retrievalResults', []):
                results.append({
                    "text": result.get('content', {}).get('text'),
                    "score": result.get('score'),
                    "metadata": result.get('metadata', {})
                })
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve from Bedrock KB: {e}")
            return []

class LocalKnowledgeBaseAdapter(ManagedKnowledgeBase):
    def __init__(self):
        # We would inject Qdrant/Chroma interface here, but keeping it simple for adapter wrapper
        self.store = []

    def sync_asset(self, asset_uri: str, metadata: Dict[str, Any]) -> str:
        self.store.append({"uri": asset_uri, "metadata": metadata})
        return "local_sync_success"

    def retrieve(self, query: str, filters: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        return []
