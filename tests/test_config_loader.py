"""Tests for config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_handshake.config.loader import load_config
from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.exceptions import ConfigError


class TestConfigLoader:
    def test_load_valid_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "handshake.yaml"
        config_file.write_text('project_name: my-proj\nversion: "2.0"')
        config = load_config(config_file)
        assert config.project_name == "my-proj"
        assert config.version == "2.0"

    def test_load_returns_defaults_when_no_file(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert isinstance(config, HandshakeConfig)
        assert config.project_name == "my-project"

    def test_load_missing_explicit_path(self) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config("/nonexistent/config.yaml")

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("{{bad yaml")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(config_file)

    def test_load_non_mapping(self, tmp_path: Path) -> None:
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_config(config_file)

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = load_config(config_file)
        assert isinstance(config, HandshakeConfig)

    def test_defaults_semantic_config(self) -> None:
        config = HandshakeConfig()
        assert config.semantic.enabled is True
        assert config.semantic.model == "all-MiniLM-L6-v2"

    def test_defaults_ci_config(self) -> None:
        config = HandshakeConfig()
        assert config.ci.fail_on_semantic_drift is True
        assert config.ci.drift_threshold == 0.15

    def test_custom_storage_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "handshake.yaml"
        config_file.write_text('storage:\n  path: "/custom/path"')
        config = load_config(config_file)
        assert config.storage.path == "/custom/path"
