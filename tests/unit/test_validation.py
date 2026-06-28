"""Tests for strict validation: extra-field rejection and ID format enforcement (US2 / SC-002)."""

from datetime import datetime, timezone

import pydantic
import pytest

from adp.models import (
    AuditEntry,
    Element,
    ElementKind,
    Finding,
    Relationship,
    Requirement,
    SolutionOption,
    Verdict,
    VerdictStatus,
)

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


# ── Extra-field rejection ─────────────────────────────────────────────────────


def test_requirement_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Requirement(id="REQ-001", title="T", description="D", unknown_field="x")  # type: ignore[call-arg]


def test_element_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Element(id="ELM-001", name="N", kind=ElementKind.CONTAINER, rogue="y")  # type: ignore[call-arg]


def test_relationship_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Relationship(id="REL-001", source="ELM-001", target="ELM-002", extra="z")  # type: ignore[call-arg]


def test_solution_option_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        SolutionOption(  # type: ignore[call-arg]
            id="OPT-001",
            title="T",
            description="D",
            status=VerdictStatus.PENDING,
            bogus=True,
        )


def test_finding_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Finding(id="FND-001", subject="ELM-001", summary="S", extra_key="v")  # type: ignore[call-arg]


def test_verdict_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        Verdict(  # type: ignore[call-arg]
            id="VRD-001",
            option_id="OPT-001",
            status=VerdictStatus.ACCEPTED,
            rationale="R",
            decided_by="board",
            decided_at=_NOW,
            mystery="value",
        )


def test_audit_entry_rejects_extra_field() -> None:
    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        AuditEntry(  # type: ignore[call-arg]
            id="AUD-001",
            actor="a",
            action="b",
            affected_entity="ELM-001",
            summary="S",
            timestamp=_NOW,
            origin="human",
            extra="x",
        )


# ── ID format enforcement ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    [
        "REQ-ABC",     # non-numeric suffix
        "REQ-1234",    # four digits
        "req-001",     # lowercase prefix
        "",            # empty string
        "REQ001",      # missing hyphen
        "REQ-00",      # two digits only
    ],
)
def test_invalid_requirement_id_rejected(bad_id: str) -> None:
    with pytest.raises(pydantic.ValidationError):
        Requirement(id=bad_id, title="T", description="D")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad_id",
    ["ELM-ABC", "ELM-1234", "elm-001", ""],
)
def test_invalid_element_id_rejected(bad_id: str) -> None:
    with pytest.raises(pydantic.ValidationError):
        Element(id=bad_id, name="N", kind=ElementKind.SYSTEM)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad_id",
    ["OPT-ABC", "OPT-9999", "opt-001"],
)
def test_invalid_option_id_rejected(bad_id: str) -> None:
    with pytest.raises(pydantic.ValidationError):
        SolutionOption(id=bad_id, title="T", description="D", status=VerdictStatus.PENDING)  # type: ignore[arg-type]


# ── Boundary conditions ───────────────────────────────────────────────────────


def test_requirement_title_empty_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        Requirement(id="REQ-001", title="", description="D")


def test_requirement_title_over_120_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        Requirement(id="REQ-001", title="x" * 121, description="D")


def test_finding_summary_over_240_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        Finding(id="FND-001", subject="ELM-001", summary="x" * 241)


def test_audit_entry_summary_over_240_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        AuditEntry(
            id="AUD-001",
            actor="a",
            action="b",
            affected_entity="ELM-001",
            summary="x" * 241,
            timestamp=_NOW,
            origin="human",
        )


def test_finding_invalid_severity_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        Finding(id="FND-001", subject="ELM-001", summary="S", severity="fatal")  # type: ignore[arg-type]


def test_audit_entry_invalid_origin_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        AuditEntry(
            id="AUD-001",
            actor="a",
            action="b",
            affected_entity="ELM-001",
            summary="S",
            timestamp=_NOW,
            origin="robot",  # type: ignore[arg-type]
        )
