"""Contract tests for the Design List + Create API (ADP-SPEC-025 T001-T005)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription


def _make_design(design_id: str, title: str = "Test Design") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": title,
        "created_at": "2026-07-03T10:00:00Z",
        "updated_at": "2026-07-03T10:00:00Z",
        "elements": [],
        "requirements": [],
        "relationships": [],
    })


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import designs as designs_module

    app = create_app()
    mock_store = AsyncMock()
    mock_store.save = AsyncMock()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[designs_module._get_design_store] = _fake_store
    return TestClient(app, raise_server_exceptions=True), mock_store, designs_module


# ── T001: empty list ──────────────────────────────────────────────────────────

def test_list_designs_returns_empty_list(client):
    c, mock_store, _ = client
    mock_store.list_all = AsyncMock(return_value=[])
    mock_store.count_all = AsyncMock(return_value=0)
    resp = c.get("/api/v1/designs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["designs"] == []
    assert body["total"] == 0


# ── T002: summaries ───────────────────────────────────────────────────────────

def test_list_designs_returns_summaries(client):
    c, mock_store, _ = client
    d1 = _make_design("DSN-001", "Alpha Design")
    d2 = _make_design("DSN-002", "Beta Design")
    mock_store.list_all = AsyncMock(return_value=[d1, d2])
    mock_store.count_all = AsyncMock(return_value=2)
    resp = c.get("/api/v1/designs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = {d["id"] for d in body["designs"]}
    assert "DSN-001" in ids
    assert "DSN-002" in ids
    # Check required fields
    d = body["designs"][0]
    assert "id" in d
    assert "title" in d
    assert "element_count" in d
    assert "created_at" in d


# ── T003: create returns 201 ──────────────────────────────────────────────────

def test_create_design_returns_201(client):
    c, mock_store, _ = client
    mock_store.count_all = AsyncMock(return_value=0)
    mock_store.list_all = AsyncMock(return_value=[])  # no existing designs → DSN-001
    mock_store.next_design_id = AsyncMock(return_value="DSN-001")

    created_design = None

    async def _fake_save(design, actor="system"):
        nonlocal created_design
        created_design = design

    mock_store.save = AsyncMock(side_effect=_fake_save)

    resp = c.post("/api/v1/designs", json={"title": "My New Design"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "My New Design"
    assert "id" in body
    assert body["elements"] == []
    assert body["requirements"] == []
    assert body["relationships"] == []


# ── T004: blank title returns 422 ────────────────────────────────────────────

def test_create_design_blank_title_returns_422(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs", json={"title": ""})
    assert resp.status_code == 422


def test_create_design_whitespace_title_returns_422(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs", json={"title": "   "})
    assert resp.status_code == 422


# ── T005: audit entry written ─────────────────────────────────────────────────

def test_create_design_audit_entry_written(client):
    c, mock_store, _ = client
    mock_store.count_all = AsyncMock(return_value=0)
    mock_store.list_all = AsyncMock(return_value=[])
    mock_store.next_design_id = AsyncMock(return_value="DSN-001")

    saved: list[ArchitectureDescription] = []

    async def _capture_save(design, actor="system"):
        saved.append(design)

    mock_store.save = AsyncMock(side_effect=_capture_save)

    resp = c.post("/api/v1/designs", json={"title": "Audited Design"})
    assert resp.status_code == 201
    assert len(saved) == 1
    design = saved[0]
    assert len(design.audit_log) == 1
    assert design.audit_log[0].action == "design-created"


# ── ADP-SPEC-030: Lifecycle filter + default status ───────────────────────────

def test_list_designs_filter_by_status(client):
    """T016: GET /designs?status=current returns only current designs."""
    from unittest.mock import AsyncMock

    from adp.models import LifecycleStatus

    c, mock_store, _ = client
    d1 = _make_design("DSN-001", "Current Design")
    d2 = _make_design("DSN-002", "Draft Design")
    d1.lifecycle_status = LifecycleStatus.CURRENT
    d2.lifecycle_status = LifecycleStatus.DRAFT

    mock_store.list_all = AsyncMock(return_value=[d1])  # store pre-filtered
    mock_store.count_all = AsyncMock(return_value=1)

    resp = c.get("/api/v1/designs?status=current")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["designs"]) == 1
    assert body["designs"][0]["lifecycle_status"] == "current"


def test_list_designs_no_filter_returns_all(client):
    """T017: GET /designs without status returns all designs."""
    from unittest.mock import AsyncMock

    from adp.models import LifecycleStatus

    c, mock_store, _ = client
    d1 = _make_design("DSN-001", "Current Design")
    d2 = _make_design("DSN-002", "Draft Design")
    d1.lifecycle_status = LifecycleStatus.CURRENT
    d2.lifecycle_status = LifecycleStatus.DRAFT

    mock_store.list_all = AsyncMock(return_value=[d1, d2])
    mock_store.count_all = AsyncMock(return_value=2)

    resp = c.get("/api/v1/designs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


def test_create_design_defaults_lifecycle_to_draft(client):
    """T018: New designs default to draft status."""
    from unittest.mock import AsyncMock

    c, mock_store, _ = client
    mock_store.count_all = AsyncMock(return_value=0)
    mock_store.list_all = AsyncMock(return_value=[])
    mock_store.next_design_id = AsyncMock(return_value="DSN-001")
    mock_store.save = AsyncMock()

    resp = c.post("/api/v1/designs", json={"title": "New Design"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["lifecycle_status"] == "draft"
    assert body["proposed_date"] is None
    assert body["current_since"] is None
    assert body["review_due"] is None
    assert body["retirement_date"] is None


# ── ADP-d8u.2: GET /designs/{id}/objectives (reverse lookup) ───────────────────
#
# Separate, async httpx-based fixture (unlike the synchronous, fully-mocked
# `client` fixture above) since this endpoint genuinely reads real strategy-
# scoped data (adp.strategy.store's objective_design_links table) through a
# new _get_strategy_session dependency, alongside the existing mocked
# DesignStore (used only for the design-exists 404 check).

import httpx  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from adp.store.store import DesignNotFoundError  # noqa: E402


@pytest.fixture()
async def objectives_lookup_client(tmp_path):
    from adp.api.app import create_app
    from adp.api.routers import designs as designs_module
    from adp.strategy import store as sstore

    strategy_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/strategy.db")
    async with strategy_engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        await conn.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_odl ON objective_design_links(objective_id, design_id)"
            )
        )
    strategy_factory = async_sessionmaker(strategy_engine, expire_on_commit=False)

    app = create_app()
    mock_store = AsyncMock()

    async def _get_design(design_id: str, version: int | None = None):
        if design_id != "DSN-001":
            raise DesignNotFoundError(design_id, f"Design {design_id!r} not found")
        return _make_design(design_id)

    mock_store.get = AsyncMock(side_effect=_get_design)

    async def _fake_store():
        return mock_store

    async def _strategy_override():
        async with strategy_factory() as session:
            yield session

    app.dependency_overrides[designs_module._get_design_store] = _fake_store
    app.dependency_overrides[designs_module._get_strategy_session] = _strategy_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, strategy_factory
    await strategy_engine.dispose()


async def test_get_design_objectives_404_unknown_design(objectives_lookup_client) -> None:
    c, _ = objectives_lookup_client
    resp = await c.get("/api/v1/designs/nonexistent/objectives")
    assert resp.status_code == 404


async def test_get_design_objectives_200_reflects_real_links(objectives_lookup_client) -> None:
    c, strategy_factory = objectives_lookup_client
    from adp.strategy import store as sstore
    from adp.strategy.models import StrategicObjectiveCreate, StrategicThemeCreate

    async with strategy_factory() as session:
        theme = await sstore.create_theme(StrategicThemeCreate(name="Growth"), session)
        objective = await sstore.create_objective(
            StrategicObjectiveCreate(
                theme_id=theme.id, owner="Owner", statement="Statement",
                fiscal_year=2026, period="Q1",
            ),
            session,
        )
        await session.commit()
        await sstore.link_objective_design(objective.id, "DSN-001", session)
        await session.commit()

    resp = await c.get("/api/v1/designs/DSN-001/objectives")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == objective.id


async def test_get_design_objectives_200_empty_when_unlinked(objectives_lookup_client) -> None:
    c, _ = objectives_lookup_client
    resp = await c.get("/api/v1/designs/DSN-001/objectives")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}
