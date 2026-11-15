"""937-application-capabilities: the application capability catalog, its layer links, the level
rules and the derived missing-technical-capability warning (spec US1-US4).

SQLite fixture over adp.application.store's metadata (which defines the four new tables and the
narrow business_capabilities mirror, now with level/parent_id).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import app_capabilities as ac
from adp.application import store as astore
from adp.application.app_capability_models import (
    MISSING_TECHNICAL_CAPABILITY,
    RULE_APP_CAP_L3,
    RULE_BUSINESS_L3,
    RULE_TECH_L2_L3,
    AppCapDepthError,
    AppCapHasChildrenError,
    AppCapNotFoundError,
    ApplicationCapabilityCreate,
    ApplicationCapabilityUpdate,
    CapabilityLevelError,
    DuplicateAppCapLinkError,
    DuplicateSiblingNameError,
)
from adp.application.models import ApplicationCreate, TechnicalCapabilityCreate

NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


@pytest.fixture()
async def engine_session(tmp_path, monkeypatch):
    indexed: list[tuple[str, str, str]] = []

    async def _index(entity_type, entity_id, text, session):
        indexed.append((entity_type, entity_id, text))

    async def _unindex(entity_type, entity_id, session):
        indexed.append((entity_type, entity_id, "<removed>"))

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ac, "index_entity", _index)
    monkeypatch.setattr(ac, "unindex_entity", _unindex)
    monkeypatch.setattr(astore, "index_entity", _noop)
    monkeypatch.setattr(astore, "unindex_entity", _noop)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/appcap.db")
    async with engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.info["indexed"] = indexed
        yield engine, s
    await engine.dispose()


@pytest.fixture()
async def session(engine_session):
    return engine_session[1]


async def _cap(session, name: str, parent: str | None = None) -> str:
    return (
        await ac.create_app_capability(
            ApplicationCapabilityCreate(name=name, parent_id=parent), session
        )
    ).id


async def _branch(session) -> dict[str, str]:
    """Transaction Processing > Payments > Tender Authorization."""
    l1 = await _cap(session, "Transaction Processing")
    l2 = await _cap(session, "Payments", l1)
    l3 = await _cap(session, "Tender Authorization", l2)
    return {"l1": l1, "l2": l2, "l3": l3}


async def _biz(session, cid: str, name: str, level: int, parent: str | None = None) -> str:
    await session.execute(
        astore._biz_caps.insert().values(id=cid, name=name, level=level, parent_id=parent)
    )
    return cid


async def _biz_branch(session) -> dict[str, str]:
    return {
        "l1": await _biz(session, "b1", "Sales & Customer Transactions", 1),
        "l2": await _biz(session, "b2", "In-Store Transaction Management", 2, "b1"),
        "l3": await _biz(session, "b3", "Accept Payment", 3, "b2"),
    }


async def _tech(session, name: str, parent: str | None = None) -> str:
    return (
        await astore.create_technical_capability(
            TechnicalCapabilityCreate(name=name, parent_id=parent), session
        )
    ).id


async def _tech_branch(session) -> dict[str, str]:
    l1 = await _tech(session, "Integration & Data Services")
    l2 = await _tech(session, "Security", l1)
    l3 = await _tech(session, "Payment Tokenization (P2PE)", l2)
    return {"l1": l1, "l2": l2, "l3": l3}


async def _app(session, name: str = "Store POS") -> str:
    return (await astore.create_application(ApplicationCreate(name=name), session)).id


# ── US1: catalog ─────────────────────────────────────────────────────────────


async def test_level_is_derived_from_parent(session) -> None:
    b = await _branch(session)
    levels = {i.id: i.level for i in (await ac.list_app_capabilities(session)).items}
    assert (levels[b["l1"]], levels[b["l2"]], levels[b["l3"]]) == (1, 2, 3)


async def test_fourth_level_refused(session) -> None:
    b = await _branch(session)
    with pytest.raises(AppCapDepthError, match="maximum depth is 3"):
        await _cap(session, "Too deep", b["l3"])


async def test_unknown_parent(session) -> None:
    with pytest.raises(AppCapNotFoundError):
        await _cap(session, "Orphan", "nope")


async def test_sibling_names_unique_case_insensitive(session) -> None:
    b = await _branch(session)
    with pytest.raises(DuplicateSiblingNameError):
        await _cap(session, "transaction processing")  # L1 roots collide too
    with pytest.raises(DuplicateSiblingNameError):
        await _cap(session, "PAYMENTS", b["l1"])
    other = await _cap(session, "Customer Service")
    await _cap(session, "Payments", other)  # same name, different branch: fine


async def test_rename_checks_siblings_and_keeps_parent(session) -> None:
    b = await _branch(session)
    sibling = await _cap(session, "Checkout", b["l1"])
    with pytest.raises(DuplicateSiblingNameError):
        await ac.update_app_capability(
            sibling, ApplicationCapabilityUpdate(name="payments"), session
        )
    updated = await ac.update_app_capability(
        b["l2"], ApplicationCapabilityUpdate(name="Payment Handling", description="d"), session
    )
    assert updated is not None
    assert (updated.name, updated.description, updated.parent_id) == (
        "Payment Handling",
        "d",
        b["l1"],
    )
    assert (
        await ac.update_app_capability("nope", ApplicationCapabilityUpdate(name="x"), session)
        is None
    )


async def test_blank_name_refused() -> None:
    with pytest.raises(ValueError):
        ApplicationCapabilityCreate(name="  ")
    with pytest.raises(ValueError):
        ApplicationCapabilityUpdate(name="")
    with pytest.raises(ValueError):
        ApplicationCapabilityUpdate.model_validate({"parent_id": "x"})  # parent is immutable


async def test_delete_refused_with_children(session) -> None:
    b = await _branch(session)
    with pytest.raises(AppCapHasChildrenError):
        await ac.delete_app_capability(b["l2"], session)
    assert await ac.delete_app_capability(b["l3"], session) is True
    assert await ac.delete_app_capability(b["l3"], session) is False


async def test_search_hooks(session) -> None:
    b = await _branch(session)
    indexed = session.info["indexed"]
    l3_text = [t for (_, i, t) in indexed if i == b["l3"]][-1]
    assert "Tender Authorization" in l3_text and "Transaction Processing / Payments" in l3_text
    indexed.clear()
    await ac.update_app_capability(b["l1"], ApplicationCapabilityUpdate(name="Txn"), session)
    reindexed = {i for (_, i, _t) in indexed}
    assert reindexed == {b["l1"], b["l2"], b["l3"]}  # descendants' paths changed
    await ac.delete_app_capability(b["l3"], session)
    assert indexed[-1] == ("application_capability", b["l3"], "<removed>")
    entries = dict(await ac.search_entries(session))
    assert entries == {b["l1"]: "Txn", b["l2"]: "Payments Txn"}


# ── US2: links and level rules ───────────────────────────────────────────────


async def test_links_at_allowed_levels_show_in_detail(session) -> None:
    b, biz, tech = await _branch(session), await _biz_branch(session), await _tech_branch(session)
    gateway_l2 = await _tech(session, "API Services", tech["l1"])
    app = await _app(session)
    await ac.add_business_link(b["l3"], biz["l3"], session)
    await ac.add_tech_link(b["l3"], tech["l3"], session)
    await ac.add_tech_link(b["l3"], gateway_l2, session)  # L2 target allowed; two is normal
    await ac.add_realization(b["l3"], app, session)
    d = await ac.get_app_capability_detail(b["l3"], session)
    assert d is not None
    assert [p.name for p in d.path] == ["Transaction Processing", "Payments"]
    assert [c.name for c in d.business_capabilities] == ["Accept Payment"]
    assert [p.name for p in d.business_capabilities[0].path] == [
        "Sales & Customer Transactions",
        "In-Store Transaction Management",
    ]
    assert sorted(c.name for c in d.technical_capabilities) == [
        "API Services",
        "Payment Tokenization (P2PE)",
    ]
    assert [a.name for a in d.realized_by] == ["Store POS"]
    assert (d.business_capability_count, d.technical_capability_count, d.realization_count) == (
        1,
        2,
        1,
    )


@pytest.mark.parametrize("app_level", ["l1", "l2"])
async def test_app_capability_must_be_l3(session, app_level) -> None:
    b, biz, tech, app = (
        await _branch(session),
        await _biz_branch(session),
        await _tech_branch(session),
        await _app(session),
    )
    for call, target in (
        (ac.add_business_link, biz["l3"]),
        (ac.add_tech_link, tech["l3"]),
        (ac.add_realization, app),
    ):
        with pytest.raises(CapabilityLevelError) as exc:
            await call(b[app_level], target, session)
        assert str(exc.value) == RULE_APP_CAP_L3


@pytest.mark.parametrize("biz_level", ["l1", "l2"])
async def test_business_capability_must_be_l3(session, biz_level) -> None:
    b, biz = await _branch(session), await _biz_branch(session)
    with pytest.raises(CapabilityLevelError) as exc:
        await ac.add_business_link(b["l3"], biz[biz_level], session)
    assert str(exc.value) == RULE_BUSINESS_L3


async def test_technical_l1_refused(session) -> None:
    b, tech = await _branch(session), await _tech_branch(session)
    with pytest.raises(CapabilityLevelError) as exc:
        await ac.add_tech_link(b["l3"], tech["l1"], session)
    assert str(exc.value) == RULE_TECH_L2_L3


async def test_duplicates_and_missing_ends(session) -> None:
    b, biz, tech, app = (
        await _branch(session),
        await _biz_branch(session),
        await _tech_branch(session),
        await _app(session),
    )
    await ac.add_business_link(b["l3"], biz["l3"], session)
    await ac.add_tech_link(b["l3"], tech["l3"], session)
    await ac.add_realization(b["l3"], app, session)
    for call, target in (
        (ac.add_business_link, biz["l3"]),
        (ac.add_tech_link, tech["l3"]),
        (ac.add_realization, app),
    ):
        with pytest.raises(DuplicateAppCapLinkError):
            await call(b["l3"], target, session)
        with pytest.raises(AppCapNotFoundError):
            await call(b["l3"], "missing", session)
        with pytest.raises(AppCapNotFoundError):
            await call("missing", target, session)


async def test_many_to_many_and_unlink(session) -> None:
    b, biz = await _branch(session), await _biz_branch(session)
    other_l3 = await _cap(session, "Payment Reconciliation", b["l2"])
    second_biz = await _biz(session, "b4", "Process Returns", 3, "b2")
    for a in (b["l3"], other_l3):
        for c in (biz["l3"], second_biz):
            await ac.add_business_link(a, c, session)
    assert len(await ac.list_by_business_capability(biz["l3"], session)) == 2
    assert await ac.remove_business_link(b["l3"], biz["l3"], session) is True
    assert await ac.remove_business_link(b["l3"], biz["l3"], session) is False
    assert [s.name for s in await ac.list_by_business_capability(biz["l3"], session)] == [
        "Payment Reconciliation"
    ]


async def test_deleting_each_end_removes_only_its_links(session) -> None:
    b, biz, tech, app = (
        await _branch(session),
        await _biz_branch(session),
        await _tech_branch(session),
        await _app(session),
    )
    await ac.add_business_link(b["l3"], biz["l3"], session)
    await ac.add_tech_link(b["l3"], tech["l3"], session)
    await ac.add_realization(b["l3"], app, session)

    assert await astore.delete_technical_capability(tech["l3"], session) is True
    assert await astore.delete_application(app, session) is True
    d = await ac.get_app_capability_detail(b["l3"], session)
    assert d is not None
    assert (d.technical_capability_count, d.realization_count, d.business_capability_count) == (
        0,
        0,
        1,
    )
    # A business capability deleted elsewhere (Postgres cascades; SQLite leaves the row):
    # reads inner-join the far end, so nothing dangling is returned either way.
    await session.execute(astore._biz_caps.delete().where(astore._biz_caps.c.id == biz["l3"]))
    d = await ac.get_app_capability_detail(b["l3"], session)
    assert d is not None and d.business_capabilities == [] and d.business_capability_count == 0
    # Deleting the application capability removes its remaining link rows.
    assert await ac.delete_app_capability(b["l3"], session) is True
    left = (
        await session.execute(sa.select(sa.func.count()).select_from(astore._biz_app_cap_links))
    ).scalar_one()
    assert left == 0


async def test_old_links_untouched(session) -> None:
    b, tech, app = await _branch(session), await _tech_branch(session), await _app(session)
    await session.execute(
        astore._app_tech_cap_links.insert().values(
            app_id=app, tech_cap_id=tech["l3"], usage_type="provides"
        )
    )
    await ac.add_realization(b["l3"], app, session)
    await ac.add_tech_link(b["l3"], tech["l3"], session)
    await ac.remove_tech_link(b["l3"], tech["l3"], session)
    await ac.remove_realization(b["l3"], app, session)
    old = (
        await session.execute(sa.select(sa.func.count()).select_from(astore._app_tech_cap_links))
    ).scalar_one()
    assert old == 1


# ── US3: derived warning ─────────────────────────────────────────────────────


async def test_warning_lifecycle(session) -> None:
    b, tech = await _branch(session), await _tech_branch(session)
    by_id = {i.id: i for i in (await ac.list_app_capabilities(session)).items}
    assert by_id[b["l3"]].warnings == [MISSING_TECHNICAL_CAPABILITY]
    assert by_id[b["l1"]].warnings == [] and by_id[b["l2"]].warnings == []  # never on L1/L2
    gaps = await ac.list_app_capabilities(session, warning=MISSING_TECHNICAL_CAPABILITY)
    assert [i.id for i in gaps.items] == [b["l3"]] and gaps.total == 1

    await ac.add_tech_link(b["l3"], tech["l3"], session)
    got = await ac.get_app_capability(b["l3"], session)
    assert got is not None and got.warnings == []
    assert (
        await ac.list_app_capabilities(session, warning=MISSING_TECHNICAL_CAPABILITY)
    ).items == []

    await astore.delete_technical_capability(tech["l3"], session)
    got = await ac.get_app_capability(b["l3"], session)
    assert got is not None and got.warnings == [MISSING_TECHNICAL_CAPABILITY]


def test_warnings_for_is_pure() -> None:
    assert ac.warnings_for(3, 0) == [MISSING_TECHNICAL_CAPABILITY]
    assert ac.warnings_for(3, 1) == []
    assert ac.warnings_for(1, 0) == [] and ac.warnings_for(2, 0) == []


def test_warning_is_never_stored() -> None:
    """ART-II / FR-017: no column can hold the derived warning."""
    tables = [
        astore._app_caps,
        astore._biz_app_cap_links,
        astore._app_cap_tech_links,
        astore._app_cap_realizations,
    ]
    for t in tables:
        for c in t.columns:
            assert "warning" not in c.name and not c.name.startswith("missing")


async def test_list_query_count_is_fixed(engine_session) -> None:
    engine, session = engine_session
    b, tech = await _branch(session), await _tech_branch(session)
    await ac.add_tech_link(b["l3"], tech["l3"], session)
    selects: list[str] = []

    def count(conn, cursor, statement, *args):  # type: ignore[no-untyped-def]
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    sa.event.listen(engine.sync_engine, "before_cursor_execute", count)
    await ac.list_app_capabilities(session)
    first = len(selects)
    for i in range(10):
        await _cap(session, f"Extra {i}", b["l2"])
    selects.clear()
    await ac.list_app_capabilities(session)
    assert len(selects) == first == 4


# ── US4: reverse lookups ─────────────────────────────────────────────────────


async def test_reverse_lookups(session) -> None:
    b, biz, tech, app = (
        await _branch(session),
        await _biz_branch(session),
        await _tech_branch(session),
        await _app(session),
    )
    returns_l3 = await _cap(session, "Return Authorization", b["l2"])
    await ac.add_business_link(b["l3"], biz["l3"], session)
    await ac.add_realization(b["l3"], app, session)
    await ac.add_realization(returns_l3, app, session)
    await ac.add_tech_link(b["l3"], tech["l3"], session)

    by_biz = await ac.list_by_business_capability(biz["l3"], session)
    assert [(s.name, [a.name for a in s.realized_by]) for s in by_biz] == [
        ("Tender Authorization", ["Store POS"])
    ]
    assert [p.name for p in by_biz[0].path] == ["Transaction Processing", "Payments"]
    assert [s.name for s in await ac.list_by_technical_capability(tech["l3"], session)] == [
        "Tender Authorization"
    ]
    by_app = await ac.list_by_application(app, session)
    assert [s.name for s in by_app] == ["Return Authorization", "Tender Authorization"]
    assert by_app[0].warnings == [MISSING_TECHNICAL_CAPABILITY]
    assert await ac.list_by_application("unknown", session) == []
