"""Tests for all custom exception types."""

from __future__ import annotations

import pytest

from a2a_spec.exceptions import (
    AdapterError,
    ConfigError,
    PipelineExecutionError,
    PolicyViolationError,
    SemanticDriftError,
    SnapshotMismatchError,
    SnapshotNotFoundError,
    SpecValidationError,
)


class TestSpecValidationError:
    """Tests for SpecValidationError."""

    def test_message_contains_spec_name(self) -> None:
        """Spec name must appear in the error message."""
        err = SpecValidationError("my-spec", ["field 'x' missing", "wrong type"])
        assert "my-spec" in str(err)

    def test_message_contains_all_errors(self) -> None:
        """All individual errors must be listed in the message."""
        err = SpecValidationError("my-spec", ["field 'x' missing", "wrong type"])
        assert "field 'x' missing" in str(err)
        assert "wrong type" in str(err)

    def test_attributes_stored(self) -> None:
        """spec_name and errors attributes must be stored."""
        err = SpecValidationError("my-spec", ["err1"])
        assert err.spec_name == "my-spec"
        assert err.errors == ["err1"]


class TestSnapshotNotFoundError:
    """Tests for SnapshotNotFoundError."""

    def test_suggests_record_command(self) -> None:
        """Error message must suggest running a2aspec record."""
        err = SnapshotNotFoundError("triage-agent", "billing")
        assert "a2aspec record" in str(err)

    def test_contains_agent_id(self) -> None:
        """Agent ID must appear in the message."""
        err = SnapshotNotFoundError("triage-agent", "billing")
        assert "triage-agent" in str(err)

    def test_contains_scenario(self) -> None:
        """Scenario name must appear in the message."""
        err = SnapshotNotFoundError("triage-agent", "billing_case")
        assert "billing_case" in str(err)

    def test_attributes_stored(self) -> None:
        """agent_id and scenario attributes must be stored."""
        err = SnapshotNotFoundError("a", "b")
        assert err.agent_id == "a"
        assert err.scenario == "b"


class TestSnapshotMismatchError:
    """Tests for SnapshotMismatchError."""

    def test_contains_both_hashes(self) -> None:
        """Both expected and actual hashes must appear in the message."""
        err = SnapshotMismatchError("triage-agent", "abc123", "def456")
        assert "abc123" in str(err)
        assert "def456" in str(err)

    def test_attributes_stored(self) -> None:
        """All three attributes must be accessible."""
        err = SnapshotMismatchError("agent", "expected", "actual")
        assert err.agent_id == "agent"
        assert err.expected_hash == "expected"
        assert err.actual_hash == "actual"


class TestSemanticDriftError:
    """Tests for SemanticDriftError."""

    def test_contains_similarity_value(self) -> None:
        """Similarity value must appear in the message."""
        err = SemanticDriftError("summary", 0.42, 0.85)
        msg = str(err)
        assert "0.42" in msg or "0.420" in msg

    def test_contains_threshold(self) -> None:
        """Threshold value must appear in the message."""
        err = SemanticDriftError("summary", 0.42, 0.85)
        assert "0.85" in str(err) or "0.850" in str(err)

    def test_contains_field_name(self) -> None:
        """Field name must appear in the message."""
        err = SemanticDriftError("summary", 0.42, 0.85)
        assert "summary" in str(err)

    def test_attributes_stored(self) -> None:
        """All attributes must be accessible."""
        err = SemanticDriftError("f", 0.5, 0.9)
        assert err.field == "f"
        assert err.similarity == 0.5
        assert err.threshold == 0.9


class TestPolicyViolationError:
    """Tests for PolicyViolationError."""

    def test_contains_rule_name(self) -> None:
        """Rule name must appear in the message."""
        err = PolicyViolationError("no_pii", "Credit card found in 'summary'")
        assert "no_pii" in str(err)

    def test_contains_detail(self) -> None:
        """Detail text must appear in the message."""
        err = PolicyViolationError("no_pii", "Credit card found in 'summary'")
        assert "Credit card" in str(err)

    def test_attributes_stored(self) -> None:
        """rule_name and detail attributes must be stored."""
        err = PolicyViolationError("rule", "detail")
        assert err.rule_name == "rule"
        assert err.detail == "detail"


class TestPipelineExecutionError:
    """Tests for PipelineExecutionError."""

    def test_contains_agent_id(self) -> None:
        """Agent ID must appear in the message."""
        err = PipelineExecutionError("qa-agent", ValueError("timeout"))
        assert "qa-agent" in str(err)

    def test_contains_cause_message(self) -> None:
        """Cause exception message must appear in the pipeline error."""
        err = PipelineExecutionError("qa-agent", ValueError("timeout"))
        assert "timeout" in str(err)

    def test_attributes_stored(self) -> None:
        """agent_id and cause attributes must be stored."""
        cause = ValueError("boom")
        err = PipelineExecutionError("agent", cause)
        assert err.agent_id == "agent"
        assert err.cause is cause


class TestAdapterError:
    """Tests for AdapterError."""

    def test_contains_agent_id(self) -> None:
        """Agent ID must appear in the message."""
        err = AdapterError("http-agent", "Connection refused")
        assert "http-agent" in str(err)

    def test_contains_detail(self) -> None:
        """Detail message must appear in the error."""
        err = AdapterError("http-agent", "Connection refused")
        assert "Connection refused" in str(err)

    def test_attributes_stored(self) -> None:
        """agent_id and detail attributes must be stored."""
        err = AdapterError("a", "d")
        assert err.agent_id == "a"
        assert err.detail == "d"


class TestConfigError:
    """Tests for ConfigError."""

    def test_is_a2a_spec_error(self) -> None:
        """ConfigError must inherit from A2ASpecError."""
        from a2a_spec.exceptions import A2ASpecError

        err = ConfigError("bad config")
        assert isinstance(err, A2ASpecError)

    def test_message_preserved(self) -> None:
        """The message must be accessible."""
        err = ConfigError("field 'x' is required")
        assert "field 'x' is required" in str(err)


class TestExceptionHierarchy:
    """Tests for the exception hierarchy."""

    def test_all_errors_inherit_base(self) -> None:
        """All custom exceptions must inherit from A2ASpecError."""
        from a2a_spec.exceptions import A2ASpecError

        errors = [
            SpecValidationError("s", []),
            SnapshotNotFoundError("a", "b"),
            SnapshotMismatchError("a", "b", "c"),
            SemanticDriftError("f", 0.1, 0.9),
            PolicyViolationError("r", "d"),
            PipelineExecutionError("a", Exception("e")),
            AdapterError("a", "d"),
            ConfigError("msg"),
        ]
        for err in errors:
            assert isinstance(err, A2ASpecError), f"{type(err).__name__} must extend A2ASpecError"

    def test_all_errors_catchable_as_base(self) -> None:
        """Catching A2ASpecError must catch all custom errors."""
        from a2a_spec.exceptions import A2ASpecError

        with pytest.raises(A2ASpecError):
            raise SnapshotNotFoundError("a", "b")
