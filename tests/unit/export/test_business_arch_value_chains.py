"""Unit tests: value chains in the business architecture export (ADP-nag).

Same reconciliation cycle as test_business_arch_reconciliation.py: a chain is written to
value-chains/<id>/value-chain.json and each activity to value-chains/<id>/activities/<id>.json,
with its linked capability ids; deleted activities and chains have their files removed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.business import store as bstore
from adp.business.models import ValueChain, ValueChainActivity
from adp.export import business_arch

_NOW = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed(factory) -> None:
    async with factory() as session:
        await session.execute(bstore._capabilities.insert().values(
            id="cap-1", name="Inventory Management", description=None, level=1,
            parent_id=None, position=0, created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(bstore._value_chains.insert().values(
            id="vc-1", name="Retail", description="Stores and online", margin_label="Profit",
            position=0, created_at=_NOW, updated_at=_NOW,
        ))
        await session.execute(bstore._value_chain_activities.insert().values(
            id="act-ops", value_chain_id="vc-1", name="Operations", description=None,
            category="primary", position=0,
        ))
        await session.execute(bstore._value_chain_activities.insert().values(
            id="act-hr", value_chain_id="vc-1", name="HR Management", description=None,
            category="support", position=0,
        ))
        await session.execute(bstore._value_chain_activity_caps.insert().values(
            activity_id="act-ops", capability_id="cap-1",
        ))
        await session.commit()


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_serialize_value_chain_and_activity() -> None:
    chain = ValueChain(
        id="vc-1", name="Retail", description=None, margin_label="Margin", position=0,
        created_at=_NOW, updated_at=_NOW,
    )
    assert business_arch._serialize_value_chain(chain) == {
        "id": "vc-1", "name": "Retail", "description": None, "margin_label": "Margin",
        "position": 0,
    }
    activity = ValueChainActivity(
        id="act-1", value_chain_id="vc-1", name="Operations", description=None,
        category="primary", position=2,
    )
    assert business_arch._serialize_activity(activity, ["cap-b", "cap-a"]) == {
        "id": "act-1", "value_chain_id": "vc-1", "name": "Operations", "description": None,
        "category": "primary", "position": 2, "linked_capability_ids": ["cap-a", "cap-b"],
    }


async def test_value_chain_files_are_written(tmp_path, session_factory) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"
    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)

    chain_dir = root / "business-architecture" / "value-chains" / "vc-1"
    chain = _read_json(chain_dir / "value-chain.json")
    assert (chain["name"], chain["margin_label"]) == ("Retail", "Profit")
    assert "exported_at" in chain

    ops = _read_json(chain_dir / "activities" / "act-ops.json")
    assert (ops["category"], ops["linked_capability_ids"]) == ("primary", ["cap-1"])
    hr = _read_json(chain_dir / "activities" / "act-hr.json")
    assert (hr["category"], hr["linked_capability_ids"]) == ("support", [])


async def test_deleted_activity_and_chain_files_are_removed(tmp_path, session_factory) -> None:
    await _seed(session_factory)
    root = tmp_path / "export"
    chain_dir = root / "business-architecture" / "value-chains" / "vc-1"
    async with session_factory() as session:
        await business_arch.run_reconciliation_cycle(root, session)
    assert (chain_dir / "activities" / "act-hr.json").exists()

    async with session_factory() as session:
        await session.execute(
            bstore._value_chain_activities.delete().where(
                bstore._value_chain_activities.c.id == "act-hr"
            )
        )
        await session.commit()
        await business_arch.run_reconciliation_cycle(root, session)
    assert not (chain_dir / "activities" / "act-hr.json").exists()
    assert (chain_dir / "activities" / "act-ops.json").exists()

    async with session_factory() as session:
        await session.execute(bstore._value_chain_activity_caps.delete())
        await session.execute(bstore._value_chain_activities.delete())
        await session.execute(bstore._value_chains.delete())
        await session.commit()
        await business_arch.run_reconciliation_cycle(root, session)
    assert not chain_dir.exists()
