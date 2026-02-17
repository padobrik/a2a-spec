"""Tests for policy evaluation engine."""

from __future__ import annotations

from a2a_spec.policy.engine import PolicyEngine
from a2a_spec.spec.schema import PolicyRule


class TestPolicyEngine:
    def test_regex_no_match_passes(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="no_ssn", method="regex", patterns=[r"\b\d{3}-\d{2}-\d{4}\b"])]
        results = engine.evaluate({"text": "Hello world"}, {}, rules)
        assert all(r.passed for r in results)

    def test_regex_match_fails(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="no_ssn", method="regex", patterns=[r"\b\d{3}-\d{2}-\d{4}\b"])]
        results = engine.evaluate({"text": "SSN: 123-45-6789"}, {}, rules)
        assert not results[0].passed
        assert "123-45-6789" in results[0].detail

    def test_regex_no_patterns_passes(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="empty", method="regex", patterns=[])]
        results = engine.evaluate({"text": "anything"}, {}, rules)
        assert results[0].passed

    def test_custom_validator_passes(self) -> None:
        engine = PolicyEngine()
        engine.register_validator("my.check", lambda o, i: (True, "ok"))
        rules = [PolicyRule(rule="custom_check", method="custom", validator="my.check")]
        results = engine.evaluate({"x": 1}, {}, rules)
        assert results[0].passed

    def test_custom_validator_fails(self) -> None:
        engine = PolicyEngine()
        engine.register_validator("my.check", lambda o, i: (False, "bad output"))
        rules = [PolicyRule(rule="custom_check", method="custom", validator="my.check")]
        results = engine.evaluate({"x": 1}, {}, rules)
        assert not results[0].passed

    def test_custom_missing_validator(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="missing", method="custom", validator="nonexistent.func")]
        results = engine.evaluate({}, {}, rules)
        assert not results[0].passed
        assert "not registered" in results[0].detail

    def test_custom_no_validator_field(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="bad", method="custom")]
        results = engine.evaluate({}, {}, rules)
        assert not results[0].passed

    def test_nested_string_checked(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="no_ssn", method="regex", patterns=[r"\b\d{3}-\d{2}-\d{4}\b"])]
        output = {"nested": {"deep": "SSN: 123-45-6789"}}
        results = engine.evaluate(output, {}, rules)
        assert not results[0].passed
