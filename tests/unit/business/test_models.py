"""Unit tests for adp.business.models — Pydantic validation rules (ADP-SPEC-033/034/035).

Tests MUST fail before models are implemented (TDD — ART-IV).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adp.business.models import (
    BusinessCapabilityCreate,
    BusinessCapabilityUpdate,
    BusinessContextResponse,
    BusinessDomainCreate,
    BusinessDomainUpdate,
    CapabilityDomainAssign,
    CapabilityRef,
    DesignLinkCreate,
    DesignRef,
    LinkedDesignsResponse,
    StageCapabilityLinkCreate,
    ValueStreamCreate,
    ValueStreamRef,
    ValueStreamStageCreate,
)

# ── BusinessCapabilityCreate ──────────────────────────────────────────────────

class TestBusinessCapabilityCreate:
    def test_level_1_no_parent(self):
        cap = BusinessCapabilityCreate(name="Customer Engagement", level=1)
        assert cap.level == 1
        assert cap.parent_id is None

    def test_level_2_requires_parent(self):
        with pytest.raises(ValidationError, match="parent_id"):
            BusinessCapabilityCreate(name="Sales", level=2, parent_id=None)

    def test_level_3_requires_parent(self):
        with pytest.raises(ValidationError, match="parent_id"):
            BusinessCapabilityCreate(name="Lead Qual", level=3, parent_id=None)

    def test_level_1_rejects_parent(self):
        with pytest.raises(ValidationError, match="parent_id"):
            BusinessCapabilityCreate(name="Top", level=1, parent_id="some-parent-id")

    def test_level_4_rejected(self):
        with pytest.raises(ValidationError):
            BusinessCapabilityCreate(name="Too Deep", level=4, parent_id="p")

    def test_level_0_rejected(self):
        with pytest.raises(ValidationError):
            BusinessCapabilityCreate(name="Zero", level=0)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessCapabilityCreate(name="", level=1)

    def test_whitespace_only_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessCapabilityCreate(name="   ", level=1)

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            BusinessCapabilityCreate(name="Cap", level=1, unknown_field="x")

    def test_valid_level_2_with_parent(self):
        cap = BusinessCapabilityCreate(name="Sales", level=2, parent_id="parent-uuid")
        assert cap.parent_id == "parent-uuid"
        assert cap.level == 2

    def test_default_position_zero(self):
        cap = BusinessCapabilityCreate(name="Cap", level=1)
        assert cap.position == 0


class TestBusinessCapabilityUpdate:
    def test_all_fields_optional(self):
        update = BusinessCapabilityUpdate()
        assert update.name is None
        assert update.description is None
        assert update.position is None

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessCapabilityUpdate(name="")

    def test_whitespace_only_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessCapabilityUpdate(name="  ")

    def test_valid_name_update(self):
        update = BusinessCapabilityUpdate(name="Updated Name")
        assert update.name == "Updated Name"


# ── ValueStreamCreate ─────────────────────────────────────────────────────────

class TestValueStreamCreate:
    def test_name_required(self):
        with pytest.raises(ValidationError):
            ValueStreamCreate(name="")

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValidationError):
            ValueStreamCreate(name="   ")

    def test_optional_fields_default_none(self):
        vs = ValueStreamCreate(name="Order to Cash")
        assert vs.description is None
        assert vs.stakeholder is None

    def test_full_creation(self):
        vs = ValueStreamCreate(name="Order to Cash", description="Desc", stakeholder="Customer")
        assert vs.stakeholder == "Customer"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ValueStreamCreate(name="VS", extra_field="x")


# ── ValueStreamStageCreate ────────────────────────────────────────────────────

class TestValueStreamStageCreate:
    def test_name_required_non_empty(self):
        with pytest.raises(ValidationError):
            ValueStreamStageCreate(name="")

    def test_default_position(self):
        stage = ValueStreamStageCreate(name="Order Capture")
        assert stage.position == 0

    def test_valid_stage(self):
        stage = ValueStreamStageCreate(name="Fulfilment", description="Ship it", position=1)
        assert stage.name == "Fulfilment"
        assert stage.position == 1


# ── DesignLinkCreate (ADP-SPEC-034) ──────────────────────────────────────────

class TestDesignLinkCreate:
    def test_blank_design_id_rejected(self):
        with pytest.raises(ValidationError, match="design_id"):
            DesignLinkCreate(design_id="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError, match="design_id"):
            DesignLinkCreate(design_id="   ")

    def test_valid_design_id(self):
        link = DesignLinkCreate(design_id="DES-001")
        assert link.design_id == "DES-001"

    def test_design_id_stripped(self):
        link = DesignLinkCreate(design_id="  DES-001  ")
        assert link.design_id == "DES-001"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            DesignLinkCreate(design_id="DES-001", extra="x")


class TestDesignRef:
    def test_valid(self):
        ref = DesignRef(design_id="DES-001", title="Order System", lifecycle_status="current")
        assert ref.design_id == "DES-001"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            DesignRef(design_id="DES-001", title="T", lifecycle_status="draft", extra="x")


class TestLinkedDesignsResponse:
    def test_empty_items(self):
        resp = LinkedDesignsResponse(items=[])
        assert resp.items == []

    def test_items_list(self):
        resp = LinkedDesignsResponse(items=[
            DesignRef(design_id="D1", title="T1", lifecycle_status="draft"),
        ])
        assert len(resp.items) == 1


class TestBusinessContextResponse:
    def test_empty_lists(self):
        resp = BusinessContextResponse(design_id="D1", capabilities=[], value_streams=[])
        assert resp.capabilities == []
        assert resp.value_streams == []

    def test_with_entries(self):
        resp = BusinessContextResponse(
            design_id="D1",
            capabilities=[CapabilityRef(capability_id="c1", name="Order Processing", level=1)],
            value_streams=[
                ValueStreamRef(value_stream_id="v1", name="Order to Cash", stakeholder="Finance")
            ],
        )
        assert resp.capabilities[0].level == 1
        assert resp.value_streams[0].stakeholder == "Finance"


# ── BusinessDomainCreate (ADP-SPEC-035) ───────────────────────────────────────

class TestBusinessDomainCreate:
    def test_valid_full_create(self):
        d = BusinessDomainCreate(
            name="Customer",
            scope_statement="In: identity. Out: billing.",
            classification="strategic",
            org_unit="CX",
            risk_flags=["PII", "GDPR"],
        )
        assert d.name == "Customer"
        assert d.risk_flags == ["PII", "GDPR"]

    def test_blank_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessDomainCreate(name="", classification="strategic")

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessDomainCreate(name="   ", classification="strategic")

    def test_invalid_classification(self):
        with pytest.raises(ValidationError):
            BusinessDomainCreate(name="D", classification="premium")

    def test_blank_risk_flag_rejected(self):
        with pytest.raises(ValidationError, match="risk_flags"):
            BusinessDomainCreate(name="D", classification="commodity", risk_flags=["PII", ""])

    def test_duplicate_risk_flags_deduplicated(self):
        d = BusinessDomainCreate(
            name="D", classification="commodity", risk_flags=["PII", "PII", "GDPR"]
        )
        assert d.risk_flags == ["PII", "GDPR"]

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            BusinessDomainCreate(name="D", classification="strategic", extra="x")

    def test_optional_fields_default(self):
        d = BusinessDomainCreate(name="D", classification="differentiating")
        assert d.scope_statement is None
        assert d.org_unit is None
        assert d.risk_flags == []


class TestBusinessDomainUpdate:
    def test_all_fields_optional(self):
        u = BusinessDomainUpdate()
        assert u.name is None
        assert u.classification is None
        assert u.risk_flags is None

    def test_blank_name_rejected(self):
        with pytest.raises(ValidationError, match="name"):
            BusinessDomainUpdate(name="")

    def test_blank_risk_flag_rejected(self):
        with pytest.raises(ValidationError, match="risk_flags"):
            BusinessDomainUpdate(risk_flags=["PII", "  "])

    def test_duplicate_flags_deduplicated(self):
        u = BusinessDomainUpdate(risk_flags=["SOX", "SOX", "HIPAA"])
        assert u.risk_flags == ["SOX", "HIPAA"]


class TestCapabilityDomainAssign:
    def test_valid_uuid(self):
        a = CapabilityDomainAssign(domain_id="some-domain-uuid")
        assert a.domain_id == "some-domain-uuid"

    def test_null_accepted(self):
        a = CapabilityDomainAssign(domain_id=None)
        assert a.domain_id is None

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            CapabilityDomainAssign(domain_id="x", extra="y")


class TestStageCapabilityLinkCreate:
    def test_valid(self):
        s = StageCapabilityLinkCreate(capability_id="cap-001")
        assert s.capability_id == "cap-001"

    def test_blank_rejected(self):
        with pytest.raises(ValidationError, match="capability_id"):
            StageCapabilityLinkCreate(capability_id="")

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError, match="capability_id"):
            StageCapabilityLinkCreate(capability_id="   ")

    def test_whitespace_stripped(self):
        s = StageCapabilityLinkCreate(capability_id="  cap-001  ")
        assert s.capability_id == "cap-001"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            StageCapabilityLinkCreate(capability_id="c", extra="x")
