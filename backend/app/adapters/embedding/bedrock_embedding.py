import json
import logging
from typing import List
import boto3
from app.domain.interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)


class BedrockEmbeddingProvider(EmbeddingProvider):
    """
    AWS Bedrock embedding provider using Amazon Titan Embeddings.
    Supports both amazon.titan-embed-text-v1 and v2 models.
    """
    
    def __init__(
        self, 
        model_id: str = "amazon.titan-embed-text-v1",
        region_name: str = "us-east-1"
    ):
        """
        Initialize Bedrock embedding provider.
        
        Args:
            model_id: Bedrock model ID (default: amazon.titan-embed-text-v1)
            region_name: AWS region (default: us-east-1)
        """
        self.model_id = model_id
        self.region_name = region_name
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=region_name
        )
        logger.info(f"Initialized BedrockEmbeddingProvider with model: {model_id}")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using AWS Bedrock.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (each vector is a list of floats)
        """
        embeddings = []
        
        for text in texts:
            try:
                # Prepare request body for Titan embeddings
                body = json.dumps({
                    "inputText": text
                })
                
                # Call Bedrock
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType='application/json',
                    accept='application/json'
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                embedding = response_body.get('embedding', [])
                
                if not embedding:
                    logger.warning(f"Empty embedding returned for text: {text[:50]}...")
                    # Return zero vector as fallback
                    embedding = [0.0] * 1536  # Titan v1 dimension
                
                embeddings.append(embedding)
                
            except Exception as e:
                logger.error(f"Error generating embedding for text: {str(e)}")
                # Return zero vector as fallback
                embeddings.append([0.0] * 1536)
        
        return embeddings
