"""Embedding model loading and management."""

from __future__ import annotations


class EmbeddingModel:
    """Wrapper around sentence-transformers for lazy loading.

    The model is loaded on first use, not at import time.
    This keeps the package lightweight for users who only need
    structural validation.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: object | None = None

    def _load(self) -> None:
        """Load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for semantic features. "
                "Install with: pip install a2a-spec[semantic]"
            ) from e
        self._model = SentenceTransformer(self._model_name)

    def encode(self, texts: str | list[str]) -> list[list[float]]:
        """Encode text(s) into embedding vectors.

        Args:
            texts: A single string or list of strings.

        Returns:
            List of embedding vectors (list of floats).
        """
        if self._model is None:
            self._load()

        if isinstance(texts, str):
            texts = [texts]

        embeddings = self._model.encode(texts)  # type: ignore[union-attr]
        return [emb.tolist() for emb in embeddings]

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name
