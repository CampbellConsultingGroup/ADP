"""Published pattern JSON Schema (934 US3, FR-016)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from adp.generate import _PATTERN_SCHEMA_PATH, generate_pattern_schema

from .conftest import valid_fixture_paths


def test_pattern_schema_deterministic() -> None:
    assert generate_pattern_schema() == generate_pattern_schema()


def test_pattern_schema_metadata() -> None:
    schema = json.loads(generate_pattern_schema())
    assert schema["$id"].endswith("/pattern.schema.json")
    assert schema["title"] == "ADP EA Pattern"
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "lifecycle" not in schema["properties"]


def test_committed_schema_matches_generated() -> None:
    assert _PATTERN_SCHEMA_PATH.read_text(encoding="utf-8") == generate_pattern_schema()


@pytest.mark.parametrize("path", valid_fixture_paths(), ids=lambda p: p.name)
def test_valid_fixtures_validate_against_schema(path: Path) -> None:
    schema = json.loads(generate_pattern_schema())
    jsonschema.validate(yaml.safe_load(path.read_text(encoding="utf-8")), schema)


def test_schema_rejects_unknown_field() -> None:
    schema = json.loads(generate_pattern_schema())
    doc = yaml.safe_load((valid_fixture_paths()[0]).read_text(encoding="utf-8"))
    doc["lifecycle"] = "current"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(doc, schema)
