"""Tests for semantic comparison (fallback mode)."""

from __future__ import annotations

from a2a_spec.diff.semantic import compute_similarity


class TestSemanticComparison:
    def test_identical_texts_high_similarity(self) -> None:
        result = compute_similarity("hello world", "hello world")
        assert result.similarity == 1.0

    def test_completely_different_texts(self) -> None:
        result = compute_similarity("apple banana cherry", "xyz abc def")
        assert result.similarity == 0.0

    def test_partial_overlap(self) -> None:
        result = compute_similarity("the cat sat on the mat", "the dog sat on the rug")
        assert 0.0 < result.similarity < 1.0

    def test_empty_strings_are_identical(self) -> None:
        result = compute_similarity("", "")
        assert result.similarity == 1.0

    def test_one_empty_string(self) -> None:
        result = compute_similarity("hello", "")
        assert result.similarity == 0.0

    def test_above_threshold_true(self) -> None:
        result = compute_similarity("hello world foo", "hello world foo")
        assert result.above_threshold(0.85)

    def test_above_threshold_false(self) -> None:
        result = compute_similarity("alpha beta", "gamma delta")
        assert not result.above_threshold(0.85)

    def test_is_similar_property(self) -> None:
        result = compute_similarity("same same same", "same same same")
        assert result.is_similar

    def test_fallback_method_used(self) -> None:
        result = compute_similarity("test", "test", model=None)
        assert result.method == "token_overlap_jaccard"
