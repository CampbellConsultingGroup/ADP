"""Unit tests: 932-regulatory-framework-tags (ADP-bkg) -- ApplicationFrameworkTag reconciliation
(adp.application.store) against in-memory SQLite, mirroring test_capability_groups_store.py's own
fixture convention and tests/unit/strategy/test_theme_framework_links.py's mirror-seeding idiom.

Store metadata omits PK/FK constraints (those live only in migration 041), so uniqueness here is
whatever upsert_application_risk's own Python-side diff/dedup logic provides -- exactly what these
tests exist to verify.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.application.models import (
    ApplicationRiskUpdate,
    FrameworkNotSelectableError,
    UnknownFrameworkError,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/application_framework_tags.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _now():
    return datetime.now(timezone.utc)


async def _seed_app(session, app_id: str = "APP-1", name: str = "CRM") -> str:
    await session.execute(
        astore._applications.insert().values(
            id=app_id, name=name, tech_debt_flags=[], created_at=_now(), updated_at=_now()
        )
    )
    return app_id


async def _seed_framework(session, framework_id: str, name: str, status: str) -> None:
    await session.execute(
        astore._regulatory_frameworks.insert().values(id=framework_id, name=name, status=status)
    )


async def _set_framework_status(session, framework_id: str, status: str) -> None:
    await session.execute(
        astore._regulatory_frameworks.update()
        .where(astore._regulatory_frameworks.c.id == framework_id)
        .values(status=status)
    )


# ── T004: _framework_record / _linked_framework_ids ───────────────────────────


async def test_framework_record_returns_none_for_unknown_id(session):
    assert await astore._framework_record("NOPE", session) is None


async def test_framework_record_returns_seeded_fields(session):
    await _seed_framework(session, "FRM-1", "GDPR", "in_force")
    record = await astore._framework_record("FRM-1", session)
    assert record == {"id": "FRM-1", "name": "GDPR", "status": "in_force"}


async def test_linked_framework_ids_empty_for_untagged_application(session):
    app_id = await _seed_app(session)
    await session.commit()
    assert await astore._linked_framework_ids(app_id, session) == []


# ── T006: reconciliation / diff / validate logic ──────────────────────────────


async def test_tagging_persists_and_survives_reload(session):
    app_id = await _seed_app(session)
    await _seed_framework(session, "FRM-1", "GDPR", "in_force")
    await _seed_framework(session, "FRM-2", "DORA", "amended")
    await session.commit()

    risk = await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-1", "FRM-2"]), session
    )
    await session.commit()
    assert set(risk.regulatory_tags) == {"FRM-1", "FRM-2"}

    reloaded = await astore.get_application_risk(app_id, session)
    assert set(reloaded.regulatory_tags) == {"FRM-1", "FRM-2"}


async def test_full_replace_removes_unselected_and_adds_new(session):
    app_id = await _seed_app(session)
    await _seed_framework(session, "FRM-1", "GDPR", "in_force")
    await _seed_framework(session, "FRM-2", "DORA", "amended")
    await session.commit()
    await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-1", "FRM-2"]), session
    )
    await session.commit()

    risk = await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-2"]), session
    )
    await session.commit()
    assert risk.regulatory_tags == ["FRM-2"]


async def test_duplicate_id_in_submitted_list_is_deduplicated(session):
    app_id = await _seed_app(session)
    await _seed_framework(session, "FRM-1", "GDPR", "in_force")
    await session.commit()

    risk = await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-1", "FRM-1"]), session
    )
    await session.commit()
    assert risk.regulatory_tags == ["FRM-1"]


async def test_zero_tags_round_trips_cleanly(session):
    app_id = await _seed_app(session)
    await session.commit()
    risk = await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=[]), session
    )
    await session.commit()
    assert risk.regulatory_tags == []


async def test_unknown_framework_id_is_rejected(session):
    app_id = await _seed_app(session)
    await session.commit()
    with pytest.raises(UnknownFrameworkError):
        await astore.upsert_application_risk(
            app_id, ApplicationRiskUpdate(regulatory_tags=["NOPE"]), session
        )


async def test_newly_added_repealed_framework_is_rejected_whole_write(session):
    app_id = await _seed_app(session)
    await _seed_framework(session, "FRM-1", "GDPR", "in_force")
    await _seed_framework(session, "FRM-3", "Repealed Reg", "repealed")
    await session.commit()

    with pytest.raises(FrameworkNotSelectableError):
        await astore.upsert_application_risk(
            app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-1", "FRM-3"]), session
        )

    # No partial write: neither id was linked.
    assert await astore._linked_framework_ids(app_id, session) == []


async def test_not_yet_applicable_framework_is_rejected(session):
    app_id = await _seed_app(session)
    await _seed_framework(session, "FRM-4", "Future Reg", "not_yet_applicable")
    await session.commit()
    with pytest.raises(FrameworkNotSelectableError):
        await astore.upsert_application_risk(
            app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-4"]), session
        )


async def test_already_linked_framework_survives_its_own_later_status_change(session):
    """Edge Case (spec.md): an already-tagged framework that later becomes repealed is not
    retroactively removed -- FR-001's status filter only governs what is newly *selectable*."""
    app_id = await _seed_app(session)
    await _seed_framework(session, "FRM-1", "GDPR", "in_force")
    await session.commit()

    await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-1"]), session
    )
    await session.commit()

    await _set_framework_status(session, "FRM-1", "repealed")
    await session.commit()

    # Re-submitting the same (now-repealed) id, unchanged, must NOT raise and must NOT remove it --
    # it was already linked, so it is never in the "to_add" set this diff computes.
    risk = await astore.upsert_application_risk(
        app_id, ApplicationRiskUpdate(regulatory_tags=["FRM-1"]), session
    )
    await session.commit()
    assert risk.regulatory_tags == ["FRM-1"]
