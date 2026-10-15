"""Tests for SemanticEngine."""

from __future__ import annotations

import pytest

from a2a_spec.semantic.engine import SemanticEngine
from a2a_spec.spec.schema import SemanticMethod, SemanticRule


class FakeEncoder:
    """Maps known texts to fixed vectors so similarity is predictable."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls = 0

    def encode(self, texts: str | list[str]) -> list[list[float]]:
        self.calls += 1
        items = [texts] if isinstance(texts, str) else texts
        return [self.vectors[t] for t in items]


def _rule(**kwargs: object) -> SemanticRule:
    defaults: dict[str, object] = {
        "rule": "summary_reflects_input",
        "method": SemanticMethod.EMBEDDING_SIMILARITY,
        "threshold": 0.8,
        "source_field": "message",
        "target_field": "summary",
    }
    defaults.update(kwargs)
    return SemanticRule(**defaults)  # type: ignore[arg-type]


ENCODER = FakeEncoder(
    {
        "charged twice": [1.0, 0.0],
        "duplicate charge": [0.9, 0.1],
        "package lost": [0.0, 1.0],
    }
)


class TestSemanticEngine:
    def test_similar_texts_pass(self) -> None:
        engine = SemanticEngine(model=ENCODER)
        [result] = engine.evaluate(
            {"summary": "duplicate charge"}, {"message": "charged twice"}, [_rule()]
        )
        assert result.passed
        assert result.similarity is not None and result.similarity > 0.9

    def test_unrelated_texts_fail(self) -> None:
        engine = SemanticEngine(model=ENCODER)
        [result] = engine.evaluate(
            {"summary": "package lost"}, {"message": "charged twice"}, [_rule()]
        )
        assert not result.passed
        assert "< threshold 0.80" in result.detail

    def test_missing_output_field_fails(self) -> None:
        engine = SemanticEngine(model=ENCODER)
        [result] = engine.evaluate({}, {"message": "charged twice"}, [_rule()])
        assert not result.passed
        assert "output field 'summary'" in result.detail

    def test_non_string_input_field_fails(self) -> None:
        engine = SemanticEngine(model=ENCODER)
        [result] = engine.evaluate({"summary": "duplicate charge"}, {"message": 42}, [_rule()])
        assert not result.passed
        assert "input field 'message'" in result.detail

    def test_rule_without_fields_fails(self) -> None:
        engine = SemanticEngine(model=ENCODER)
        [result] = engine.evaluate({}, {}, [_rule(source_field=None, target_field=None)])
        assert not result.passed
        assert "requires 'source_field' and 'target_field'" in result.detail

    @pytest.mark.parametrize(
        "method", [SemanticMethod.ENTAILMENT, SemanticMethod.LANGUAGE_DETECTION]
    )
    def test_unimplemented_method_fails(self, method: SemanticMethod) -> None:
        engine = SemanticEngine(model=ENCODER)
        [result] = engine.evaluate({}, {}, [_rule(method=method)])
        assert not result.passed
        assert "not implemented" in result.detail

    def test_no_rules_does_not_load_model(self) -> None:
        encoder = FakeEncoder({})
        assert SemanticEngine(model=encoder).evaluate({}, {}, []) == []
        assert encoder.calls == 0
