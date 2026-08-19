"""Contract tests for Regulatory Framework Legal Dates & Identity (COMPLY-01a,
specs/926-framework-versioning-correction/).

Mirrors tests/contract/test_compliance_registry_api.py's fixture shape exactly, extended with the
`regulation_number` UNIQUE index migration 035 adds at the DB level (store metadata omits it, same
convention as `controls`' own `UNIQUE(framework_id, code)` in that file).
"""

from __future__ import annotations

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import router as crouter
from adp.compliance import store as cstore
from adp.compliance.models import (
    FrameworkAmendment,
    FrameworkAmendmentListResponse,
    FrameworkApplicationPhase,
    FrameworkApplicationPhaseListResponse,
    RegulatoryFramework,
    RegulatoryFrameworkDetail,
)

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_controls_framework_code ON controls(framework_id, code)",
    "CREATE UNIQUE INDEX uq_regulatory_frameworks_regulation_number "
    "ON regulatory_frameworks(regulation_number)",
]


@pytest.fixture()
async def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/framework_legal_dates.db")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from adp.api.app import create_app

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[crouter._get_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


BASE = "/api/v1/compliance"


async def _mk_framework(client, name="GDPR", **extra) -> dict:
    payload = {
        "name": name, "jurisdiction": "EU", "authority": "European Commission",
        "version": "2016/679", **extra,
    }
    resp = await client.post(f"{BASE}/frameworks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── User Story 1: legal identity + dates on the framework's own fields ──────────────────────────

async def test_patch_new_fields_leaves_existing_fields_unchanged(client):
    fw = await _mk_framework(client)
    resp = await client.patch(
        f"{BASE}/frameworks/{fw['id']}",
        json={
            "regulation_number": "2016/679", "celex_number": "32016R0679",
            "adoption_date": "2016-04-27", "consolidated_as_of": "2016-05-04",
        },
    )
    assert resp.status_code == 200, resp.text
    updated = RegulatoryFramework.model_validate(resp.json())
    assert updated.regulation_number == "2016/679"
    assert updated.celex_number == "32016R0679"
    # Existing fields, never touched by this PATCH, remain exactly as created.
    assert updated.name == fw["name"]
    assert updated.jurisdiction == fw["jurisdiction"]
    assert updated.version == fw["version"]


async def test_duplicate_regulation_number_returns_409(client):
    fw1 = await _mk_framework(client, name="GDPR")
    await client.patch(f"{BASE}/frameworks/{fw1['id']}", json={"regulation_number": "2016/679"})
    fw2 = await _mk_framework(client, name="GDPR Duplicate")
    resp = await client.patch(
        f"{BASE}/frameworks/{fw2['id']}", json={"regulation_number": "2016/679"}
    )
    assert resp.status_code == 409, resp.text


async def test_invalid_status_returns_422(client):
    resp = await client.post(
        f"{BASE}/frameworks",
        json={
            "name": "Test", "jurisdiction": "EU", "authority": "Test", "version": "1.0",
            "status": "bogus",
        },
    )
    assert resp.status_code == 422, resp.text


async def test_framework_detail_includes_new_fields_and_empty_child_lists(client):
    fw = await _mk_framework(client)
    resp = await client.get(f"{BASE}/frameworks/{fw['id']}")
    assert resp.status_code == 200, resp.text
    detail = RegulatoryFrameworkDetail.model_validate(resp.json())
    assert detail.regulation_number is None
    assert detail.status == "in_force"
    assert detail.application_phases == []
    assert detail.amendments == []
    assert detail.controls == []


# ── User Story 2: application phases ─────────────────────────────────────────────────────────

async def test_create_list_application_phase(client):
    fw = await _mk_framework(client)
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/application-phases",
        json={"phase_label": "Prohibited practices", "applies_from_date": "2025-02-02"},
    )
    assert resp.status_code == 201, resp.text
    phase = FrameworkApplicationPhase.model_validate(resp.json())
    assert phase.phase_label == "Prohibited practices"

    listing = await client.get(f"{BASE}/frameworks/{fw['id']}/application-phases")
    assert listing.status_code == 200, listing.text
    parsed = FrameworkApplicationPhaseListResponse.model_validate(listing.json())
    assert parsed.total == 1


async def test_delete_application_phase_then_repeat_404(client):
    fw = await _mk_framework(client)
    create = await client.post(
        f"{BASE}/frameworks/{fw['id']}/application-phases",
        json={"phase_label": "Phase 1", "applies_from_date": "2025-01-01"},
    )
    phase_id = create.json()["id"]

    delete = await client.delete(f"{BASE}/frameworks/{fw['id']}/application-phases/{phase_id}")
    assert delete.status_code == 204, delete.text

    repeat = await client.delete(f"{BASE}/frameworks/{fw['id']}/application-phases/{phase_id}")
    assert repeat.status_code == 404, repeat.text


async def test_application_phase_routes_404_for_unknown_framework(client):
    resp = await client.post(
        f"{BASE}/frameworks/does-not-exist/application-phases",
        json={"phase_label": "Phase 1", "applies_from_date": "2025-01-01"},
    )
    assert resp.status_code == 404, resp.text
    resp = await client.get(f"{BASE}/frameworks/does-not-exist/application-phases")
    assert resp.status_code == 404, resp.text


# ── User Story 3: amendments ─────────────────────────────────────────────────────────────────

async def test_create_list_amendment(client):
    fw = await _mk_framework(client)
    resp = await client.post(
        f"{BASE}/frameworks/{fw['id']}/amendments",
        json={"amending_title": "RTS on ICT risk management", "amending_celex": "32024R1620"},
    )
    assert resp.status_code == 201, resp.text
    amendment = FrameworkAmendment.model_validate(resp.json())
    assert amendment.amending_title == "RTS on ICT risk management"

    listing = await client.get(f"{BASE}/frameworks/{fw['id']}/amendments")
    assert listing.status_code == 200, listing.text
    parsed = FrameworkAmendmentListResponse.model_validate(listing.json())
    assert parsed.total == 1


async def test_no_limit_on_amendment_count(client):
    fw = await _mk_framework(client)
    for i in range(5):
        resp = await client.post(
            f"{BASE}/frameworks/{fw['id']}/amendments", json={"amending_title": f"RTS {i}"}
        )
        assert resp.status_code == 201, resp.text
    listing = await client.get(f"{BASE}/frameworks/{fw['id']}/amendments")
    assert listing.json()["total"] == 5


async def test_delete_amendment_then_repeat_404(client):
    fw = await _mk_framework(client)
    create = await client.post(
        f"{BASE}/frameworks/{fw['id']}/amendments", json={"amending_title": "RTS 1"}
    )
    amendment_id = create.json()["id"]

    delete = await client.delete(f"{BASE}/frameworks/{fw['id']}/amendments/{amendment_id}")
    assert delete.status_code == 204, delete.text

    repeat = await client.delete(f"{BASE}/frameworks/{fw['id']}/amendments/{amendment_id}")
    assert repeat.status_code == 404, repeat.text


async def test_amendment_routes_404_for_unknown_framework(client):
    resp = await client.post(
        f"{BASE}/frameworks/does-not-exist/amendments", json={"amending_title": "RTS 1"}
    )
    assert resp.status_code == 404, resp.text
    resp = await client.get(f"{BASE}/frameworks/does-not-exist/amendments")
    assert resp.status_code == 404, resp.text
