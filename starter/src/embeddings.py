"""Real local semantic embeddings powered by Sentence Transformers."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """Load one local multilingual model and use it consistently for all strategies."""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install requirements.txt to use local embeddings") from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self.dimensions = int(self._model.get_embedding_dimension())
        if self.dimensions < 1:
            raise RuntimeError(f"Model reported invalid embedding dimension: {self.dimensions}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode_document(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        vector = self._model.encode_query(question, normalize_embeddings=True, show_progress_bar=False)
        return vector.tolist()
