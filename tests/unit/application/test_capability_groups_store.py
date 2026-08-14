"""Unit tests: adp.application.store.list_all_capability_links (ADP-8xo).

Mirrors adp.strategy.store's own unit-store-test convention
(tests/unit/strategy/test_strategy_store.py): build the store's own
`_metadata` on a throwaway SQLite engine, exercise the async function
directly (no HTTP layer -- that's tests/contract/test_portfolio_api.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/capability_groups.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _now():
    return datetime.now(timezone.utc)


async def _seed_app(session, app_id: str, name: str) -> None:
    await session.execute(
        astore._applications.insert().values(
            id=app_id,
            name=name,
            tech_debt_flags=[],
            created_at=_now(),
            updated_at=_now(),
        )
    )


async def _seed_capability(session, cap_id: str, name: str) -> None:
    await session.execute(astore._biz_caps.insert().values(id=cap_id, name=name))


async def _seed_link(session, app_id: str, capability_id: str, fit_score: int) -> None:
    await session.execute(
        astore._app_cap_links.insert().values(
            app_id=app_id, capability_id=capability_id, fit_score=fit_score
        )
    )


async def test_list_all_capability_links_returns_links_across_multiple_apps(session):
    """No app_id filter -- links from every app in the registry come back in one call."""
    await _seed_app(session, "app-1", "Claims Core")
    await _seed_app(session, "app-2", "Policy Admin")
    await _seed_capability(session, "cap-1", "Claims Processing")
    await _seed_capability(session, "cap-2", "Underwriting")
    await _seed_link(session, "app-1", "cap-1", 4)
    await _seed_link(session, "app-2", "cap-2", 3)
    await session.commit()

    links = await astore.list_all_capability_links(session)

    assert len(links) == 2
    by_app = {link.app_id: link for link in links}
    assert by_app["app-1"].capability_id == "cap-1"
    assert by_app["app-1"].capability_name == "Claims Processing"
    assert by_app["app-1"].fit_score == 4
    assert by_app["app-2"].capability_id == "cap-2"


async def test_list_all_capability_links_one_app_multiple_capabilities(session):
    """An app linked to 2 capabilities produces 2 rows -- the multi-membership contract
    the Application Portfolio pivot's capability grouping dimension relies on."""
    await _seed_app(session, "app-1", "Claims Core")
    await _seed_capability(session, "cap-1", "Claims Processing")
    await _seed_capability(session, "cap-2", "Fraud Detection")
    await _seed_link(session, "app-1", "cap-1", 5)
    await _seed_link(session, "app-1", "cap-2", 2)
    await session.commit()

    links = await astore.list_all_capability_links(session)

    assert len(links) == 2
    assert {link.capability_id for link in links} == {"cap-1", "cap-2"}
    assert all(link.app_id == "app-1" for link in links)


async def test_list_all_capability_links_ordered_by_capability_then_app_name(session):
    """Stable default order: capability name, then app name (research.md-style
    documented ordering, not incidental)."""
    await _seed_app(session, "app-2", "Zeta App")
    await _seed_app(session, "app-1", "Alpha App")
    await _seed_capability(session, "cap-2", "Zeta Capability")
    await _seed_capability(session, "cap-1", "Alpha Capability")
    await _seed_link(session, "app-2", "cap-1", 3)
    await _seed_link(session, "app-1", "cap-1", 3)
    await _seed_link(session, "app-1", "cap-2", 3)
    await session.commit()

    links = await astore.list_all_capability_links(session)

    ordered = [(link.capability_name, link.app_id) for link in links]
    assert ordered == [
        ("Alpha Capability", "app-1"),
        ("Alpha Capability", "app-2"),
        ("Zeta Capability", "app-1"),
    ]


async def test_list_all_capability_links_empty_when_no_links(session):
    await _seed_app(session, "app-1", "Unlinked App")
    await session.commit()

    links = await astore.list_all_capability_links(session)

    assert links == []
