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


class TestUnknownSettings:
    def test_typo_suggests_the_closest_setting(self, tmp_path: Path) -> None:
        config_file = tmp_path / "handshake.yaml"
        config_file.write_text("project: demo\n")
        with pytest.raises(ConfigError) as info:
            load_config(config_file)
        message = str(info.value)
        assert message.startswith(f"{config_file}: Unknown setting 'project'.")
        assert "Did you mean 'project_name'?" in message
        assert "Known settings: project_name, version." in message

    def test_no_close_match_lists_the_settings(self, tmp_path: Path) -> None:
        config_file = tmp_path / "handshake.yaml"
        config_file.write_text("zzz: 1\n")
        with pytest.raises(ConfigError) as info:
            load_config(config_file)
        assert "Did you mean" not in str(info.value)
        assert "Unknown setting 'zzz'. Known settings:" in str(info.value)

    def test_models_reject_unknown_fields(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HandshakeConfig.model_validate({"specs_dir": "x"})
