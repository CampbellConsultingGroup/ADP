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
    mock_index.get_all_active_ids = AsyncMock(return_value=set())
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
    # PAT-001 was previously active
    mock_index.get_all_active_ids = AsyncMock(return_value={"PAT-001"})
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
    mock_index.get_all_active_ids = AsyncMock(return_value=set())
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
