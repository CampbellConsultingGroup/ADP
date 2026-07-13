"""Contract tests: canonical example validates against the published schema (QG-05)."""

import json
from pathlib import Path

import jsonschema
import pytest

_SCHEMA_PATH = Path("generated/architecture-description.schema.json")
_EXAMPLE_PATH = Path("fixtures/example-adp.json")


@pytest.fixture()
def schema() -> dict:  # type: ignore[type-arg]
    if not _SCHEMA_PATH.exists():
        pytest.skip(f"Schema not yet generated: {_SCHEMA_PATH}")
    return json.loads(_SCHEMA_PATH.read_text())  # type: ignore[no-any-return]


@pytest.fixture()
def example() -> dict:  # type: ignore[type-arg]
    if not _EXAMPLE_PATH.exists():
        pytest.skip(f"Example fixture not yet created: {_EXAMPLE_PATH}")
    return json.loads(_EXAMPLE_PATH.read_text())  # type: ignore[no-any-return]


def test_example_validates_against_schema(schema: dict, example: dict) -> None:  # type: ignore[type-arg]
    """fixtures/example-adp.json must validate against the published schema (FR-006, QG-05)."""
    jsonschema.validate(instance=example, schema=schema)


def test_schema_has_required_top_level_fields(schema: dict) -> None:  # type: ignore[type-arg]
    """Published schema must carry $schema, $id, title, schema_version (FR-004)."""
    assert "$schema" in schema
    assert "$id" in schema
    assert "title" in schema
    assert "schema_version" in schema
    assert schema["schema_version"] == "1.0.0"
