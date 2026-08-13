"""Contract tests for the Strategic Objective Capture API (ADP-d8u.1).

Full-stack against the real router on in-memory SQLite -- mirrors
tests/contract/test_business_registry_api.py's and test_diagrams_api_
contract.py's own fixture conventions, combined: a strategy-scoped
database plus a *second*, business-scoped database (for the link
endpoints' cross-package existence validation, research.md Decision 2),
each overriding the router's respective session dependency.

Auth is disabled in tests, so the default caller is ENTERPRISE_ARCHITECT,
which holds WRITE_BUSINESS_ARCH via its wildcard grant -- no per-test role
override needed for the happy paths; the denial path is covered by
tests/authz/test_enforcement.py's route-completeness gate, which will fail
if /api/v1/strategy/ isn't present in _PREFIX_ROUTE_ACTIONS.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore
from adp.strategy import router as srouter
from adp.strategy import store as sstore

_STRATEGY_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_soc ON strategic_objective_capabilities(objective_id, capability_id)",
    "CREATE UNIQUE INDEX uq_sovs "
    "ON strategic_objective_value_streams(objective_id, value_stream_id)",
    "CREATE UNIQUE INDEX uq_progress ON strategic_objective_progress(objective_id, as_of_date)",
]


@pytest.fixture()
async def client(tmp_path):
    strategy_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy.db")
    async with strategy_engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        for ddl in _STRATEGY_UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    strategy_factory = async_sessionmaker(strategy_engine, expire_on_commit=False)

    business_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with business_engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    business_factory = async_sessionmaker(business_engine, expire_on_commit=False)

    # Seed one real capability + value stream to link against (research.md
    # Decision 2's target of the cross-package existence check).
    now = datetime.now(timezone.utc)
    async with business_factory() as session:
        await session.execute(
            bstore._capabilities.insert().values(
                id="cap-1", name="Claims Processing", level=1, parent_id=None,
                position=0, created_at=now, updated_at=now,
            )
        )
        await session.execute(
            bstore._value_streams.insert().values(
                id="vs-1", name="Claim to Payout", position=0,
                created_at=now, updated_at=now,
            )
        )
        await session.commit()

    from adp.api.app import create_app

    app = create_app()

    async def _strategy_override():
        async with strategy_factory() as session:
            yield session

    async def _business_override():
        async with business_factory() as session:
            yield session

    app.dependency_overrides[srouter._get_session] = _strategy_override
    app.dependency_overrides[srouter._get_business_session] = _business_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await strategy_engine.dispose()
    await business_engine.dispose()


BASE = "/api/v1/strategy"


async def _mk_theme(client, name="Growth") -> str:
    resp = await client.post(f"{BASE}/themes", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _mk_objective(client, theme_id: str, **overrides) -> dict:
    body = {
        "theme_id": theme_id,
        "owner": "Claims Platform Team",
        "statement": "Reduce claims cycle time",
        "fiscal_year": 2026,
        "period": "Q3",
    }
    body.update(overrides)
    resp = await client.post(f"{BASE}/objectives", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── User Story 1: themes + objective create/read ──────────────────────────────


async def test_create_theme_201(client) -> None:
    resp = await client.post(f"{BASE}/themes", json={"name": "Usage-based pricing"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "Usage-based pricing"


async def test_create_theme_duplicate_name_409(client) -> None:
    await _mk_theme(client, "Growth")
    resp = await client.post(f"{BASE}/themes", json={"name": "Growth"})
    assert resp.status_code == 409


async def test_list_themes(client) -> None:
    await _mk_theme(client, "Growth")
    resp = await client.get(f"{BASE}/themes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Growth"


async def test_create_objective_201_with_all_core_fields(client) -> None:
    theme_id = await _mk_theme(client)
    body = await _mk_objective(
        client, theme_id,
        metric_name="Claims cycle time", target_value=40, target_unit="%", direction="decrease",
    )
    assert body["theme_id"] == theme_id
    assert body["owner"] == "Claims Platform Team"
    assert body["metric_name"] == "Claims cycle time"
    assert body["direction"] == "decrease"
    assert body["capability_ids"] == []
    assert body["value_stream_ids"] == []


async def test_create_objective_404_unknown_theme(client) -> None:
    resp = await client.post(
        f"{BASE}/objectives",
        json={
            "theme_id": "nonexistent", "owner": "X", "statement": "Y",
            "fiscal_year": 2026, "period": "Q1",
        },
    )
    assert resp.status_code == 404


async def test_create_objective_422_blank_owner(client) -> None:
    theme_id = await _mk_theme(client)
    resp = await client.post(
        f"{BASE}/objectives",
        json={
            "theme_id": theme_id, "owner": "   ", "statement": "Y",
            "fiscal_year": 2026, "period": "Q1",
        },
    )
    assert resp.status_code == 422


async def test_create_objective_422_blank_statement(client) -> None:
    theme_id = await _mk_theme(client)
    resp = await client.post(
        f"{BASE}/objectives",
        json={
            "theme_id": theme_id, "owner": "X", "statement": "",
            "fiscal_year": 2026, "period": "Q1",
        },
    )
    assert resp.status_code == 422


async def test_create_objective_422_partial_metric_group(client) -> None:
    theme_id = await _mk_theme(client)
    resp = await client.post(
        f"{BASE}/objectives",
        json={
            "theme_id": theme_id, "owner": "X", "statement": "Y",
            "fiscal_year": 2026, "period": "Q1", "metric_name": "Latency",
        },
    )
    assert resp.status_code == 422


async def test_get_objective_reads_it_back(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.get(f"{BASE}/objectives/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_objective_404_unknown_id(client) -> None:
    resp = await client.get(f"{BASE}/objectives/nonexistent")
    assert resp.status_code == 404


# ── User Story 2: link/unlink capabilities and value streams ──────────────────


async def test_link_capability_201_returns_updated_list(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/capabilities", json={"capability_id": "cap-1"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json() == ["cap-1"]


async def test_link_capability_404_unknown_capability(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/capabilities",
        json={"capability_id": "nonexistent-cap"},
    )
    assert resp.status_code == 404


async def test_link_capability_404_unknown_objective(client) -> None:
    resp = await client.post(
        f"{BASE}/objectives/nonexistent/capabilities", json={"capability_id": "cap-1"}
    )
    assert resp.status_code == 404


async def test_link_capability_409_already_linked(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/capabilities", json={"capability_id": "cap-1"}
    )
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/capabilities", json={"capability_id": "cap-1"}
    )
    assert resp.status_code == 409


async def test_unlink_capability_204_removes_only_the_link(client) -> None:
    # This fixture's /api/v1/business/* endpoints aren't wired to the same
    # business_factory (only /api/v1/strategy's cross-package validation
    # dependency is overridden here) -- spec.md Acceptance Scenario 3's
    # "the capability itself is unaffected" is exercised in full against
    # the real business router in tests/contract/test_business_registry_
    # api.py; here we confirm this endpoint's own contract: it deletes
    # exactly the link row, nothing else in adp.strategy's own data.
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/capabilities", json={"capability_id": "cap-1"}
    )
    resp = await client.delete(f"{BASE}/objectives/{created['id']}/capabilities/cap-1")
    assert resp.status_code == 204

    objective_resp = await client.get(f"{BASE}/objectives/{created['id']}")
    assert objective_resp.json()["capability_ids"] == []
    assert objective_resp.json()["owner"] == created["owner"]  # rest of the objective untouched


async def test_unlink_capability_404_not_linked(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.delete(f"{BASE}/objectives/{created['id']}/capabilities/cap-1")
    assert resp.status_code == 404


async def test_link_value_stream_201_returns_updated_list(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/value-streams", json={"value_stream_id": "vs-1"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json() == ["vs-1"]


async def test_link_value_stream_404_unknown_value_stream(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/value-streams",
        json={"value_stream_id": "nonexistent-vs"},
    )
    assert resp.status_code == 404


async def test_unlink_value_stream_204(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/value-streams", json={"value_stream_id": "vs-1"}
    )
    resp = await client.delete(f"{BASE}/objectives/{created['id']}/value-streams/vs-1")
    assert resp.status_code == 204


# ── User Story 3: list / update / delete ───────────────────────────────────────


async def test_list_objectives_multiple_summaries(client) -> None:
    theme_id = await _mk_theme(client)
    await _mk_objective(client, theme_id, owner="Owner A")
    await _mk_objective(client, theme_id, owner="Owner B")
    resp = await client.get(f"{BASE}/objectives")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    owners = {item["owner"] for item in body["items"]}
    assert owners == {"Owner A", "Owner B"}
    assert all("capability_ids" not in item for item in body["items"])


async def test_update_objective_persists_edit(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.put(
        f"{BASE}/objectives/{created['id']}", json={"owner": "New Owner"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["owner"] == "New Owner"
    assert resp.json()["statement"] == created["statement"]  # untouched


async def test_update_objective_404_unknown_id(client) -> None:
    resp = await client.put(f"{BASE}/objectives/nonexistent", json={"owner": "X"})
    assert resp.status_code == 404


async def test_delete_objective_then_get_404(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective(client, theme_id)
    resp = await client.delete(f"{BASE}/objectives/{created['id']}")
    assert resp.status_code == 204

    get_resp = await client.get(f"{BASE}/objectives/{created['id']}")
    assert get_resp.status_code == 404


async def test_delete_objective_404_unknown_id(client) -> None:
    resp = await client.delete(f"{BASE}/objectives/nonexistent")
    assert resp.status_code == 404


# ── GET /strategy/summary (051-strategy-landing-card) ──────────────────────────
#
# A dedicated fixture, not the module's real-SQLite `client` fixture above:
# get_summary_stats's raw SQL uses NOW()/EXTRACT(), which is Postgres-only
# syntax SQLite can't execute -- mirrors tests/contract/test_portfolio_api.py's
# own session-mock pattern for the exact same class of endpoint.

@pytest.fixture()
async def summary_client(mocked_summary_session):
    from adp.api.app import create_app

    app = create_app()

    async def _override():
        yield mocked_summary_session

    app.dependency_overrides[srouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _mock_row(**fields):
    row = MagicMock()
    row.__getitem__.side_effect = lambda k: fields[k]
    return row


@pytest.fixture()
def mocked_summary_session():
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first = MagicMock(
        return_value=_mock_row(
            total_themes=4,
            total_objectives=12,
            linked_count=9,
            unlinked_count=3,
            current_period_count=5,
            upcoming_count=4,
            past_due_count=3,
        )
    )
    session.execute = AsyncMock(return_value=result)
    return session


async def test_get_summary_200_with_all_fields(summary_client) -> None:
    resp = await summary_client.get(f"{BASE}/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "total_themes": 4,
        "total_objectives": 12,
        "linked_count": 9,
        "unlinked_count": 3,
        "current_period_count": 5,
        "upcoming_count": 4,
        "past_due_count": 3,
    }


async def test_get_summary_rejects_unexpected_fields(summary_client) -> None:
    # extra="forbid" on StrategicSummaryResponse -- confirms the endpoint
    # never leaks a stray field, mirroring every other ADP boundary model.
    resp = await summary_client.get(f"{BASE}/summary")
    assert resp.status_code == 200
    assert set(resp.json().keys()) == {
        "total_themes", "total_objectives", "linked_count", "unlinked_count",
        "current_period_count", "upcoming_count", "past_due_count",
    }


async def test_get_summary_all_zero_on_empty_database() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.first = MagicMock(
        return_value=_mock_row(
            total_themes=0, total_objectives=0, linked_count=0, unlinked_count=0,
            current_period_count=0, upcoming_count=0, past_due_count=0,
        )
    )
    session.execute = AsyncMock(return_value=result)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        yield session

    app.dependency_overrides[srouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(f"{BASE}/summary")

    assert resp.status_code == 200, resp.text
    assert all(v == 0 for v in resp.json().values())


# ── User Story 1 (ADP-d8u.5): objective progress + computed status ────────────


async def _mk_objective_with_target(client, theme_id: str, direction="increase") -> dict:
    return await _mk_objective(
        client, theme_id,
        metric_name="Metric", target_value=100, target_unit="%", direction=direction,
    )


async def test_get_objective_includes_proposed_status_with_no_progress(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    resp = await client.get(f"{BASE}/objectives/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "proposed"


async def test_create_progress_entry_201(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 40},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["as_of_date"] == "2026-08-01"
    assert body["actual_value"] == "40.00"
    assert body["recorded_by"]

    # And the objective now reads a non-"proposed" computed status.
    obj_resp = await client.get(f"{BASE}/objectives/{created['id']}")
    assert obj_resp.json()["status"] == "active"


async def test_create_progress_entry_404_unknown_objective(client) -> None:
    resp = await client.post(
        f"{BASE}/objectives/nonexistent/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 40},
    )
    assert resp.status_code == 404


async def test_create_progress_entry_409_duplicate_date(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 40},
    )
    resp = await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 99},
    )
    assert resp.status_code == 409


async def test_list_progress_entries_200(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 40},
    )
    await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-08", "actual_value": 55},
    )
    resp = await client.get(f"{BASE}/objectives/{created['id']}/progress")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert [e["as_of_date"] for e in body["items"]] == ["2026-08-01", "2026-08-08"]


async def test_list_progress_entries_404_unknown_objective(client) -> None:
    resp = await client.get(f"{BASE}/objectives/nonexistent/progress")
    assert resp.status_code == 404


async def test_patch_progress_entry_200_edits_in_place(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 40},
    )
    resp = await client.patch(
        f"{BASE}/objectives/{created['id']}/progress/2026-08-01",
        json={"actual_value": 100, "note": "corrected"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["actual_value"] == "100.00"
    assert body["note"] == "corrected"
    assert body["as_of_date"] == "2026-08-01"


async def test_patch_progress_entry_404_unknown_date(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    resp = await client.patch(
        f"{BASE}/objectives/{created['id']}/progress/2099-01-01",
        json={"actual_value": 1},
    )
    assert resp.status_code == 404


# ── User Story 2 (ADP-d8u.5): abandon ─────────────────────────────────────────


async def test_abandon_objective_200_with_reason(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    resp = await client.patch(
        f"{BASE}/objectives/{created['id']}/abandon",
        json={"status_reason": "Superseded by a broader objective"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "abandoned"
    assert body["status_reason"] == "Superseded by a broader objective"


async def test_abandon_objective_400_no_reason(client) -> None:
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    resp = await client.patch(f"{BASE}/objectives/{created['id']}/abandon", json={})
    assert resp.status_code == 422  # extra="forbid" + min_length=1 -- FastAPI validation, not 400


async def test_abandon_objective_404_unknown_id(client) -> None:
    resp = await client.patch(
        f"{BASE}/objectives/nonexistent/abandon", json={"status_reason": "X"}
    )
    assert resp.status_code == 404


async def test_abandon_objective_wins_over_achieved_progress(client) -> None:
    # FR-011: abandoned always short-circuits compute_status, even if the
    # progress trend would otherwise read "achieved".
    theme_id = await _mk_theme(client)
    created = await _mk_objective_with_target(client, theme_id)
    await client.post(
        f"{BASE}/objectives/{created['id']}/progress",
        json={"as_of_date": "2026-08-01", "actual_value": 100},
    )
    await client.patch(
        f"{BASE}/objectives/{created['id']}/abandon", json={"status_reason": "Cancelled"}
    )
    resp = await client.get(f"{BASE}/objectives/{created['id']}")
    assert resp.json()["status"] == "abandoned"


# ── User Story 3 (ADP-d8u.5): theme lifecycle completion ──────────────────────


async def test_create_theme_accepts_description_owner_priority(client) -> None:
    resp = await client.post(
        f"{BASE}/themes",
        json={
            "name": "Digital Channels",
            "description": "Customer-facing digital experience",
            "owner": "jane.architect",
            "priority": 2,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["description"] == "Customer-facing digital experience"
    assert body["owner"] == "jane.architect"
    assert body["priority"] == 2


async def test_get_theme_200(client) -> None:
    theme_id = await _mk_theme(client, "Growth")
    resp = await client.get(f"{BASE}/themes/{theme_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Growth"


async def test_get_theme_404_unknown_id(client) -> None:
    resp = await client.get(f"{BASE}/themes/nonexistent")
    assert resp.status_code == 404


async def test_patch_theme_200_updates_fields(client) -> None:
    theme_id = await _mk_theme(client, "Growth")
    resp = await client.patch(f"{BASE}/themes/{theme_id}", json={"priority": 1})
    assert resp.status_code == 200, resp.text
    assert resp.json()["priority"] == 1


async def test_patch_theme_404_unknown_id(client) -> None:
    resp = await client.patch(f"{BASE}/themes/nonexistent", json={"priority": 1})
    assert resp.status_code == 404


async def test_delete_theme_204_when_unused(client) -> None:
    theme_id = await _mk_theme(client, "Unused Theme")
    resp = await client.delete(f"{BASE}/themes/{theme_id}")
    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/themes/{theme_id}")).status_code == 404


async def test_delete_theme_409_when_referenced(client) -> None:
    theme_id = await _mk_theme(client, "In Use")
    await _mk_objective(client, theme_id)
    resp = await client.delete(f"{BASE}/themes/{theme_id}")
    assert resp.status_code == 409


async def test_delete_theme_404_unknown_id(client) -> None:
    resp = await client.delete(f"{BASE}/themes/nonexistent")
    assert resp.status_code == 404
