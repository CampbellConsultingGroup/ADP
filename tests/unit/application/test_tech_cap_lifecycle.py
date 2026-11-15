"""938-capability-model-analysis (ADP-6et.2) US2 / FR-001: technical capability lifecycle.

A lifecycle status (closed set, default "current") and an optional end-of-life date, stored on
technical_capabilities (migration 047).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.application.models import TechnicalCapabilityCreate, TechnicalCapabilityUpdate

STATUSES = ["emerging", "current", "contained", "retiring", "retired"]


@pytest.fixture()
async def session(tmp_path, monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(astore, "index_entity", _noop)
    monkeypatch.setattr(astore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/lifecycle.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_create_defaults_to_current_with_no_date(session):
    tc = await astore.create_technical_capability(
        TechnicalCapabilityCreate(name="API Services"), session
    )
    assert tc.lifecycle_status == "current"
    assert tc.end_of_life_date is None


@pytest.mark.parametrize("status", STATUSES)
async def test_create_and_update_accept_every_status(session, status):
    tc = await astore.create_technical_capability(
        TechnicalCapabilityCreate(name=f"Cap {status}", lifecycle_status=status), session
    )
    assert tc.lifecycle_status == status
    other = next(s for s in STATUSES if s != status)
    updated = await astore.update_technical_capability(
        tc.id, TechnicalCapabilityUpdate(lifecycle_status=other), session
    )
    assert updated is not None and updated.lifecycle_status == other


async def test_end_of_life_date_set_cleared_and_left_alone(session):
    tc = await astore.create_technical_capability(
        TechnicalCapabilityCreate(name="Offline Sync", end_of_life_date=date(2027, 6, 30)), session
    )
    assert tc.end_of_life_date == date(2027, 6, 30)
    # Omitted: unchanged.
    tc2 = await astore.update_technical_capability(
        tc.id, TechnicalCapabilityUpdate(lifecycle_status="retiring"), session
    )
    assert tc2 is not None and tc2.end_of_life_date == date(2027, 6, 30)
    # Explicit null: cleared.
    tc3 = await astore.update_technical_capability(
        tc.id, TechnicalCapabilityUpdate(end_of_life_date=None), session
    )
    assert tc3 is not None and tc3.end_of_life_date is None
    assert tc3.lifecycle_status == "retiring"


def test_update_rejects_explicit_null_status():
    with pytest.raises(ValidationError):
        TechnicalCapabilityUpdate(lifecycle_status=None)


@pytest.mark.parametrize("model", [TechnicalCapabilityCreate, TechnicalCapabilityUpdate])
def test_invalid_status_rejected(model):
    with pytest.raises(ValidationError):
        model(name="x", lifecycle_status="bogus")


async def test_raw_insert_without_the_column_gets_current(session):
    tc_id = str(uuid.uuid4())
    await session.execute(
        astore._tech_caps.insert().values(
            id=tc_id, name="Raw", level=1, created_at=datetime(2026, 11, 15, tzinfo=timezone.utc)
        )
    )
    tc = await astore.get_technical_capability(tc_id, session)
    assert tc is not None and tc.lifecycle_status == "current" and tc.end_of_life_date is None
