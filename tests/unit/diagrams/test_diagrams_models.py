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


def test_create_rejects_title_with_backslash() -> None:
    # ADP-6ir: confirmed ZAP false positive (High/Low confidence, empty
    # evidence) -- its generic Path Traversal rule flagged POST /diagrams
    # accepting and echoing back a backslash-prefixed title verbatim.
    # title is never used to construct a filesystem path anywhere in this
    # module; this is display-string hygiene, not a traversal fix, but it
    # does mean the exact payload ZAP tried is now rejected with a 422.
    with pytest.raises(ValidationError):
        DiagramCreate(title="\\diagrams", diagram_type="flowchart")


def test_create_rejects_title_with_dot_dot() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="../etc/passwd", diagram_type="flowchart")


def test_create_rejects_title_with_control_character() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="Bad\x00Title", diagram_type="flowchart")


def test_create_rejects_title_over_cap() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="x" * 201, diagram_type="flowchart")


def test_create_accepts_title_at_cap() -> None:
    body = DiagramCreate(title="x" * 200, diagram_type="flowchart")
    assert len(body.title) == 200


def test_update_rejects_title_with_backslash() -> None:
    with pytest.raises(ValidationError):
        DiagramUpdate(title="\\diagrams")


def test_create_rejects_dsl_source_over_cap() -> None:
    with pytest.raises(ValidationError):
        DiagramCreate(title="Big", diagram_type="flowchart", dsl_source="x" * 50_001)


def test_create_accepts_dsl_source_at_cap() -> None:
    body = DiagramCreate(title="Big", diagram_type="flowchart", dsl_source="x" * 50_000)
    assert len(body.dsl_source) == 50_000


@pytest.mark.parametrize(
    "diagram_type", ["flowchart", "sequence", "erd", "uml", "architecture", "c4"]
)
def test_create_accepts_each_supported_type(diagram_type: str) -> None:
    body = DiagramCreate(title="T", diagram_type=diagram_type)  # type: ignore[arg-type]
    assert body.diagram_type == diagram_type


def test_create_rejects_unsupported_type() -> None:
    # ADP-SPEC-053: "c4" used to be the example of an unsupported type here -- it isn't anymore
    # (see test_create_accepts_each_supported_type above), so this now exercises a genuinely
    # unsupported value instead. The test's purpose (reject unknown types) is unchanged.
    with pytest.raises(ValidationError):
        DiagramCreate(title="T", diagram_type="gantt")  # type: ignore[arg-type]


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
