from typing import List
import random
from app.domain.interfaces import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Mock embedding provider that returns random embeddings.
    Used as a fallback when sentence-transformers cannot be loaded.
    """
    
    def __init__(self, dimension: int = 384):
        """
        Initialize mock embedding provider.
        
        Args:
            dimension: Size of embedding vectors (default 384 matches all-MiniLM-L6-v2)
        """
        self.dimension = dimension
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate random embeddings for a list of texts.
        
        Args:
            texts: List of strings to embed
            
        Returns:
            List of embedding vectors (random values between -1 and 1)
        """
        # Generate random embeddings with deterministic seed based on text
        embeddings = []
        for text in texts:
            # Use text hash as seed for reproducibility
            random.seed(hash(text) % (2**32))
            embedding = [random.uniform(-1, 1) for _ in range(self.dimension)]
            embeddings.append(embedding)
        return embeddings
