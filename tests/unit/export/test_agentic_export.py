"""Unit tests for adp.export.agentic (933-agent-registry, ADP-hii): one reconciliation cycle against
a SQLite fixture writes one file per agent with its solutions, and removes files for deleted agents.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.agentic import store as agstore
from adp.agentic.models import AgentCreate
from adp.compliance import store as cstore
from adp.export import agentic as agexport


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(agstore, "index_entity", _noop)
    monkeypatch.setattr(agstore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/export.db")
    async with engine.begin() as conn:
        # agstore owns agents; cstore's narrow agents mirror is then skipped (944).
        await conn.run_sync(agstore._metadata.create_all)
        await conn.run_sync(cstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(
            agstore._applications_mirror.insert().values(
                id="claims", name="Claims", application_type="agentic"
            )
        )
        yield s
    await engine.dispose()


async def test_cycle_writes_agents_with_solutions_and_cleans_orphans(session, tmp_path):
    agent = await agstore.create_agent(
        AgentCreate(
            name="Triage",
            autonomy_level=3,
            human_approval="none",
            est_cost_per_run="0.05",
            runs_per_month=10,
        ),
        session,
    )
    loner = await agstore.create_agent(
        AgentCreate(name="Loner", autonomy_level=0, human_approval="always"), session
    )
    await agstore.add_solution_agent("claims", agent.id, "orchestrator", session)

    root = tmp_path / "out"
    await agexport.run_reconciliation_cycle(root, session)
    agents_dir = root / "agentic" / "agents"
    data = json.loads((agents_dir / f"{agent.id}.json").read_text())
    assert data["name"] == "Triage" and data["autonomy_level"] == 3
    assert data["est_cost_per_run"] == "0.0500" and data["runs_per_month"] == 10
    assert data["solutions"] == [{"app_id": "claims", "role": "orchestrator", "position": 0}]
    assert "exported_at" in data
    assert json.loads((agents_dir / f"{loner.id}.json").read_text())["solutions"] == []

    await agstore.delete_agent(loner.id, session)
    await agexport.run_reconciliation_cycle(root, session)
    assert sorted(p.stem for p in agents_dir.glob("*.json")) == [agent.id]


async def test_cycle_failure_is_swallowed(tmp_path):
    class _Broken:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    await agexport.run_reconciliation_cycle(tmp_path, _Broken())  # must not raise


async def test_cycle_exports_automates_and_compliance(session, tmp_path):
    """944-agent-traceability (US4, FR-018)."""
    from adp.compliance.models import (
        ComplianceStatus,
        ControlCreate,
        ControlMappingWrite,
        RegulatoryFrameworkCreate,
    )

    agent = await agstore.create_agent(
        AgentCreate(name="Chat", autonomy_level=2, human_approval="on_write"), session
    )
    plain = await agstore.create_agent(
        AgentCreate(name="Plain", autonomy_level=0, human_approval="always"), session
    )
    for table, values in [
        (agstore._capabilities_mirror, {"id": "l1", "name": "IT", "level": 1, "parent_id": None}),
        (agstore._capabilities_mirror, {"id": "l3", "name": "Design Validation", "level": 3,
                                        "parent_id": "l1"}),
        (agstore._value_streams_mirror, {"id": "vs", "name": "Design to Deliver"}),
        (agstore._stages_mirror, {"id": "st", "value_stream_id": "vs", "name": "Review",
                                  "position": 0}),
        (agstore._value_chains_mirror, {"id": "ch", "name": "IT"}),
        (agstore._activities_mirror, {"id": "act", "value_chain_id": "ch", "name": "Governance",
                                      "category": "support", "position": 0}),
    ]:
        await session.execute(table.insert().values(**values))
    for kind, target in [("capability", "l3"), ("stage", "st"), ("activity", "act")]:
        await agstore.add_link(kind, agent.id, target, session)
    fw = await cstore.create_framework(
        RegulatoryFrameworkCreate(name="EU AI Act", jurisdiction="EU", authority="EU",
                                  version="2024/1689"),
        session,
    )
    ctrl = await cstore.create_control(
        fw.id, ControlCreate(code="Art. 50", title="Transparency", description="d"), session
    )
    await cstore.upsert_agent_mapping(
        ctrl.id, agent.id, ControlMappingWrite(compliance_status=ComplianceStatus.PARTIAL), session
    )

    root = tmp_path / "out"
    await agexport.run_reconciliation_cycle(root, session)
    agents_dir = root / "agentic" / "agents"
    data = json.loads((agents_dir / f"{agent.id}.json").read_text())
    assert data["automates"] == {
        "capabilities": [{"id": "l3", "name": "Design Validation"}],
        "stages": [{"id": "st", "name": "Review"}],
        "activities": [{"id": "act", "name": "Governance"}],
    }
    assert data["compliance_mappings"] == [
        {"control_id": ctrl.id, "control_code": "Art. 50", "framework_id": fw.id,
         "framework_name": "EU AI Act", "compliance_status": "partial"}
    ]
    other = json.loads((agents_dir / f"{plain.id}.json").read_text())
    assert other["automates"] == {"capabilities": [], "stages": [], "activities": []}
    assert other["compliance_mappings"] == []
