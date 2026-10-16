"""Semantic rule evaluation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from a2a_spec.semantic.similarity import cosine_similarity
from a2a_spec.spec.schema import SemanticMethod, SemanticRule

logger = logging.getLogger(__name__)


class Encoder(Protocol):
    """Anything that turns texts into embedding vectors."""

    def encode(self, texts: str | list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class SemanticResult:
    """Result of a single semantic rule check.

    Immutable — represents a recorded semantic evaluation outcome.
    """

    rule_name: str
    passed: bool
    similarity: float | None = None
    detail: str = ""


class SemanticEngine:
    """Evaluates semantic rules against an agent's input and output.

    An ``embedding_similarity`` rule compares ``input[source_field]`` with
    ``output[target_field]`` and passes when their cosine similarity is at
    least the rule's threshold. The embedding model is loaded lazily on the
    first rule that needs it.
    """

    def __init__(self, model: Encoder | None = None) -> None:
        self._model = model

    def evaluate(
        self,
        output: dict[str, Any],
        input_data: dict[str, Any],
        rules: list[SemanticRule],
    ) -> list[SemanticResult]:
        """Evaluate all semantic rules.

        Args:
            output: The agent output to check.
            input_data: The input the agent received.
            rules: List of semantic rules from the spec.

        Returns:
            List of SemanticResult objects.

        Raises:
            ImportError: If an embedding rule is present and the
                ``semantic`` extra is not installed.
        """
        logger.debug("Evaluating %d semantic rule(s)", len(rules))
        results: list[SemanticResult] = []

        for rule in rules:
            if rule.method == SemanticMethod.EMBEDDING_SIMILARITY:
                result = self._check_embedding(output, input_data, rule)
            else:
                result = SemanticResult(
                    rule_name=rule.rule,
                    passed=False,
                    detail=f"Semantic method '{rule.method}' is not implemented",
                )
            if not result.passed:
                logger.warning("Semantic failure [%s]: %s", result.rule_name, result.detail)
            results.append(result)

        return results

    def _check_embedding(
        self,
        output: dict[str, Any],
        input_data: dict[str, Any],
        rule: SemanticRule,
    ) -> SemanticResult:
        """Compare an input field with an output field by embedding similarity."""
        if not rule.source_field or not rule.target_field:
            return SemanticResult(
                rule_name=rule.rule,
                passed=False,
                detail="embedding_similarity requires 'source_field' and 'target_field'",
            )

        source = input_data.get(rule.source_field)
        if not isinstance(source, str):
            return _missing_field(rule, "input", rule.source_field)
        target = output.get(rule.target_field)
        if not isinstance(target, str):
            return _missing_field(rule, "output", rule.target_field)

        vec_source, vec_target = self._encoder().encode([source, target])
        similarity = cosine_similarity(vec_source, vec_target)
        passed = similarity >= rule.threshold
        detail = "" if passed else f"similarity {similarity:.2f} < threshold {rule.threshold:.2f}"
        return SemanticResult(
            rule_name=rule.rule, passed=passed, similarity=similarity, detail=detail
        )

    def _encoder(self) -> Encoder:
        if self._model is None:
            from a2a_spec.semantic.embeddings import EmbeddingModel

            self._model = EmbeddingModel()
        return self._model


def _missing_field(rule: SemanticRule, side: str, field: str) -> SemanticResult:
    return SemanticResult(
        rule_name=rule.rule,
        passed=False,
        detail=f"{side} field '{field}' is missing or not a string",
    )
