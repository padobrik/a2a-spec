"""Tests for spec YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from a2a_spec.exceptions import ConfigError
from a2a_spec.spec.loader import load_all_specs, load_spec

VALID_SPEC_YAML = """
spec:
  name: test-spec
  version: "1.0"
  producer: agent-a
  consumer: agent-b
  structural:
    type: object
    required:
      - category
    properties:
      category:
        type: string
"""


class TestLoadSpec:
    def test_load_valid_spec(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(VALID_SPEC_YAML)
        spec = load_spec(spec_file)
        assert spec.name == "test-spec"
        assert spec.producer == "agent-a"
        assert spec.consumer == "agent-b"
        assert spec.structural.required == ["category"]

    def test_load_spec_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_spec(tmp_path / "nonexistent.yaml")

    def test_load_spec_wrong_extension(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "test.json"
        spec_file.write_text("{}")
        with pytest.raises(ConfigError, match=".yaml or .yml"):
            load_spec(spec_file)

    def test_load_spec_invalid_yaml(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "bad.yaml"
        spec_file.write_text("{{invalid yaml")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_spec(spec_file)

    def test_load_spec_not_mapping(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "list.yaml"
        spec_file.write_text("- item1\n- item2")
        with pytest.raises(ConfigError, match="YAML mapping"):
            load_spec(spec_file)

    def test_load_spec_missing_spec_key(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "no_key.yaml"
        spec_file.write_text("name: test\nversion: 1")
        with pytest.raises(ConfigError, match="top-level 'spec' key"):
            load_spec(spec_file)

    def test_load_spec_invalid_schema(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "bad_schema.yaml"
        spec_file.write_text("spec:\n  name: test\n  version: '1'\n")
        with pytest.raises(ConfigError, match="Invalid spec"):
            load_spec(spec_file)

    def test_load_spec_yml_extension(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "test.yml"
        spec_file.write_text(VALID_SPEC_YAML)
        spec = load_spec(spec_file)
        assert spec.name == "test-spec"


class TestLoadAllSpecs:
    def test_load_all_from_directory(self, tmp_path: Path) -> None:
        for i in range(3):
            content = VALID_SPEC_YAML.replace("test-spec", f"spec-{i}")
            (tmp_path / f"spec_{i}.yaml").write_text(content)
        specs = load_all_specs(tmp_path)
        assert len(specs) == 3

    def test_load_from_nonexistent_directory(self) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_all_specs("/nonexistent/path")

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        specs = load_all_specs(tmp_path)
        assert specs == []
