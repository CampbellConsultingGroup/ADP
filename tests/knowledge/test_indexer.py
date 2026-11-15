"""Tests for Indexer orchestration logic (US2 / FR-004) — no Docker needed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adp.knowledge.indexer import Indexer
from adp.knowledge.schema import KnowledgeItem, KnowledgeType


def _make_item(item_id: str = "PAT-001", version: str = "1.0.0") -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id, version=version, kind=KnowledgeType.PATTERN,
        title=f"Item {item_id}", full_text=f"Text for {item_id}",
        metadata={}, source_ref=f"git:test:{item_id}.md",
    )


def _async_ctx(session):
    """Helper: build a proper async context manager for session.begin()."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


def _make_session_factory(mock_index):
    """Return a session factory whose sessions delegate begin() correctly."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []  # get_all_active_ids returns empty set
    session.execute.return_value = result_mock
    # begin() must be a plain MagicMock so it returns the CM directly (not a coroutine)
    session.begin = MagicMock(return_value=_async_ctx(session))

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=ctx)
    return factory, session


@pytest.mark.asyncio
async def test_indexer_upserts_updated_item(tmp_path: Path) -> None:
    """Indexer calls upsert_item with the latest item version (US2)."""
    mock_index = AsyncMock()
    mock_index.get_active_source_refs = AsyncMock(return_value={})
    mock_index.upsert_item = AsyncMock()
    mock_index.upsert_relationship = AsyncMock()
    mock_index.mark_inactive = AsyncMock(return_value=0)

    factory, _ = _make_session_factory(mock_index)

    items_v1 = [_make_item("PAT-001", "1.0.0")]
    items_v11 = [_make_item("PAT-001", "1.1.0")]

    indexer = Indexer(
        database_url="postgresql+asyncpg://test/test",
        embedding_model="mock",
        embedding_dim=4,
        git_repo_urls=["file://test"],
        git_local_path=str(tmp_path),
    )
    indexer._embedder = MagicMock()
    indexer._embedder.embed_batch.return_value = [[0.1, 0.2, 0.3, 0.4]]

    mock_connector = MagicMock()
    mock_connector.pull_or_clone = MagicMock()
    mock_connector.read_items.return_value = iter(items_v1)
    mock_connector.read_relationships.return_value = iter([])

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with patch("adp.knowledge.indexer.create_async_engine", return_value=mock_engine), \
         patch("adp.knowledge.indexer.async_sessionmaker", return_value=factory), \
         patch("adp.knowledge.indexer.KnowledgeIndex", return_value=mock_index), \
         patch("adp.knowledge.indexer.GitConnector", return_value=mock_connector):
        await indexer.run()

    assert mock_index.upsert_item.called
    call_versions = [args[0][0].version for args in mock_index.upsert_item.call_args_list]
    assert "1.0.0" in call_versions

    # Second run with v1.1
    mock_index.upsert_item.reset_mock()
    mock_connector.read_items.return_value = iter(items_v11)
    with patch("adp.knowledge.indexer.create_async_engine", return_value=mock_engine), \
         patch("adp.knowledge.indexer.async_sessionmaker", return_value=factory), \
         patch("adp.knowledge.indexer.KnowledgeIndex", return_value=mock_index), \
         patch("adp.knowledge.indexer.GitConnector", return_value=mock_connector):
        await indexer.run()

    call_versions_v2 = [args[0][0].version for args in mock_index.upsert_item.call_args_list]
    assert "1.1.0" in call_versions_v2


@pytest.mark.asyncio
async def test_indexer_marks_absent_items_inactive(tmp_path: Path) -> None:
    """Items in prev_active_ids but absent this run are marked inactive (FR-004)."""
    mock_index = AsyncMock()
    # PAT-001 was previously active, indexed from the same git source
    mock_index.get_active_source_refs = AsyncMock(
        return_value={"PAT-001": "git:file://test:PAT-001.md"}
    )
    mock_index.upsert_item = AsyncMock()
    mock_index.upsert_relationship = AsyncMock()
    mock_index.mark_inactive = AsyncMock(return_value=1)

    factory, _ = _make_session_factory(mock_index)

    # This run only indexes PAT-002 — PAT-001 should be deactivated
    indexer = Indexer(
        database_url="postgresql+asyncpg://test/test",
        embedding_model="mock",
        embedding_dim=4,
        git_repo_urls=["file://test"],
        git_local_path=str(tmp_path),
    )
    indexer._embedder = MagicMock()
    indexer._embedder.embed_batch.return_value = [[0.1, 0.2, 0.3, 0.4]]

    mock_connector = MagicMock()
    mock_connector.pull_or_clone = MagicMock()
    mock_connector.read_items.return_value = iter([_make_item("PAT-002", "1.0.0")])
    mock_connector.read_relationships.return_value = iter([])

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with patch("adp.knowledge.indexer.create_async_engine", return_value=mock_engine), \
         patch("adp.knowledge.indexer.async_sessionmaker", return_value=factory), \
         patch("adp.knowledge.indexer.KnowledgeIndex", return_value=mock_index), \
         patch("adp.knowledge.indexer.GitConnector", return_value=mock_connector):
        result = await indexer.run()

    mock_index.mark_inactive.assert_called_once()
    deactivated_ids = mock_index.mark_inactive.call_args[0][0]
    assert "PAT-001" in deactivated_ids
    assert result.deactivated == 1


@pytest.mark.asyncio
async def test_indexer_connector_failure_does_not_block_others(tmp_path: Path) -> None:
    """A failing connector records an error but doesn't block other connectors (I2)."""
    mock_index = AsyncMock()
    mock_index.get_active_source_refs = AsyncMock(return_value={})
    mock_index.upsert_item = AsyncMock()
    mock_index.upsert_relationship = AsyncMock()
    mock_index.mark_inactive = AsyncMock(return_value=0)

    factory, _ = _make_session_factory(mock_index)

    indexer = Indexer(
        database_url="postgresql+asyncpg://test/test",
        embedding_model="mock",
        embedding_dim=4,
        git_repo_urls=["https://broken-repo.example.org"],
        git_local_path=str(tmp_path),
    )
    indexer._embedder = MagicMock()

    broken_connector = MagicMock()
    broken_connector.pull_or_clone = MagicMock(side_effect=ConnectionError("repo unreachable"))

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with patch("adp.knowledge.indexer.create_async_engine", return_value=mock_engine), \
         patch("adp.knowledge.indexer.async_sessionmaker", return_value=factory), \
         patch("adp.knowledge.indexer.KnowledgeIndex", return_value=mock_index), \
         patch("adp.knowledge.indexer.GitConnector", return_value=broken_connector):
        result = await indexer.run()

    # Run completes without raising; error is recorded in connector_errors
    assert "https://broken-repo.example.org" in result.connector_errors
    assert "repo unreachable" in result.connector_errors["https://broken-repo.example.org"]


# ── 935-pattern-registry: registry-owned items are not deactivation candidates ──────

async def _run(
    tmp_path: Path,
    prev: dict[str, str],
    *,
    repo_urls: list[str] | None = None,
    connector: MagicMock | None = None,
    upsert_error: bool = False,
    design_store_items: list[KnowledgeItem] | None = None,
):  # type: ignore[no-untyped-def]
    """Run the indexer against mocks; return (result, ids passed to mark_inactive)."""
    mock_index = AsyncMock()
    mock_index.get_active_source_refs = AsyncMock(return_value=prev)
    mock_index.upsert_item = AsyncMock(side_effect=RuntimeError("db") if upsert_error else None)
    mock_index.upsert_relationship = AsyncMock()
    mock_index.mark_inactive = AsyncMock(side_effect=lambda ids, session: len(ids))
    factory, _ = _make_session_factory(mock_index)
    indexer = Indexer(
        database_url="postgresql+asyncpg://test/test", embedding_model="mock", embedding_dim=4,
        git_repo_urls=repo_urls or [], git_local_path=str(tmp_path),
        design_store=object() if design_store_items is not None else None,
    )
    indexer._embedder = MagicMock()
    indexer._embedder.embed_batch.side_effect = lambda texts: [[0.1, 0.2, 0.3, 0.4]] * len(texts)

    ds_connector = MagicMock()

    async def _ds_items():  # type: ignore[no-untyped-def]
        for item in design_store_items or []:
            yield item

    ds_connector.read_items = _ds_items
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    with patch("adp.knowledge.indexer.create_async_engine", return_value=mock_engine), \
         patch("adp.knowledge.indexer.async_sessionmaker", return_value=factory), \
         patch("adp.knowledge.indexer.KnowledgeIndex", return_value=mock_index), \
         patch("adp.knowledge.indexer.GitConnector", return_value=connector or MagicMock()), \
         patch("adp.knowledge.connectors.design_store.DesignStoreConnector",
               return_value=ds_connector):
        result = await indexer.run()
    calls = mock_index.mark_inactive.call_args_list
    swept = sorted(calls[0][0][0]) if calls else []
    return result, swept


def _git_connector(items: list[KnowledgeItem]) -> MagicMock:
    c = MagicMock()
    c.read_items.return_value = iter(items)
    c.read_relationships.return_value = iter([])
    return c


# ── ADP-4zn: the sweep only touches items owned by a connector that ran ─────────────

@pytest.mark.asyncio
async def test_sweep_ignores_items_no_connector_owns(tmp_path: Path) -> None:
    """API-, CALM-, seed- and pattern-registry items come from no connector: never swept."""
    prev = {
        "PAT-001": "git:file://test:PAT-001.md",          # owned by the git source that ran
        "PRIN-003": "https://example.com/api-first",      # seed_knowledge.py / API create
        "calm-event-driven": "calm:event-driven",         # CALM import
        "manual-1": "Architecture board minutes 2026-03",  # free-text API source_ref
        "adp-pattern:ea.x.y": "adp-pattern:ea.x.y",        # pattern registry (935)
        "DSN-1": "adp-store:DSN-1",                        # design store did not run
    }
    item = _make_item("PAT-002")
    item = item.model_copy(update={"source_ref": "git:file://test:PAT-002.md"})
    result, swept = await _run(
        tmp_path, prev, repo_urls=["file://test"], connector=_git_connector([item])
    )
    assert swept == ["PAT-001"]
    assert result.deactivated == 1


@pytest.mark.asyncio
async def test_failed_connector_sweeps_nothing_of_its_own(tmp_path: Path) -> None:
    broken = MagicMock()
    broken.pull_or_clone = MagicMock(side_effect=ConnectionError("repo unreachable"))
    prev = {"PAT-001": "git:https://broken.example.org:PAT-001.md"}
    result, swept = await _run(
        tmp_path, prev, repo_urls=["https://broken.example.org"], connector=broken
    )
    assert swept == []
    assert result.deactivated == 0
    assert "https://broken.example.org" in result.connector_errors


@pytest.mark.asyncio
async def test_item_still_in_source_is_kept_even_if_its_upsert_failed(tmp_path: Path) -> None:
    prev = {"PAT-001": "git:file://test:PAT-001.md"}
    result, swept = await _run(
        tmp_path, prev, repo_urls=["file://test"],
        connector=_git_connector([_make_item("PAT-001")]), upsert_error=True,
    )
    assert swept == []
    assert result.failed == 1


@pytest.mark.asyncio
async def test_design_store_items_swept_only_when_that_connector_ran(tmp_path: Path) -> None:
    prev = {"DSN-1": "adp-store:DSN-1", "DSN-2": "adp-store:DSN-2"}
    _, without_store = await _run(tmp_path, prev)
    assert without_store == []
    kept = _make_item("DSN-2").model_copy(update={"source_ref": "adp-store:DSN-2"})
    _, with_store = await _run(tmp_path, prev, design_store_items=[kept])
    assert with_store == ["DSN-1"]


@pytest.mark.asyncio
async def test_get_active_source_refs_on_sqlite(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adp.knowledge.index import KnowledgeIndex
    from adp.patterns import store as pstore

    knowledge_items = pstore._knowledge_items
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/kb_refs.db")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: pstore._metadata.create_all(c, tables=[knowledge_items]))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with factory() as session:
        for item_id, ref, active in (("A", "git:r:A.md", True), ("B", "calm:b", True),
                                     ("C", "git:r:C.md", False)):
            await session.execute(
                knowledge_items.insert().values(
                    id=item_id, version="1.0.0", kind="pattern", title=item_id, full_text="t",
                    metadata={}, source_ref=ref, schema_version="1.0.0", active=active,
                    embedding=[0.0] * 384, indexed_at=now,
                )
            )
        await session.commit()
        refs = await KnowledgeIndex(factory).get_active_source_refs(session)
        assert refs == {"A": "git:r:A.md", "B": "calm:b"}
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_all_active_ids_honours_excluded_prefixes(tmp_path: Path) -> None:
    """Real query on SQLite: excluded source prefixes are never returned (935 research D7)."""
    from datetime import datetime, timezone

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from adp.knowledge.index import KnowledgeIndex
    from adp.patterns import store as pstore

    # knowledge_items' own metadata uses JSONB/Vector (Postgres-only); the pattern registry's
    # full-column mirror of the same table carries SQLite variants, so create it from there.
    knowledge_items = pstore._knowledge_items
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/kb.db")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: pstore._metadata.create_all(c, tables=[knowledge_items])
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with factory() as session:
        for item_id, ref, active in (
            ("PAT-001", "git:x", True),
            ("adp-pattern:ea.a.b", "adp-pattern:ea.a.b", True),
            ("PAT-002", "git:y", False),
        ):
            await session.execute(
                knowledge_items.insert().values(
                    id=item_id, version="1.0.0", kind="pattern", title=item_id, full_text="t",
                    metadata={}, source_ref=ref, schema_version="1.0.0", active=active,
                    embedding=[0.0] * 384, indexed_at=now,
                )
            )
        await session.commit()
        index = KnowledgeIndex(factory)
        assert await index.get_all_active_ids(session) == {"PAT-001", "adp-pattern:ea.a.b"}
        assert await index.get_all_active_ids(
            session, exclude_source_prefixes=("adp-pattern:",)
        ) == {"PAT-001"}
    await engine.dispose()

