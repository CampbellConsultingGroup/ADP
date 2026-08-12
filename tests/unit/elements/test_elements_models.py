"""Unit tests: Pydantic v2 validation for the Elements domain (ADP-SPEC-054)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adp.api.routers.elements import ElementCreate, ElementUpdate, RelationshipCreate


def test_element_create_accepts_valid_input() -> None:
    body = ElementCreate(kind="system", name="Payments Service")  # type: ignore[arg-type]
    assert body.kind == "system"
    assert body.name == "Payments Service"


@pytest.mark.parametrize("kind", ["person", "system", "container", "component"])
def test_element_create_accepts_each_kind(kind: str) -> None:
    body = ElementCreate(kind=kind, name="T")  # type: ignore[arg-type]
    assert body.kind == kind


def test_element_create_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        ElementCreate(kind="database", name="T")  # type: ignore[arg-type]


def test_element_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ElementCreate(kind="system", name="")  # type: ignore[arg-type]


def test_element_create_rejects_oversized_name() -> None:
    with pytest.raises(ValidationError):
        ElementCreate(kind="system", name="x" * 121)  # type: ignore[arg-type]


def test_element_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ElementCreate(kind="system", name="T", description="x")  # type: ignore[call-arg]


def test_element_update_accepts_name_only() -> None:
    body = ElementUpdate(name="New Name")
    assert body.name == "New Name"


def test_element_update_rejects_kind_field() -> None:
    # No `kind` field exists at all on ElementUpdate (v1: name-only, data-model.md) --
    # confirms changing an element's kind is genuinely unsupported, not just undocumented.
    with pytest.raises(ValidationError):
        ElementUpdate(name="T", kind="system")  # type: ignore[call-arg]


def test_element_update_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ElementUpdate(name="")


def test_relationship_create_accepts_valid_input() -> None:
    body = RelationshipCreate(source="ELM-001", target="ELM-002", label="Uses")
    assert body.source == "ELM-001"
    assert body.target == "ELM-002"
    assert body.label == "Uses"


def test_relationship_create_label_is_optional() -> None:
    body = RelationshipCreate(source="ELM-001", target="ELM-002")
    assert body.label is None


def test_relationship_create_rejects_oversized_label() -> None:
    with pytest.raises(ValidationError):
        RelationshipCreate(source="ELM-001", target="ELM-002", label="x" * 81)


def test_relationship_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RelationshipCreate(source="ELM-001", target="ELM-002", technology="REST")  # type: ignore[call-arg]
