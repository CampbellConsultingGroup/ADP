"""Unit tests: Pydantic v2 validation for the Diagrams domain (ADP-SPEC-046
T005, data-model.md §2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from adp.diagrams.models import (
    Diagram,
    DiagramCreate,
    DiagramListResponse,
    DiagramSummary,
    DiagramUpdate,
)

_NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


def test_create_accepts_minimal_valid_payload() -> None:
    body = DiagramCreate(title="Claims Intake", diagram_type="flowchart")
    assert body.dsl_source == ""  # creatable before any content exists


def test_create_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="   ", diagram_type="flowchart")


def test_create_rejects_dsl_source_over_cap() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="Big", diagram_type="flowchart", dsl_source="x" * 50_001)


def test_create_accepts_dsl_source_at_cap() -> None:
    body = DiagramCreate(title="Big", diagram_type="flowchart", dsl_source="x" * 50_000)
    assert len(body.dsl_source) == 50_000


@pytest.mark.parametrize(
    "diagram_type", ["flowchart", "sequence", "erd", "uml", "architecture"]
)
def test_create_accepts_each_supported_type(diagram_type: str) -> None:
    body = DiagramCreate(title="T", diagram_type=diagram_type)  # type: ignore[arg-type]
    assert body.diagram_type == diagram_type


def test_create_rejects_unsupported_type() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="T", diagram_type="c4")  # type: ignore[arg-type]


def test_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="T", diagram_type="flowchart", design_id="d-1")  # type: ignore[call-arg]


def test_update_all_fields_optional() -> None:
    body = DiagramUpdate()
    assert body.title is None
    assert body.dsl_source is None


def test_update_has_no_diagram_type_field() -> None:
    # diagram_type is immutable after creation (data-model.md §4) -- DiagramUpdate
    # must not even accept it as a field to attempt setting.
    assert "diagram_type" not in DiagramUpdate.model_fields


def test_diagram_summary_omits_dsl_source() -> None:
    assert "dsl_source" not in DiagramSummary.model_fields


def test_diagram_full_model_round_trips() -> None:
    d = Diagram(
        id="diag-1",
        title="Claims Intake",
        diagram_type="flowchart",
        dsl_source="flowchart LR\nA-->B\n",
        created_by="alice",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert d.dsl_source == "flowchart LR\nA-->B\n"


def test_diagram_list_response_shape() -> None:
    resp = DiagramListResponse(
        items=[
            DiagramSummary(id="d-1", title="A", diagram_type="flowchart", updated_at=_NOW),
        ],
        total=1,
    )
    assert resp.total == 1
    assert resp.items[0].title == "A"
