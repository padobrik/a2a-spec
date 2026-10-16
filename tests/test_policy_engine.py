"""Tests for policy evaluation engine."""

from __future__ import annotations

from agent_handshake.policy.engine import PolicyEngine
from agent_handshake.spec.schema import PolicyRule


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
        assert "Could not import module 'nonexistent'" in results[0].detail

    def test_custom_validator_loaded_from_dotted_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "shop_checks.py").write_text(
            "def no_refund_promise(output, input_data):\n"
            "    ok = 'refund' not in output.get('reply', '')\n"
            "    return ok, '' if ok else 'reply promises a refund'\n"
        )
        engine = PolicyEngine()
        rules = [
            PolicyRule(
                rule="no_promise", method="custom", validator="shop_checks.no_refund_promise"
            )
        ]
        assert engine.evaluate({"reply": "We are looking into it."}, {}, rules)[0].passed
        failed = engine.evaluate({"reply": "We will refund you."}, {}, rules)[0]
        assert not failed.passed
        assert failed.detail == "reply promises a refund"

    def test_validator_module_that_raises_on_import(self, tmp_path, monkeypatch) -> None:
        monkeypatch.syspath_prepend(str(tmp_path))
        (tmp_path / "broken_checks.py").write_text("raise ValueError('bad config')\n")
        engine = PolicyEngine()
        rules = [PolicyRule(rule="r", method="custom", validator="broken_checks.check")]
        result = engine.evaluate({}, {}, rules)[0]
        assert not result.passed
        assert "Could not import module 'broken_checks'" in result.detail
        assert "bad config" in result.detail

    def test_builtin_validator_by_dotted_path(self) -> None:
        engine = PolicyEngine()
        path = "agent_handshake.policy.builtin.output_not_empty"
        rules = [PolicyRule(rule="not_empty", method="custom", validator=path)]
        assert engine.evaluate({"summary": "Charged twice."}, {}, rules)[0].passed
        assert engine.evaluate({}, {}, rules)[0].detail == "Output is empty"

    def test_custom_validator_path_without_module(self) -> None:
        engine = PolicyEngine()
        rules = [PolicyRule(rule="bad", method="custom", validator="check")]
        assert "Expected format: 'module.path.function_name'" in (
            engine.evaluate({}, {}, rules)[0].detail
        )

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
