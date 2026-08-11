"""Unit tests: CRUD store functions for the Diagrams domain (ADP-SPEC-046
T007), against a SQLite-backed adp.diagrams.store. Explicitly asserts no
design_id column/FK exists on the table (FR-011 -- standalone in v1)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.diagrams import store as dstore
from adp.diagrams.models import DiagramCreate, DiagramUpdate


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/diagrams.db")
    async with engine.begin() as conn:
        await conn.run_sync(dstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def test_diagrams_table_has_no_design_id_column() -> None:
    # FR-011: standalone in v1 -- no relationship to designs at all.
    assert "design_id" not in dstore._diagrams.c
    assert not any(fk.column.table.name == "designs" for fk in dstore._diagrams.foreign_keys)


async def test_create_persists_and_defaults(session) -> None:
    d = await dstore.create_diagram(
        DiagramCreate(title="Claims Intake", diagram_type="flowchart"),
        actor="alice",
        session=session,
    )
    assert d.id
    assert d.title == "Claims Intake"
    assert d.dsl_source == ""
    assert d.created_by == "alice"
    assert d.created_at == d.updated_at


async def test_get_returns_none_for_unknown_id(session) -> None:
    assert await dstore.get_diagram("nonexistent", session) is None


async def test_get_returns_full_content(session) -> None:
    created = await dstore.create_diagram(
        DiagramCreate(title="T", diagram_type="sequence", dsl_source="sequenceDiagram\n"),
        actor=None,
        session=session,
    )
    fetched = await dstore.get_diagram(created.id, session)
    assert fetched is not None
    assert fetched.dsl_source == "sequenceDiagram\n"


async def test_list_returns_summaries_across_types(session) -> None:
    await dstore.create_diagram(
        DiagramCreate(title="A", diagram_type="flowchart"), actor=None, session=session
    )
    await dstore.create_diagram(
        DiagramCreate(title="B", diagram_type="erd"), actor=None, session=session
    )
    resp = await dstore.list_diagrams(session)
    assert resp.total == 2
    assert {item.diagram_type for item in resp.items} == {"flowchart", "erd"}
    assert all(not hasattr(item, "dsl_source") for item in resp.items)


async def test_update_partial_changes_only_given_fields(session) -> None:
    created = await dstore.create_diagram(
        DiagramCreate(title="Original", diagram_type="uml", dsl_source="classDiagram\n"),
        actor=None,
        session=session,
    )
    updated = await dstore.update_diagram(
        created.id, DiagramUpdate(dsl_source="classDiagram\nclass Foo\n"), session
    )
    assert updated is not None
    assert updated.title == "Original"  # untouched
    assert updated.dsl_source == "classDiagram\nclass Foo\n"
    assert updated.updated_at >= created.updated_at


async def test_update_returns_none_for_unknown_id(session) -> None:
    result = await dstore.update_diagram("nonexistent", DiagramUpdate(title="X"), session)
    assert result is None


async def test_delete_removes_diagram(session) -> None:
    created = await dstore.create_diagram(
        DiagramCreate(title="Doomed", diagram_type="architecture"), actor=None, session=session
    )
    deleted = await dstore.delete_diagram(created.id, session)
    assert deleted is True
    assert await dstore.get_diagram(created.id, session) is None


async def test_delete_returns_false_for_unknown_id(session) -> None:
    assert await dstore.delete_diagram("nonexistent", session) is False


async def test_diagram_type_immutable_via_update_model() -> None:
    # DiagramUpdate has no diagram_type field at all (test_diagrams_models.py
    # already covers this) -- this test documents that the store layer has no
    # code path to change it either, since the update SQL only ever touches
    # columns present on the DiagramUpdate instance.
    assert "diagram_type" not in DiagramUpdate.model_fields
