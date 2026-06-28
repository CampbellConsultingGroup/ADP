"""Tests for ArchitectureDescription round-trip fidelity (US1 / SC-001)."""

from datetime import datetime, timezone

import pytest

from adp.models import (
    ArchitectureDescription,
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


def _full_description() -> ArchitectureDescription:
    return ArchitectureDescription(
        schema_version="1.0.0",
        id="DESIGN-001",
        title="Test Architecture",
        description="Full entity coverage fixture.",
        requirements=[
            Requirement(
                id="REQ-001",
                title="Stateless handling",
                description="All handlers must be stateless.",
                priority="must",
                tags=["perf"],
            )
        ],
        elements=[
            Element(
                id="ELM-001",
                name="API Gateway",
                kind=ElementKind.CONTAINER,
                description="Entry point.",
                satisfies=["REQ-001"],
                provenance="human",
                tags=["api"],
            ),
            Element(
                id="ELM-002",
                name="Order Service",
                kind=ElementKind.CONTAINER,
                satisfies=["REQ-001"],
            ),
        ],
        relationships=[
            Relationship(
                id="REL-001",
                source="ELM-001",
                target="ELM-002",
                label="routes",
                technology="HTTPS",
            )
        ],
        options=[
            SolutionOption(
                id="OPT-001",
                title="JWT auth",
                description="Short-lived JWTs at gateway.",
                status=VerdictStatus.ACCEPTED,
                satisfies=["REQ-001"],
                provenance="ai-rec-001",
            )
        ],
        findings=[
            Finding(
                id="FND-001",
                subject="ELM-001",
                summary="Gateway has no rate limiting.",
                severity="warning",
                source="security-review",
            )
        ],
        verdicts=[
            Verdict(
                id="VRD-001",
                option_id="OPT-001",
                status=VerdictStatus.ACCEPTED,
                rationale="Consistent with platform patterns.",
                decided_by="architecture-board",
                decided_at=_NOW,
            )
        ],
        audit_log=[
            AuditEntry(
                id="AUD-001",
                actor="jmuir",
                action="add-element",
                affected_entity="ELM-001",
                summary="Added API Gateway element.",
                timestamp=_NOW,
                origin="human",
            )
        ],
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_round_trip_all_entities() -> None:
    """Serializing then deserializing a full description produces an equal model (SC-001)."""
    original = _full_description()
    json_str = original.model_dump_json()
    restored = ArchitectureDescription.model_validate_json(json_str)
    assert restored == original


def test_empty_description_is_valid() -> None:
    """An ArchitectureDescription with no entities is still valid."""
    d = ArchitectureDescription(
        schema_version="1.0.0",
        id="D-EMPTY",
        title="Empty",
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert d.requirements == []
    assert d.audit_log == []


def test_schema_version_must_be_semver() -> None:
    """schema_version must follow X.Y.Z pattern."""
    import pydantic

    with pytest.raises(pydantic.ValidationError, match="semver"):
        ArchitectureDescription(
            schema_version="v1",
            id="D-001",
            title="T",
            created_at=_NOW,
            updated_at=_NOW,
        )
