"""Unit tests for adp.compliance.models's ControlMapping family (COMPLY-02).

Tests MUST fail before models are implemented (TDD — ART-IV).
"""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from adp.compliance.models import (
    ComplianceStatus,
    ControlMapping,
    ControlMappingListResponse,
    ControlMappingWrite,
    InvalidPatternTargetError,
    MappingNotFoundError,
    MappingTargetNotFoundError,
    MappingTargetType,
)

_NOW = datetime.datetime(2026, 8, 18, 12, 0, 0)


# ── ControlMappingWrite ──────────────────────────────────────────────────────

class TestControlMappingWrite:
    def test_no_args_defaults_to_not_assessed(self):
        write = ControlMappingWrite()
        assert write.compliance_status == ComplianceStatus.NOT_ASSESSED
        assert write.evidence_ref is None
        assert write.assessed_at is None
        assert write.assessed_by is None

    def test_full_write_valid(self):
        write = ControlMappingWrite(
            compliance_status=ComplianceStatus.COMPLIANT,
            evidence_ref="https://docs.example.com/audit",
            assessed_at=datetime.date(2026, 8, 18),
            assessed_by="alice",
        )
        assert write.compliance_status == ComplianceStatus.COMPLIANT
        assert write.evidence_ref == "https://docs.example.com/audit"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            ControlMappingWrite(compliance_status="bogus")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ControlMappingWrite(bogus="nope")


# ── ControlMapping (read model) ──────────────────────────────────────────────

class TestControlMapping:
    def test_entity_targeted_mapping_valid(self):
        mapping = ControlMapping(
            control_id="c1", target_type=MappingTargetType.APPLICATION, target_id="a1",
            compliance_status=ComplianceStatus.PARTIAL, evidence_ref=None,
            assessed_at=None, assessed_by=None, created_at=_NOW,
        )
        assert mapping.target_type == MappingTargetType.APPLICATION
        assert mapping.target_id == "a1"

    def test_organization_mapping_has_no_target_id(self):
        mapping = ControlMapping(
            control_id="c1", target_type=MappingTargetType.ORGANIZATION, target_id=None,
            compliance_status=ComplianceStatus.NOT_ASSESSED, evidence_ref=None,
            assessed_at=None, assessed_by=None, created_at=_NOW,
        )
        assert mapping.target_id is None

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ControlMapping(
                control_id="c1", target_type=MappingTargetType.CAPABILITY, target_id="cap1",
                compliance_status=ComplianceStatus.NOT_ASSESSED, evidence_ref=None,
                assessed_at=None, assessed_by=None, created_at=_NOW, bogus="nope",
            )

    def test_invalid_target_type_rejected(self):
        with pytest.raises(ValidationError):
            ControlMapping(
                control_id="c1", target_type="bogus", target_id="x",
                compliance_status=ComplianceStatus.NOT_ASSESSED, evidence_ref=None,
                assessed_at=None, assessed_by=None, created_at=_NOW,
            )


class TestControlMappingListResponse:
    def test_empty_list_valid(self):
        resp = ControlMappingListResponse(items=[], total=0)
        assert resp.items == []
        assert resp.total == 0

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            ControlMappingListResponse(items=[], total=0, bogus="nope")


# ── Typed exceptions ──────────────────────────────────────────────────────────

class TestTypedExceptions:
    def test_mapping_target_not_found_error_message(self):
        exc = MappingTargetNotFoundError("application", "a1")
        assert exc.target_type == "application"
        assert exc.target_id == "a1"
        assert "application" in str(exc)
        assert "a1" in str(exc)

    def test_invalid_pattern_target_error_message(self):
        exc = InvalidPatternTargetError("k1", "standard")
        assert exc.target_id == "k1"
        assert exc.actual_kind == "standard"
        assert "pattern" in str(exc)

    def test_mapping_not_found_error_message(self):
        exc = MappingNotFoundError("c1", "capability", "cap1")
        assert exc.control_id == "c1"
        assert exc.target_type == "capability"
        assert exc.target_id == "cap1"

    def test_mapping_not_found_error_organization_target_none(self):
        exc = MappingNotFoundError("c1", "organization", None)
        assert exc.target_id is None
