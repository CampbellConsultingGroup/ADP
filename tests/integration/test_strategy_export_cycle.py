"""Integration test: one full reconciliation cycle against a real Postgres
container (ADP-81p.3), including real migrations the shared
tests/integration/conftest.py fixtures provide.

Seeds data BEFORE ever running a reconciliation cycle, confirming the very
first cycle performs a complete bootstrap export with no separate manual
step (FR-008) -- themes, an objective with a metric target/progress
history/dependency/every cross-domain link, an initiative linked to that
objective and to a real, assessed ControlMapping (live status read via the
real mirror-table JOIN, not a value captured at link time), and the
Clarification Q2 extension to ADP-SPEC-044's own capability/value-stream
files.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from adp.business import store as bstore
from adp.compliance import store as cstore
from adp.export import business_arch
from adp.export import strategy as strategy_export
from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore

_NOW = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


async def test_first_cycle_bootstraps_full_strategy_export(tmp_path, db_session) -> None:
    theme_id = str(uuid.uuid4())
    obj_id = str(uuid.uuid4())
    obj2_id = str(uuid.uuid4())
    init_id = str(uuid.uuid4())
    cap_id = str(uuid.uuid4())
    design_id = "DSN-STRATEGY-EXPORT-TEST"
    framework_id = str(uuid.uuid4())
    control_id = str(uuid.uuid4())

    await db_session.execute(sstore._themes.insert().values(
        id=theme_id, name="Operational Excellence", description=None, owner=None,
        priority=None, created_at=_NOW,
    ))
    await db_session.execute(sstore._objectives.insert().values(
        id=obj_id, theme_id=theme_id, owner="Alice", statement="Cut MTTR",
        metric_name="MTTR", target_value=Decimal("2.00"), target_unit="hours",
        direction="decrease", fiscal_year=2026, period="Q1",
        status=None, status_reason=None, created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(sstore._objectives.insert().values(
        id=obj2_id, theme_id=theme_id, owner="Bob", statement="Reduce alert noise",
        metric_name=None, target_value=None, target_unit=None, direction=None,
        fiscal_year=2026, period="Q1", status=None, status_reason=None,
        created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(sstore._progress.insert().values(
        objective_id=obj_id, as_of_date=date(2026, 2, 1), actual_value=Decimal("6"),
        note=None, recorded_by="alice", created_at=_NOW,
    ))
    await db_session.execute(sinit._objective_dependencies.insert().values(
        objective_id=obj_id, depends_on_objective_id=obj2_id, created_at=_NOW,
    ))

    # Capability + design link -- exercises both this feature's objective-side
    # capability_ids AND the Clarification Q2 extension to business_arch.py.
    await db_session.execute(bstore._capabilities.insert().values(
        id=cap_id, name="Claims Intake", description=None, level=1,
        parent_id=None, position=0, created_at=_NOW, updated_at=_NOW,
        domain_id=None, strategic_relevance=None, maturity_level=None,
    ))
    await db_session.execute(sstore._objective_capabilities.insert().values(
        objective_id=obj_id, capability_id=cap_id, created_at=_NOW,
    ))
    await db_session.execute(bstore._cap_design_links.insert().values(
        capability_id=cap_id, design_id=design_id, created_at=_NOW,
    ))

    # A real, assessed ControlMapping -- exercises the initiative's live
    # compliance_status JOIN (never a value captured at link time).
    await db_session.execute(cstore._frameworks.insert().values(
        id=framework_id, name="GDPR", jurisdiction="EU", authority="European Commission",
        version="2016/679", effective_date=None, source_url=None,
        regulation_number=None, celex_number=None, adoption_date=None,
        oj_publication_date=None, entry_into_force_date=None, consolidated_as_of=None,
        status="in_force", created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(cstore._controls.insert().values(
        id=control_id, framework_id=framework_id, parent_id=None, code="Art. 32",
        title="Security of processing", description=None, position=0,
        created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(cstore._control_application_mapping.insert().values(
        control_id=control_id, application_id=str(uuid.uuid4()),
        compliance_status="non_compliant", evidence_ref=None, assessed_at=None,
        assessed_by=None, created_at=_NOW,
    ))
    await db_session.execute(sstore._objective_control_links.insert().values(
        objective_id=obj_id, control_id=control_id, created_at=_NOW,
    ))

    await db_session.execute(sinit._initiatives.insert().values(
        id=init_id, name="Remediate MFA gap", description=None, owner=None,
        status="in_progress", created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(sinit._initiative_objective_links.insert().values(
        initiative_id=init_id, objective_id=obj_id, created_at=_NOW,
    ))
    await db_session.flush()

    export_root = tmp_path / "export"
    await strategy_export.run_reconciliation_cycle(export_root, db_session)
    await business_arch.run_reconciliation_cycle(export_root, db_session)

    obj = json.loads((export_root / "strategy" / "objectives" / f"{obj_id}.json").read_text())
    assert obj["theme_id"] == theme_id
    assert obj["capability_ids"] == [cap_id]
    assert obj["control_ids"] == [control_id]
    assert obj["depends_on_objective_ids"] == [obj2_id]
    assert obj["initiative_ids"] == [init_id]
    assert obj["progress"] == [
        {"as_of_date": "2026-02-01", "actual_value": "6", "note": None, "recorded_by": "alice"}
    ]

    obj2 = json.loads((export_root / "strategy" / "objectives" / f"{obj2_id}.json").read_text())
    assert obj2["blocked_objective_ids"] == [obj_id]

    init = json.loads((export_root / "strategy" / "initiatives" / f"{init_id}.json").read_text())
    assert init["objective_ids"] == [obj_id]

    cap = json.loads(
        (export_root / "business-architecture" / "capabilities" / f"{cap_id}.json").read_text()
    )
    assert cap["linked_designs"] == [design_id]
