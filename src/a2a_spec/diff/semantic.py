"""Semantic comparison using embeddings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SemanticComparison:
    """Result of comparing two strings semantically."""

    text_a: str
    text_b: str
    similarity: float  # 0.0 to 1.0
    method: str = "cosine_similarity"

    @property
    def is_similar(self) -> bool:
        """Check if texts are similar using default threshold."""
        return self.similarity >= 0.85

    def above_threshold(self, threshold: float) -> bool:
        """Check if similarity is above a given threshold."""
        return self.similarity >= threshold


def compute_similarity(text_a: str, text_b: str, model: object | None = None) -> SemanticComparison:
    """Compute semantic similarity between two texts.

    If the sentence-transformers package is not installed or no model
    is provided, falls back to a basic token overlap metric.

    Args:
        text_a: First text.
        text_b: Second text.
        model: Optional SentenceTransformer model instance.

    Returns:
        SemanticComparison with similarity score.
    """
    if model is not None:
        return _embedding_similarity(text_a, text_b, model)
    return _fallback_similarity(text_a, text_b)


def _embedding_similarity(text_a: str, text_b: str, model: object) -> SemanticComparison:
    """Compute cosine similarity using sentence-transformers."""
    try:
        import numpy as np
    except ImportError as e:
        raise ImportError(
            "numpy is required for semantic comparison. "
            "Install with: pip install a2a-spec[semantic]"
        ) from e

    embeddings = model.encode([text_a, text_b])  # type: ignore[attr-defined]
    vec_a, vec_b = embeddings[0], embeddings[1]

    dot_product = float(np.dot(vec_a, vec_b))
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))

    if norm_a == 0 or norm_b == 0:
        similarity = 0.0
    else:
        similarity = dot_product / (norm_a * norm_b)

    return SemanticComparison(
        text_a=text_a,
        text_b=text_b,
        similarity=similarity,
        method="cosine_similarity",
    )


def _fallback_similarity(text_a: str, text_b: str) -> SemanticComparison:
    """Simple token overlap when sentence-transformers is unavailable."""
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())

    if not tokens_a and not tokens_b:
        similarity = 1.0
    elif not tokens_a or not tokens_b:
        similarity = 0.0
    else:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        similarity = len(intersection) / len(union)  # Jaccard

    return SemanticComparison(
        text_a=text_a,
        text_b=text_b,
        similarity=similarity,
        method="token_overlap_jaccard",
    )
