"""Unit tests for DesignImporter (T027-T029)."""

from __future__ import annotations

import json

import pytest

from adp.models import ArchitectureDescription, SCHEMA_VERSION


def _make_valid_dict(design_id: str = "D-001") -> dict:  # type: ignore[return]
    return {
        "schema_version": SCHEMA_VERSION,
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [
            {"id": "ELM-001", "name": "API", "kind": "container", "satisfies": [], "provenance": None},
        ],
        "requirements": [],
        "relationships": [],
    }


def test_import_valid_model_json_succeeds():
    from adp.export.importer import DesignImporter

    original = ArchitectureDescription.model_validate(_make_valid_dict())
    json_str = original.model_dump_json()

    reimported = DesignImporter().import_from_json(json_str)

    assert reimported.id == original.id
    assert len(reimported.elements) == len(original.elements)
    assert len(reimported.relationships) == len(original.relationships)
    # element-for-element equivalence: same element IDs
    original_ids = {e.id for e in original.elements}
    reimported_ids = {e.id for e in reimported.elements}
    assert original_ids == reimported_ids


def test_import_wrong_schema_version_rejected():
    from adp.export.importer import DesignImporter

    data = _make_valid_dict()
    data["schema_version"] = "99.0.0"

    with pytest.raises(ValueError, match="99.0.0"):
        DesignImporter().import_from_json(json.dumps(data))


def test_import_malformed_json_rejected():
    from adp.export.importer import DesignImporter

    with pytest.raises(ValueError, match="Invalid JSON"):
        DesignImporter().import_from_json("not valid json {{")


def test_import_invalid_schema_field_rejected():
    from adp.export.importer import DesignImporter
    import pydantic

    data = _make_valid_dict()
    data["unknown_extra_field"] = "boom"  # extra fields forbidden by ArchitectureDescription

    with pytest.raises((ValueError, pydantic.ValidationError)):
        DesignImporter().import_from_json(json.dumps(data))
