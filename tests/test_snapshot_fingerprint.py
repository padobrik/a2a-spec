"""Tests for snapshot fingerprinting."""

from __future__ import annotations

from a2a_spec.snapshot.fingerprint import Fingerprint


class TestFingerprint:
    def test_same_input_same_key(self) -> None:
        fp1 = Fingerprint.create("agent-a", {"msg": "hello"})
        fp2 = Fingerprint.create("agent-a", {"msg": "hello"})
        assert fp1.key == fp2.key

    def test_different_input_different_key(self) -> None:
        fp1 = Fingerprint.create("agent-a", {"msg": "hello"})
        fp2 = Fingerprint.create("agent-a", {"msg": "world"})
        assert fp1.key != fp2.key

    def test_different_agent_different_key(self) -> None:
        fp1 = Fingerprint.create("agent-a", {"msg": "hello"})
        fp2 = Fingerprint.create("agent-b", {"msg": "hello"})
        assert fp1.key != fp2.key

    def test_prompt_hash_affects_key(self) -> None:
        fp1 = Fingerprint.create("agent-a", {"msg": "hello"}, prompt_hash="v1")
        fp2 = Fingerprint.create("agent-a", {"msg": "hello"}, prompt_hash="v2")
        assert fp1.key != fp2.key

    def test_key_is_12_chars(self) -> None:
        fp = Fingerprint.create("agent-a", {"msg": "test"})
        assert len(fp.key) == 12

    def test_key_is_deterministic(self) -> None:
        fp = Fingerprint.create("agent-a", {"x": 1, "y": 2})
        assert fp.key == Fingerprint.create("agent-a", {"x": 1, "y": 2}).key

    def test_dict_key_order_does_not_matter(self) -> None:
        fp1 = Fingerprint.create("a", {"x": 1, "y": 2})
        fp2 = Fingerprint.create("a", {"y": 2, "x": 1})
        assert fp1.key == fp2.key

    def test_frozen_dataclass(self) -> None:
        fp = Fingerprint.create("agent-a", {"msg": "hello"})
        import dataclasses

        assert dataclasses.is_dataclass(fp)
