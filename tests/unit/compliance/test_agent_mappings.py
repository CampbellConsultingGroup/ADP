"""Unit tests for Agent as the sixth compliance mapping target (944-agent-traceability, ADP-12x,
US2) against a SQLite fixture. Agents are inserted through cstore's narrow `agents` mirror, so no
adp.agentic metadata is needed.

Covers: upsert (insert then update in place), unknown control / agent, list_mappings_for_agent,
list_mappings_for_control including agent rows, get_entity_compliance_status(AGENT), roll-up and
summary counting agents, delete, and bulk statuses.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import store as cstore
from adp.compliance.models import (
    ComplianceStatus,
    ControlCreate,
    ControlMappingWrite,
    ControlNotFoundError,
    MappingNotFoundError,
    MappingTargetNotFoundError,
    MappingTargetType,
    RegulatoryFrameworkCreate,
)


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/agent_mappings.db")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        for agent_id, name in [("ag1", "Chat assistant"), ("ag2", "Intake extractor")]:
            await s.execute(cstore._agents_mirror.insert().values(id=agent_id, name=name))
        await s.execute(cstore._capabilities_mirror.insert().values(id="cap1"))
        yield s
    await engine.dispose()


async def _framework_and_controls(session) -> tuple[str, str, str]:
    fw = await cstore.create_framework(
        RegulatoryFrameworkCreate(
            name="EU AI Act", jurisdiction="EU", authority="EU", version="2024/1689"
        ),
        session,
    )
    c1 = await cstore.create_control(
        fw.id, ControlCreate(code="Art. 50", title="T", description="d"), session
    )
    c2 = await cstore.create_control(
        fw.id, ControlCreate(code="Art. 13", title="T", description="d"), session
    )
    return fw.id, c1.id, c2.id


def _write(status: str, **extra) -> ControlMappingWrite:
    return ControlMappingWrite(compliance_status=ComplianceStatus(status), **extra)


async def test_upsert_inserts_then_updates_in_place(session):
    _fw, c1, _c2 = await _framework_and_controls(session)
    m = await cstore.upsert_agent_mapping(c1, "ag1", _write("partial"), session)
    assert (m.target_type, m.target_id, m.compliance_status) == (
        MappingTargetType.AGENT, "ag1", ComplianceStatus.PARTIAL
    )
    m2 = await cstore.upsert_agent_mapping(
        c1, "ag1", _write("compliant", evidence_ref="DPIA-7"), session
    )
    assert m2.compliance_status == ComplianceStatus.COMPLIANT and m2.evidence_ref == "DPIA-7"
    assert len(await cstore.list_mappings_for_agent("ag1", session)) == 1


async def test_unknown_control_or_agent(session):
    _fw, c1, _c2 = await _framework_and_controls(session)
    with pytest.raises(ControlNotFoundError):
        await cstore.upsert_agent_mapping("nope", "ag1", _write("compliant"), session)
    with pytest.raises(MappingTargetNotFoundError):
        await cstore.upsert_agent_mapping(c1, "nope", _write("compliant"), session)


async def test_control_list_includes_agent_rows(session):
    _fw, c1, _c2 = await _framework_and_controls(session)
    await cstore.upsert_capability_mapping(c1, "cap1", _write("compliant"), session)
    await cstore.upsert_agent_mapping(c1, "ag1", _write("partial"), session)
    types = {m.target_type for m in await cstore.list_mappings_for_control(c1, session)}
    assert types == {MappingTargetType.CAPABILITY, MappingTargetType.AGENT}


async def test_agent_status_is_worst_and_not_assessed_without_mappings(session):
    _fw, c1, c2 = await _framework_and_controls(session)
    assert (
        await cstore.get_entity_compliance_status(MappingTargetType.AGENT, "ag1", session)
        == ComplianceStatus.NOT_ASSESSED
    )
    await cstore.upsert_agent_mapping(c1, "ag1", _write("compliant"), session)
    await cstore.upsert_agent_mapping(c2, "ag1", _write("non_compliant"), session)
    assert (
        await cstore.get_entity_compliance_status(MappingTargetType.AGENT, "ag1", session)
        == ComplianceStatus.NON_COMPLIANT
    )


async def test_rollup_and_summary_count_agents(session):
    fw, c1, c2 = await _framework_and_controls(session)
    await cstore.upsert_capability_mapping(c1, "cap1", _write("compliant"), session)
    before = await cstore.get_framework_coverage_rollup(fw, True, session)
    assert before is not None and before.entity_counts.compliant_count == 1

    await cstore.upsert_agent_mapping(c1, "ag1", _write("compliant"), session)
    await cstore.upsert_agent_mapping(c2, "ag2", _write("non_compliant"), session)
    after = await cstore.get_framework_coverage_rollup(fw, True, session)
    assert after is not None
    assert after.entity_counts.compliant_count == 2  # the capability, unchanged, plus ag1
    assert after.entity_counts.non_compliant_count == 1

    summary = await cstore.get_compliance_summary(True, session)
    assert summary.at_risk_count == 1


async def test_delete_agent_mapping(session):
    _fw, c1, _c2 = await _framework_and_controls(session)
    await cstore.upsert_agent_mapping(c1, "ag1", _write("compliant"), session)
    await cstore.delete_agent_mapping(c1, "ag1", session)
    assert await cstore.list_mappings_for_agent("ag1", session) == []
    with pytest.raises(MappingNotFoundError):
        await cstore.delete_agent_mapping(c1, "ag1", session)


async def test_agent_statuses_bulk(session):
    _fw, c1, c2 = await _framework_and_controls(session)
    await cstore.upsert_agent_mapping(c1, "ag1", _write("compliant"), session)
    await cstore.upsert_agent_mapping(c2, "ag1", _write("partial"), session)
    out = await cstore.get_agent_statuses(["ag1", "ag2", "unknown"], session)
    assert out == {
        "ag1": ComplianceStatus.PARTIAL,
        "ag2": ComplianceStatus.NOT_ASSESSED,
        "unknown": ComplianceStatus.NOT_ASSESSED,
    }


async def test_agent_exists(session):
    assert await cstore.agent_exists("ag1", session)
    assert not await cstore.agent_exists("nope", session)
