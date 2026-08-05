"""Integration test: one full reconciliation cycle against a real Postgres
container (ADP-SPEC-044 T012), including the pgvector-image container and
real migrations the shared tests/integration/conftest.py fixtures provide.

Seeds data BEFORE ever running a reconciliation cycle, confirming the very
first cycle performs a complete bootstrap export with no separate manual
step (FR-008).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from adp.business import store as bstore
from adp.export import business_arch

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


async def test_first_cycle_bootstraps_full_export(tmp_path, db_session) -> None:
    # Seed BEFORE any reconciliation cycle has ever run against this data --
    # this is the "no separate bootstrap action" case (FR-008).
    await db_session.execute(bstore._domains.insert().values(
        id="domain-1", name="Underwriting", scope_statement=None,
        classification="strategic", org_unit=None, risk_flags=[],
        created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(bstore._capabilities.insert().values(
        id="cap-1", name="Risk Assessment", description=None, level=1,
        parent_id=None, position=0, created_at=_NOW, updated_at=_NOW,
        domain_id="domain-1", strategic_relevance=1, maturity_level=2,
    ))
    await db_session.execute(bstore._value_streams.insert().values(
        id="vs-1", name="Order-to-Cash", description=None, stakeholder=None,
        position=0, created_at=_NOW, updated_at=_NOW,
    ))
    await db_session.execute(bstore._stages.insert().values(
        id="stage-1", value_stream_id="vs-1", name="Quote", description=None, position=0,
    ))
    await db_session.execute(bstore._stage_caps.insert().values(
        stage_id="stage-1", capability_id="cap-1",
    ))
    await db_session.flush()

    export_root = tmp_path / "export"
    await business_arch.run_reconciliation_cycle(export_root, db_session)

    base = export_root / "business-architecture"
    cap = json.loads((base / "capabilities" / "cap-1.json").read_text(encoding="utf-8"))
    assert cap["name"] == "Risk Assessment"
    assert cap["maturity_level"] == 2

    stage = json.loads(
        (base / "value-streams" / "vs-1" / "stages" / "stage-1.json").read_text(encoding="utf-8")
    )
    assert stage["linked_capability_ids"] == ["cap-1"]
