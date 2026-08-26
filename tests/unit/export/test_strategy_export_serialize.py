"""Unit tests: pure serialization functions for Strategy domain export
(ADP-81p.3). No I/O, no `exported_at` -- that's added at write time by
adp.export.common._write_entity_file, not by these functions.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from adp.compliance.models import ComplianceStatus, MappingTargetType
from adp.export.strategy import (
    _serialize_control_mapping,
    _serialize_initiative,
    _serialize_objective,
    _serialize_progress_entry,
    _serialize_theme,
)
from adp.strategy.initiatives import ControlMappingRef, StrategyInitiative
from adp.strategy.models import StrategicTheme

_NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


def _objective_row(**overrides) -> SimpleNamespace:
    base = dict(
        id="obj-1", theme_id="theme-1", owner="Alice", statement="Cut MTTR",
        metric_name="MTTR", target_value=Decimal("2.00"), target_unit="hours",
        direction="decrease", fiscal_year=2026, period="Q1",
        status_reason=None, created_at=_NOW, updated_at=_NOW,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_serialize_theme_includes_all_fields() -> None:
    theme = StrategicTheme(
        id="theme-1", name="Operational Excellence", description="...", owner="Bob",
        priority=1, created_at=_NOW, framework_ids=["frm-1", "frm-2"],
    )
    result = _serialize_theme(theme)
    assert result == {
        "id": "theme-1", "name": "Operational Excellence", "description": "...",
        "owner": "Bob", "priority": 1, "framework_ids": ["frm-1", "frm-2"],
        "created_at": _NOW.isoformat(),
    }


def test_serialize_theme_empty_framework_ids_is_empty_list_not_omitted() -> None:
    theme = StrategicTheme(id="theme-1", name="Theme", created_at=_NOW, framework_ids=[])
    result = _serialize_theme(theme)
    assert result["framework_ids"] == []
    assert "framework_ids" in result


def test_serialize_progress_entry() -> None:
    entry = {
        "as_of_date": date(2026, 2, 1), "actual_value": Decimal("6.5"),
        "note": "partial", "recorded_by": "alice",
    }
    result = _serialize_progress_entry(entry)
    assert result == {
        "as_of_date": "2026-02-01", "actual_value": "6.5",
        "note": "partial", "recorded_by": "alice",
    }


def test_serialize_objective_includes_all_fields_and_relationships() -> None:
    row = _objective_row()
    result = _serialize_objective(
        row,
        status="at_risk",
        status_reason=None,
        capability_ids=["cap-1"],
        value_stream_ids=["vs-1"],
        design_ids=["DSN-1"],
        application_ids=["app-1"],
        control_ids=["ctrl-1"],
        depends_on_objective_ids=["obj-2"],
        blocked_objective_ids=["obj-3"],
        initiative_ids=["init-1"],
        progress=[{
            "as_of_date": date(2026, 2, 1), "actual_value": Decimal("6"),
            "note": None, "recorded_by": "alice",
        }],
    )
    assert result == {
        "id": "obj-1", "theme_id": "theme-1", "owner": "Alice", "statement": "Cut MTTR",
        "metric_name": "MTTR", "target_value": "2.00", "target_unit": "hours",
        "direction": "decrease", "fiscal_year": 2026, "period": "Q1",
        "status": "at_risk", "status_reason": None,
        "capability_ids": ["cap-1"], "value_stream_ids": ["vs-1"],
        "design_ids": ["DSN-1"], "application_ids": ["app-1"], "control_ids": ["ctrl-1"],
        "depends_on_objective_ids": ["obj-2"], "blocked_objective_ids": ["obj-3"],
        "initiative_ids": ["init-1"],
        "progress": [{
            "as_of_date": "2026-02-01", "actual_value": "6", "note": None, "recorded_by": "alice",
        }],
        "created_at": _NOW.isoformat(), "updated_at": _NOW.isoformat(),
    }


def test_serialize_objective_empty_relationships_are_empty_lists_not_omitted() -> None:
    row = _objective_row(metric_name=None, target_value=None, target_unit=None, direction=None)
    result = _serialize_objective(
        row, status="proposed", status_reason=None,
        capability_ids=[], value_stream_ids=[], design_ids=[], application_ids=[],
        control_ids=[], depends_on_objective_ids=[], blocked_objective_ids=[],
        initiative_ids=[], progress=[],
    )
    for key in (
        "capability_ids", "value_stream_ids", "design_ids", "application_ids", "control_ids",
        "depends_on_objective_ids", "blocked_objective_ids", "initiative_ids", "progress",
    ):
        assert result[key] == []
        assert key in result
    assert result["target_value"] is None


def test_serialize_objective_abandoned_status_carries_reason() -> None:
    row = _objective_row(status_reason="Deprioritized for FY27")
    result = _serialize_objective(
        row, status="abandoned", status_reason="Deprioritized for FY27",
        capability_ids=[], value_stream_ids=[], design_ids=[], application_ids=[],
        control_ids=[], depends_on_objective_ids=[], blocked_objective_ids=[],
        initiative_ids=[], progress=[],
    )
    assert result["status"] == "abandoned"
    assert result["status_reason"] == "Deprioritized for FY27"


def test_serialize_control_mapping() -> None:
    ref = ControlMappingRef(
        control_id="ctrl-1", target_type=MappingTargetType.APPLICATION, target_id="app-1",
        compliance_status=ComplianceStatus.NON_COMPLIANT, evidence_ref=None, assessed_at=None,
    )
    result = _serialize_control_mapping(ref)
    assert result == {
        "control_id": "ctrl-1", "target_type": "application", "target_id": "app-1",
        "compliance_status": "non_compliant", "evidence_ref": None, "assessed_at": None,
    }


def test_serialize_control_mapping_organization_scope_has_null_target_id() -> None:
    ref = ControlMappingRef(
        control_id="ctrl-1", target_type=MappingTargetType.ORGANIZATION, target_id=None,
        compliance_status=ComplianceStatus.COMPLIANT, evidence_ref="audit-2026",
        assessed_at=date(2026, 1, 1),
    )
    result = _serialize_control_mapping(ref)
    assert result["target_type"] == "organization"
    assert result["target_id"] is None
    assert result["assessed_at"] == "2026-01-01"


def test_serialize_initiative_includes_all_fields() -> None:
    initiative = StrategyInitiative(
        id="init-1", name="Remediate MFA gap", description="...", owner="Bob",
        status="in_progress", objective_ids=["obj-1"],
        control_mappings=[
            ControlMappingRef(
                control_id="ctrl-1", target_type=MappingTargetType.APPLICATION, target_id="app-1",
                compliance_status=ComplianceStatus.NON_COMPLIANT, evidence_ref=None,
                assessed_at=None,
            )
        ],
        created_at=_NOW, updated_at=_NOW,
    )
    result = _serialize_initiative(initiative)
    assert result["id"] == "init-1"
    assert result["objective_ids"] == ["obj-1"]
    assert len(result["control_mappings"]) == 1
    assert result["control_mappings"][0]["control_id"] == "ctrl-1"


def test_serialize_initiative_empty_relationships_are_empty_lists_not_omitted() -> None:
    initiative = StrategyInitiative(
        id="init-1", name="Standalone", status="planned",
        objective_ids=[], control_mappings=[], created_at=_NOW, updated_at=_NOW,
    )
    result = _serialize_initiative(initiative)
    assert result["objective_ids"] == []
    assert result["control_mappings"] == []
