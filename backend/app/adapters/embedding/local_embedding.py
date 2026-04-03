from typing import List
from sentence_transformers import SentenceTransformer
from app.domain.interfaces import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Load the model during initialization
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # Encodes and returns a list of vectors
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
