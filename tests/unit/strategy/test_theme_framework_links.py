"""Unit tests: 927-theme-framework-mapping (COMPLY-05, link #3) -- ThemeFrameworkMapping
(adp.strategy.store) against in-memory SQLite, mirroring test_control_links.py's exact fixture
convention.

Store metadata omits PK/FK constraints (those live only in the migration), so this file adds its
own unique-index DDL for theme_framework_links(theme_id, framework_id) and seeds the
_regulatory_frameworks mirror table directly, standing in for a real COMPLY-01 write (this package
never performs one).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.strategy import store as sstore
from adp.strategy.models import StrategicThemeCreate

_UNIQUE_DDL = [
    "CREATE UNIQUE INDEX uq_theme_name ON strategic_themes(name)",
    "CREATE UNIQUE INDEX uq_tfl ON theme_framework_links(theme_id, framework_id)",
]


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/theme_framework_links.db")
    async with engine.begin() as conn:
        await conn.run_sync(sstore._metadata.create_all)
        for ddl in _UNIQUE_DDL:
            await conn.execute(sa.text(ddl))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _mk_theme(session, name="Theme") -> str:
    created = await sstore.create_theme(StrategicThemeCreate(name=name), session)
    await session.commit()
    return created.id


async def _mk_framework(session, framework_id="FRM-1", name="GDPR") -> str:
    """Seeds the _regulatory_frameworks mirror table directly, standing in for a real
    COMPLY-01 write (adp.compliance.store.create_framework)."""
    await session.execute(
        sstore._regulatory_frameworks.insert().values(id=framework_id, name=name)
    )
    await session.commit()
    return framework_id


class TestFrameworkExists:
    async def test_true_when_seeded(self, session):
        framework_id = await _mk_framework(session)
        assert await sstore.framework_exists(framework_id, session) is True

    async def test_false_when_missing(self, session):
        assert await sstore.framework_exists("FRM-does-not-exist", session) is False


class TestListFrameworkIdsForTheme:
    async def test_empty_for_untagged_theme(self, session):
        theme_id = await _mk_theme(session)
        assert await sstore.list_framework_ids_for_theme(theme_id, session) == []


class TestLinkThemeFramework:
    """T005/T016 -- US1/US3: link_theme_framework()/unlink_theme_framework()."""

    async def test_link_then_duplicate_raises(self, session):
        theme_id = await _mk_theme(session)
        framework_id = await _mk_framework(session)

        await sstore.link_theme_framework(theme_id, framework_id, session)
        await session.commit()

        with pytest.raises(sstore.DuplicateLinkError):
            await sstore.link_theme_framework(theme_id, framework_id, session)

    async def test_link_appears_via_list_framework_ids(self, session):
        theme_id = await _mk_theme(session)
        framework_id = await _mk_framework(session)

        await sstore.link_theme_framework(theme_id, framework_id, session)
        await session.commit()

        assert await sstore.list_framework_ids_for_theme(theme_id, session) == [framework_id]

    async def test_unlink_raises_when_not_linked(self, session):
        theme_id = await _mk_theme(session)
        framework_id = await _mk_framework(session)
        with pytest.raises(sstore.LinkNotFoundError):
            await sstore.unlink_theme_framework(theme_id, framework_id, session)

    async def test_link_then_unlink_removes_it(self, session):
        theme_id = await _mk_theme(session)
        framework_id = await _mk_framework(session)

        await sstore.link_theme_framework(theme_id, framework_id, session)
        await session.commit()
        theme = await sstore.get_theme(theme_id, session)
        assert theme is not None
        assert theme.framework_ids == [framework_id]

        await sstore.unlink_theme_framework(theme_id, framework_id, session)
        await session.commit()
        theme = await sstore.get_theme(theme_id, session)
        assert theme is not None
        assert theme.framework_ids == []


class TestListThemesForFramework:
    """T010 -- US2: the reverse lookup, adp.compliance.router's own entry point."""

    async def test_returns_linked_theme(self, session):
        theme_id = await _mk_theme(session, "Regulatory & Compliance")
        framework_id = await _mk_framework(session)
        await sstore.link_theme_framework(theme_id, framework_id, session)
        await session.commit()

        response = await sstore.list_themes_for_framework(framework_id, session)
        assert response.total == 1
        assert response.items[0].id == theme_id

    async def test_empty_when_none_linked(self, session):
        framework_id = await _mk_framework(session)
        response = await sstore.list_themes_for_framework(framework_id, session)
        assert response.total == 0

    async def test_one_theme_tagged_against_two_frameworks(self, session):
        theme_id = await _mk_theme(session)
        framework_1 = await _mk_framework(session, "FRM-1", "GDPR")
        framework_2 = await _mk_framework(session, "FRM-2", "SOC 2")
        await sstore.link_theme_framework(theme_id, framework_1, session)
        await sstore.link_theme_framework(theme_id, framework_2, session)
        await session.commit()

        theme = await sstore.get_theme(theme_id, session)
        assert theme is not None
        assert set(theme.framework_ids) == {framework_1, framework_2}

        response_1 = await sstore.list_themes_for_framework(framework_1, session)
        response_2 = await sstore.list_themes_for_framework(framework_2, session)
        assert response_1.items[0].id == theme_id
        assert response_2.items[0].id == theme_id
