"""build_snapshot over SQLite mirrors (936 FR-005–FR-007, research D3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.patterns import snapshot_store as ss
from adp.patterns import store as pstore
from adp.patterns.models import ElementType as T
from adp.patterns.snapshot_store import SnapshotPermissions, build_snapshot


async def _costs(_session) -> dict:  # type: ignore[no-untyped-def]
    return {"a1": Decimal("1234.50")}


def _app(aid: str, name: str, **kw) -> dict:  # type: ignore[no-untyped-def]
    return {"id": aid, "name": name, "lifecycle_status": "active", "tech_debt_flags": [], **kw}


async def _insert(s, table, rows) -> None:  # type: ignore[no-untyped-def]
    for row in rows:  # rows have different keys; executemany would need uniform ones
        await s.execute(table.insert().values(**row))


@pytest.fixture()
async def session_and_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/snapshot.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await _insert(
            s,
            ss._domains,
            [
                {
                    "id": "d1",
                    "name": "Claims",
                    "classification": "strategic",
                    "risk_flags": ["pii"],
                },
                {"id": "d2", "name": "Billing", "classification": "commodity", "risk_flags": []},
            ],
        )
        await _insert(
            s,
            ss._capabilities,
            [
                {"id": "c1", "name": "Claims", "level": 1, "parent_id": None, "domain_id": "d1"},
                {"id": "c1a", "name": "Intake", "level": 2, "parent_id": "c1", "domain_id": None},
                {"id": "c2", "name": "Billing", "level": 1, "parent_id": None, "domain_id": "d2"},
            ],
        )
        await _insert(
            s,
            pstore._applications_mirror,
            [
                _app("a1", "Claims Core", time_classification="Invest", application_type="custom"),
                _app("a2", "Billing", time_classification="Tolerate"),
                _app("a3", "Orphan"),
            ],
        )
        await _insert(
            s,
            ss._cap_links,
            [
                {"app_id": "a1", "capability_id": "c1a"},
                {"app_id": "a1", "capability_id": "c2"},
                {"app_id": "a2", "capability_id": "c2"},
            ],
        )
        await _insert(s, ss._tech_caps, [{"id": "t1", "name": "Streaming", "level": 1}])
        await _insert(
            s,
            ss._tcap_links,
            [
                {"app_id": "a1", "tech_cap_id": "t1", "usage_type": "provides"},
                {"app_id": "a2", "tech_cap_id": "t1", "usage_type": "consumes"},
            ],
        )
        await _insert(
            s,
            ss._integrations,
            [
                {
                    "id": "i1",
                    "source_app_id": "a1",
                    "target_app_id": "a2",
                    "integration_type": "API",
                },
                {
                    "id": "i2",
                    "source_app_id": "a3",
                    "target_app_id": "a1",
                    "integration_type": "file",
                },
            ],
        )
        await _insert(s, ss._value_streams, [{"id": "vs1", "name": "Order to cash"}])
        await _insert(
            s,
            ss._stages,
            [
                {"id": "st2", "value_stream_id": "vs1", "position": 2},
                {"id": "st1", "value_stream_id": "vs1", "position": 1},
            ],
        )
        await _insert(
            s,
            ss._agents,
            [
                {
                    "id": "g1",
                    "name": "Triage",
                    "lifecycle_status": "active",
                    "autonomy_level": 2,
                    "human_approval": "always",
                },
            ],
        )
        await _insert(s, ss._solution_agents, [{"solution_app_id": "a1", "agent_id": "g1"}])
        await _insert(
            s,
            ss._risk,
            [
                {
                    "app_id": "a1",
                    "security_posture": "weak",
                    "end_of_support_date": date(2027, 1, 31),
                },
            ],
        )
        await _insert(s, ss._contracts, [{"app_id": "a2", "sla": "99.9"}])
        await s.commit()
        yield s, engine
    await engine.dispose()


async def test_elements_and_domain_derivation(session_and_engine) -> None:
    s, _ = session_and_engine
    snap = await build_snapshot(s, SnapshotPermissions(), cost_loader=_costs)
    a1 = snap.element(T.APPLICATION, "a1")
    assert a1 is not None
    assert a1["domain_ids"] == ["d1", "d2"]  # c1a -> L1 c1 (d1), c2 (d2)
    assert a1["capability_ids"] == ["c1a", "c2"]
    assert a1["technical_capability_ids"] == ["t1"]
    assert snap.element(T.APPLICATION, "a3")["domain_ids"] == []  # type: ignore[index]
    assert snap.element(T.BUSINESS_CAPABILITY, "c1a")["domain_id"] == "d1"  # type: ignore[index]
    assert snap.realizes("a1", "t1") and not snap.realizes("a2", "t1")
    assert snap.element(T.BUSINESS_DOMAIN, "d1")["risk_flags"] == ["pii"]  # type: ignore[index]
    assert snap.element(T.VALUE_STREAM, "vs1")["stage_ids"] == ["st1", "st2"]  # type: ignore[index]
    assert snap.element(T.AGENT, "g1")["solution_ids"] == ["a1"]  # type: ignore[index]


async def test_integration_endpoints(session_and_engine) -> None:
    s, _ = session_and_engine
    snap = await build_snapshot(s, SnapshotPermissions(), cost_loader=_costs)
    i1 = snap.element(T.INTEGRATION, "i1")
    assert i1 is not None
    assert i1["name"] == "Claims Core → Billing"
    assert i1["cross_domain"] is False  # a1 is also in d2
    assert snap.element(T.INTEGRATION, "i2")["cross_domain"] is None  # type: ignore[index]


async def test_gated_fields_follow_permissions(session_and_engine) -> None:
    s, _ = session_and_engine
    none = await build_snapshot(s, SnapshotPermissions(), cost_loader=_costs)
    a1 = none.element(T.APPLICATION, "a1")
    assert a1 is not None
    for f in ("security_posture", "tco", "sla", "end_of_support_date"):
        assert f not in a1
    assert {"tco", "sla", "security_posture"} <= none.unavailable_fields

    full = await build_snapshot(
        s, SnapshotPermissions(risk=True, cost=True, governance=True), cost_loader=_costs
    )
    a1 = full.element(T.APPLICATION, "a1")
    a2 = full.element(T.APPLICATION, "a2")
    assert a1 is not None and a2 is not None
    assert (a1["security_posture"], a1["end_of_support_date"]) == ("weak", "2027-01-31")
    assert a1["tco"] == 1234.5 and a2["tco"] is None
    assert a2["sla"] == "99.9" and a1["sla"] is None
    assert a2["security_posture"] is None  # permitted but no risk row: present as null
    assert full.unavailable_fields == frozenset()


async def test_query_count_is_bounded(session_and_engine) -> None:
    s, engine = session_and_engine
    statements: list[str] = []

    def count(conn, cursor, statement, *args):  # type: ignore[no-untyped-def]
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sa.event.listen(engine.sync_engine, "before_cursor_execute", count)
    await build_snapshot(s, SnapshotPermissions(risk=True, governance=True), cost_loader=_costs)
    first = len(statements)
    for i in range(20):  # 20 more apps must not add queries
        await s.execute(pstore._applications_mirror.insert().values(**_app(f"x{i}", f"X{i}")))
    statements.clear()
    await build_snapshot(s, SnapshotPermissions(risk=True, governance=True), cost_loader=_costs)
    assert len(statements) == first <= 13
