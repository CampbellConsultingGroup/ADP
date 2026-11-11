"""Unit tests for adp.business.value_chains (ADP-nag): value chain / activity / capability
persistence against a SQLite-backed fixture.

Covers the invariants the store owns: activity positions stay 0..n-1 within each category through
add / move / delete / reorder; deletes remove child rows themselves (SQLite doesn't enforce the
migration's ON DELETE CASCADE); and the search index is written and cleared at every call site
(index_entity / unindex_entity are patched to recording stubs, as in test_search_indexing.py --
the real index SQL is Postgres-only and covered by the integration suite).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore
from adp.business import value_chains as vcstore
from adp.business.models import (
    BusinessCapabilityCreate,
    DuplicateStageCapError,
    StageCapabilityLinkCreate,
    StageCapNotFoundError,
    ValueChainActivityCreate,
    ValueChainActivityUpdate,
    ValueChainCreate,
    ValueChainUpdate,
)
from adp.search import ENTITY_VALUE_CHAIN, ENTITY_VALUE_CHAIN_ACTIVITY


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/vc.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture()
def index_calls(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    async def fake_index(entity_type, entity_id, text, session):
        calls.append(("index", entity_type, entity_id))

    async def fake_unindex(entity_type, entity_id, session):
        calls.append(("unindex", entity_type, entity_id))

    monkeypatch.setattr(vcstore, "index_entity", fake_index)
    monkeypatch.setattr(vcstore, "unindex_entity", fake_unindex)
    return calls


async def _chain(session, name="Retail"):
    return await vcstore.create_value_chain(ValueChainCreate(name=name), session)


async def _activity(session, chain_id, name, category="primary", position=None):
    return await vcstore.add_activity(
        chain_id, ValueChainActivityCreate(name=name, category=category, position=position), session
    )


async def _lane(session, chain_id, category):
    detail = await vcstore.get_value_chain(chain_id, session)
    lane = detail.primary_activities if category == "primary" else detail.support_activities
    return [(a.name, a.position) for a in lane]


# ── Value chains ──────────────────────────────────────────────────────────────


async def test_create_and_get_value_chain(session):
    chain = await vcstore.create_value_chain(
        ValueChainCreate(name="  Retail  ", description="Stores and online", margin_label="Profit"),
        session,
    )
    assert chain.name == "Retail"
    assert chain.margin_label == "Profit"

    detail = await vcstore.get_value_chain(chain.id, session)
    assert detail.description == "Stores and online"
    assert detail.primary_activities == []
    assert detail.support_activities == []


async def test_margin_label_defaults_to_margin(session):
    chain = await _chain(session)
    assert chain.margin_label == "Margin"


async def test_list_orders_by_creation_position(session):
    for name in ["A", "B", "C"]:
        await _chain(session, name)
    assert [c.name for c in await vcstore.list_value_chains(session)] == ["A", "B", "C"]


async def test_get_unknown_chain_is_none(session):
    assert await vcstore.get_value_chain("nope", session) is None


async def test_update_clears_description_but_not_margin_label(session):
    chain = await vcstore.create_value_chain(
        ValueChainCreate(name="Retail", description="old"), session
    )
    updated = await vcstore.update_value_chain(
        chain.id, ValueChainUpdate(description=None, margin_label=None), session
    )
    assert updated.description is None
    assert updated.margin_label == "Margin"


async def test_update_unknown_chain_is_none(session):
    assert await vcstore.update_value_chain("nope", ValueChainUpdate(name="x"), session) is None


# ── Activities and their positions ────────────────────────────────────────────


async def test_activities_split_by_category_and_append_in_order(session):
    chain = await _chain(session)
    for name in ["Inbound", "Operations", "Outbound"]:
        await _activity(session, chain.id, name)
    await _activity(session, chain.id, "Procurement", "support")

    assert await _lane(session, chain.id, "primary") == [
        ("Inbound", 0), ("Operations", 1), ("Outbound", 2),
    ]
    assert await _lane(session, chain.id, "support") == [("Procurement", 0)]


async def test_add_at_position_shifts_the_rest(session):
    chain = await _chain(session)
    await _activity(session, chain.id, "Inbound")
    await _activity(session, chain.id, "Outbound")
    await _activity(session, chain.id, "Operations", position=1)
    assert await _lane(session, chain.id, "primary") == [
        ("Inbound", 0), ("Operations", 1), ("Outbound", 2),
    ]


async def test_add_position_past_the_end_appends(session):
    chain = await _chain(session)
    await _activity(session, chain.id, "Inbound")
    await _activity(session, chain.id, "Service", position=99)
    assert await _lane(session, chain.id, "primary") == [("Inbound", 0), ("Service", 1)]


async def test_add_to_unknown_chain_raises(session):
    with pytest.raises(LookupError):
        await _activity(session, "nope", "Inbound")


async def test_move_between_categories_compacts_both_lanes(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Inbound")
    await _activity(session, chain.id, "HR", "support")
    await _activity(session, chain.id, "Operations")

    moved = await vcstore.update_activity(
        chain.id, a.id, ValueChainActivityUpdate(category="support"), session
    )
    assert moved.category == "support"
    assert await _lane(session, chain.id, "primary") == [("Operations", 0)]
    assert await _lane(session, chain.id, "support") == [("HR", 0), ("Inbound", 1)]


async def test_move_within_a_category(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "A")
    await _activity(session, chain.id, "B")
    await _activity(session, chain.id, "C")
    await vcstore.update_activity(chain.id, a.id, ValueChainActivityUpdate(position=2), session)
    assert await _lane(session, chain.id, "primary") == [("B", 0), ("C", 1), ("A", 2)]


async def test_update_rename_keeps_position(session):
    chain = await _chain(session)
    await _activity(session, chain.id, "A")
    b = await _activity(session, chain.id, "B")
    renamed = await vcstore.update_activity(
        chain.id, b.id, ValueChainActivityUpdate(name="Bee"), session
    )
    assert (renamed.name, renamed.position) == ("Bee", 1)


async def test_update_activity_of_another_chain_is_none(session):
    one = await _chain(session, "One")
    two = await _chain(session, "Two")
    a = await _activity(session, one.id, "A")
    assert (
        await vcstore.update_activity(two.id, a.id, ValueChainActivityUpdate(name="x"), session)
        is None
    )


async def test_delete_activity_compacts_its_lane(session):
    chain = await _chain(session)
    await _activity(session, chain.id, "A")
    b = await _activity(session, chain.id, "B")
    await _activity(session, chain.id, "C")
    assert await vcstore.delete_activity(chain.id, b.id, session) is True
    assert await _lane(session, chain.id, "primary") == [("A", 0), ("C", 1)]
    assert await vcstore.delete_activity(chain.id, b.id, session) is False


async def test_reorder_a_category(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "A")
    b = await _activity(session, chain.id, "B")
    c = await _activity(session, chain.id, "C")
    lane = await vcstore.reorder_activities(chain.id, "primary", [c.id, a.id, b.id], session)
    assert [(x.name, x.position) for x in lane] == [("C", 0), ("A", 1), ("B", 2)]


@pytest.mark.parametrize("which", ["missing", "extra", "duplicate"])
async def test_reorder_rejects_a_mismatched_id_list(session, which):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "A")
    b = await _activity(session, chain.id, "B")
    support = await _activity(session, chain.id, "HR", "support")
    ids = {
        "missing": [a.id],
        "extra": [a.id, b.id, support.id],
        "duplicate": [a.id, b.id, b.id],
    }[which]
    with pytest.raises(ValueError):
        await vcstore.reorder_activities(chain.id, "primary", ids, session)


async def test_reorder_unknown_chain_raises(session):
    with pytest.raises(LookupError):
        await vcstore.reorder_activities("nope", "primary", [], session)


# ── Activity capabilities ─────────────────────────────────────────────────────


async def _cap(session, name):
    return await bstore.create_capability(BusinessCapabilityCreate(name=name, level=1), session)


async def test_link_list_and_unlink_capabilities(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Operations")
    inv = await _cap(session, "Inventory Management")
    wh = await _cap(session, "Warehouse Management")

    await vcstore.link_cap_to_activity(
        chain.id, a.id, StageCapabilityLinkCreate(capability_id=wh.id), session
    )
    linked = await vcstore.link_cap_to_activity(
        chain.id, a.id, StageCapabilityLinkCreate(capability_id=inv.id), session
    )
    assert [c.name for c in linked.items] == ["Inventory Management", "Warehouse Management"]

    detail = await vcstore.get_value_chain(chain.id, session)
    assert [c.capability_id for c in detail.primary_activities[0].capabilities] == [inv.id, wh.id]

    await vcstore.unlink_cap_from_activity(chain.id, a.id, inv.id, session)
    assert [c.name for c in (await vcstore.list_activity_caps(chain.id, a.id, session)).items] == [
        "Warehouse Management"
    ]


async def test_link_twice_is_a_duplicate(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Operations")
    cap = await _cap(session, "Inventory Management")
    body = StageCapabilityLinkCreate(capability_id=cap.id)
    await vcstore.link_cap_to_activity(chain.id, a.id, body, session)
    with pytest.raises(DuplicateStageCapError):
        await vcstore.link_cap_to_activity(chain.id, a.id, body, session)


async def test_link_unknown_capability_or_activity_raises(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Operations")
    with pytest.raises(LookupError):
        await vcstore.link_cap_to_activity(
            chain.id, a.id, StageCapabilityLinkCreate(capability_id="nope"), session
        )
    cap = await _cap(session, "Inventory Management")
    with pytest.raises(LookupError):
        await vcstore.link_cap_to_activity(
            chain.id, "nope", StageCapabilityLinkCreate(capability_id=cap.id), session
        )


async def test_unlink_missing_link_raises(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Operations")
    with pytest.raises(StageCapNotFoundError):
        await vcstore.unlink_cap_from_activity(chain.id, a.id, "nope", session)


async def test_list_caps_of_unknown_activity_is_none(session):
    chain = await _chain(session)
    assert await vcstore.list_activity_caps(chain.id, "nope", session) is None


# ── Deleting a chain ──────────────────────────────────────────────────────────


async def test_delete_chain_removes_its_activities_and_links(session):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Operations")
    await _activity(session, chain.id, "HR", "support")
    cap = await _cap(session, "Inventory Management")
    await vcstore.link_cap_to_activity(
        chain.id, a.id, StageCapabilityLinkCreate(capability_id=cap.id), session
    )

    assert await vcstore.delete_value_chain(chain.id, session) is True
    assert await vcstore.get_value_chain(chain.id, session) is None
    for table in (bstore._value_chain_activities, bstore._value_chain_activity_caps):
        count = await session.execute(sa.select(sa.func.count()).select_from(table))
        assert count.scalar_one() == 0
    # The capability itself is untouched.
    assert await bstore.get_capability(cap.id, session) is not None
    assert await vcstore.delete_value_chain(chain.id, session) is False


# ── Search index wiring ───────────────────────────────────────────────────────


async def test_search_index_is_written_and_cleared(session, index_calls):
    chain = await _chain(session)
    a = await _activity(session, chain.id, "Operations")
    b = await _activity(session, chain.id, "HR", "support")
    await vcstore.update_value_chain(chain.id, ValueChainUpdate(name="Retail 2"), session)
    await vcstore.update_activity(chain.id, a.id, ValueChainActivityUpdate(name="Ops"), session)
    await vcstore.delete_activity(chain.id, b.id, session)
    await vcstore.delete_value_chain(chain.id, session)

    assert index_calls == [
        ("index", ENTITY_VALUE_CHAIN, chain.id),
        ("index", ENTITY_VALUE_CHAIN_ACTIVITY, a.id),
        ("index", ENTITY_VALUE_CHAIN_ACTIVITY, b.id),
        ("index", ENTITY_VALUE_CHAIN, chain.id),
        ("index", ENTITY_VALUE_CHAIN_ACTIVITY, a.id),
        ("unindex", ENTITY_VALUE_CHAIN_ACTIVITY, b.id),
        ("unindex", ENTITY_VALUE_CHAIN, chain.id),
        ("unindex", ENTITY_VALUE_CHAIN_ACTIVITY, a.id),
    ]
