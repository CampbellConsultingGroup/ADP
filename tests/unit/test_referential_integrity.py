"""Tests for cross-entity referential integrity validation (US4 / SC-004 / ART-XI)."""

from datetime import datetime, timezone

import pydantic
import pytest

from adp.models import (
    ArchitectureDescription,
    Element,
    ElementKind,
    Finding,
    Relationship,
    Requirement,
    SolutionOption,
    Verdict,
    VerdictStatus,
)
from adp.validate import build_id_index

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def _base() -> dict:  # type: ignore[type-arg]
    """Minimal valid ArchitectureDescription kwargs."""
    return {
        "schema_version": "1.0.0",
        "id": "D-001",
        "title": "Test",
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _req() -> Requirement:
    return Requirement(id="REQ-001", title="R", description="Desc")


def _elm(eid: str = "ELM-001") -> Element:
    return Element(id=eid, name="N", kind=ElementKind.CONTAINER)


def _opt() -> SolutionOption:
    return SolutionOption(id="OPT-001", title="T", description="D", status=VerdictStatus.PENDING)


# ── Valid reference chains pass ───────────────────────────────────────────────


def test_valid_references_pass() -> None:
    """A fully-linked description with all reference types present must construct without error."""
    desc = ArchitectureDescription(
        **_base(),
        requirements=[_req()],
        elements=[
            Element(id="ELM-001", name="A", kind=ElementKind.CONTAINER, satisfies=["REQ-001"]),
            Element(id="ELM-002", name="B", kind=ElementKind.SYSTEM),
        ],
        relationships=[Relationship(id="REL-001", source="ELM-001", target="ELM-002")],
        options=[SolutionOption(id="OPT-001", title="T", description="D",
                                status=VerdictStatus.ACCEPTED, satisfies=["REQ-001"])],
        findings=[Finding(id="FND-001", subject="ELM-001", summary="S")],
        verdicts=[Verdict(id="VRD-001", option_id="OPT-001", status=VerdictStatus.ACCEPTED,
                          rationale="R", decided_by="board", decided_at=_NOW)],
    )
    assert desc.id == "D-001"


# ── Dangling references fail with named ID ────────────────────────────────────


def test_dangling_requirement_reference() -> None:
    """Element.satisfies referencing unknown RequirementId must fail naming the ID."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ArchitectureDescription(
            **_base(),
            requirements=[_req()],  # only REQ-001 exists
            elements=[Element(id="ELM-001", name="N", kind=ElementKind.CONTAINER,
                              satisfies=["REQ-999"])],  # REQ-999 missing
        )
    assert "REQ-999" in str(exc_info.value)


def test_dangling_element_source() -> None:
    """Relationship.source referencing unknown ElementId must fail naming the ID."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ArchitectureDescription(
            **_base(),
            elements=[_elm("ELM-001")],
            relationships=[Relationship(id="REL-001", source="ELM-999", target="ELM-001")],
        )
    assert "ELM-999" in str(exc_info.value)


def test_dangling_element_target() -> None:
    """Relationship.target referencing unknown ElementId must fail naming the ID."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ArchitectureDescription(
            **_base(),
            elements=[_elm("ELM-001")],
            relationships=[Relationship(id="REL-001", source="ELM-001", target="ELM-999")],
        )
    assert "ELM-999" in str(exc_info.value)


def test_dangling_finding_subject() -> None:
    """Finding.subject referencing unknown Element/Option ID must fail naming the ID."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ArchitectureDescription(
            **_base(),
            elements=[_elm("ELM-001")],
            findings=[Finding(id="FND-001", subject="ELM-999", summary="S")],
        )
    assert "ELM-999" in str(exc_info.value)


def test_dangling_verdict_option() -> None:
    """Verdict.option_id referencing unknown OptionId must fail naming the ID."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ArchitectureDescription(
            **_base(),
            options=[_opt()],  # OPT-001 exists
            verdicts=[Verdict(id="VRD-001", option_id="OPT-999",  # OPT-999 missing
                              status=VerdictStatus.ACCEPTED, rationale="R",
                              decided_by="board", decided_at=_NOW)],
        )
    assert "OPT-999" in str(exc_info.value)


def test_finding_subject_can_be_option() -> None:
    """Finding.subject may reference a SolutionOption ID (not just Element)."""
    desc = ArchitectureDescription(
        **_base(),
        options=[_opt()],
        findings=[Finding(id="FND-001", subject="OPT-001", summary="Finding on option")],
    )
    assert desc.findings[0].subject == "OPT-001"


# ── Duplicate ID detection ────────────────────────────────────────────────────


def test_duplicate_entity_ids_rejected() -> None:
    """Two entities with the same ID in a description must fail."""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        ArchitectureDescription(
            **_base(),
            requirements=[
                Requirement(id="REQ-001", title="R1", description="D1"),
                Requirement(id="REQ-001", title="R2", description="D2"),
            ],
        )
    assert "REQ-001" in str(exc_info.value)


# ── build_id_index and validate_references unit tests ─────────────────────────


def test_build_id_index_returns_all_ids() -> None:
    desc = ArchitectureDescription(
        **_base(),
        requirements=[_req()],
        elements=[_elm()],
    )
    index = build_id_index(desc)
    assert "REQ-001" in index
    assert "ELM-001" in index


def test_build_id_index_raises_on_duplicates() -> None:
    """build_id_index raises ValueError listing duplicate IDs."""
    desc = ArchitectureDescription.__new__(ArchitectureDescription)
    req = Requirement(id="REQ-001", title="R", description="D")
    object.__setattr__(desc, "requirements", [req, req])
    for field in ["elements", "relationships", "options", "findings", "verdicts", "audit_log"]:
        object.__setattr__(desc, field, [])

    with pytest.raises(ValueError, match="REQ-001"):
        build_id_index(desc)
