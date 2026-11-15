"""Nightly knowledge base indexer — orchestrates connectors → embedder → index."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.knowledge.connectors.git import GitConnector
from adp.knowledge.embedder import EmbeddingProvider
from adp.knowledge.index import KnowledgeIndex
from adp.knowledge.schema import KnowledgeItem

_logger = logging.getLogger("adp.knowledge")


@dataclass
class IndexerResult:
    indexed: int = 0
    updated: int = 0
    deactivated: int = 0
    failed: int = 0
    connector_errors: dict[str, str] = field(default_factory=dict)


# The ``source_ref`` prefix each connector writes (connectors/git.py, connectors/design_store.py).
# The deactivation sweep is scoped to items whose source_ref starts with the prefix of a connector
# that completed successfully in this run (ADP-4zn). Items written by anything else -- the
# knowledge API, CALM import, seed_knowledge.py, the pattern registry -- are never swept.
DESIGN_STORE_PREFIX = "adp-store:"


def git_prefix(repo_url: str) -> str:
    return f"git:{repo_url}:"


class Indexer:
    """Orchestrates nightly re-indexing from all canonical knowledge sources."""

    def __init__(
        self,
        database_url: str,
        embedding_model: str,
        embedding_dim: int = 384,
        git_repo_urls: list[str] | None = None,
        git_local_path: str = "",
        design_store: Any = None,
    ) -> None:
        self._database_url = database_url
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        self._git_repo_urls = git_repo_urls or []
        self._git_local_path = git_local_path
        self._design_store = design_store
        self._embedder = EmbeddingProvider(embedding_model)

    async def run(self) -> IndexerResult:
        """Execute a full re-index run. Per-connector failures don't block others."""
        engine = create_async_engine(self._database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        index = KnowledgeIndex(session_factory)
        result = IndexerResult()
        seen_ids: set[str] = set()
        # Source prefixes of connectors that read their source completely this run. Only items
        # under these prefixes are deactivation candidates (ADP-4zn).
        owned_prefixes: list[str] = []

        # Previously active items, with their source_ref, for deactivation tracking.
        async with session_factory() as session:
            async with session.begin():
                prev_active = await index.get_active_source_refs(session)

        # --- Git connectors ---
        for repo_url in self._git_repo_urls:
            try:
                connector = GitConnector(
                    repo_url=repo_url,
                    local_path=os.path.join(self._git_local_path, _repo_slug(repo_url)),
                )
                connector.pull_or_clone()
                items = list(connector.read_items())
                relationships = list(connector.read_relationships())
                # Still present in the source -> never swept, even if its upsert fails below.
                seen_ids.update(item.id for item in items)

                # Batch-embed all items from this connector.
                if items:
                    texts = [item.full_text for item in items]
                    embeddings = self._embedder.embed_batch(texts)

                    async with session_factory() as session:
                        async with session.begin():
                            for item, emb in zip(items, embeddings):
                                try:
                                    await index.upsert_item(item, emb, session)
                                    seen_ids.add(item.id)
                                    result.indexed += 1
                                except Exception as exc:
                                    _logger.warning("Failed to index item %s: %s", item.id, exc)
                                    result.failed += 1

                            for rel in relationships:
                                try:
                                    await index.upsert_relationship(rel, session)
                                except Exception:
                                    pass

                owned_prefixes.append(git_prefix(repo_url))
            except Exception as exc:
                result.connector_errors[repo_url] = str(exc)
                _logger.error("Connector failed for %s: %s", repo_url, exc)

        # --- ADP Design Store connector ---
        if self._design_store is not None:
            try:
                from adp.knowledge.connectors.design_store import DesignStoreConnector

                ds_connector = DesignStoreConnector(self._design_store)
                ds_items: list[KnowledgeItem] = []
                async for ds_item in ds_connector.read_items():
                    ds_items.append(ds_item)
                seen_ids.update(i.id for i in ds_items)

                if ds_items:
                    ds_texts = [i.full_text for i in ds_items]
                    ds_embeddings = self._embedder.embed_batch(ds_texts)

                    async with session_factory() as session:
                        async with session.begin():
                            for ds_item, ds_emb in zip(ds_items, ds_embeddings):
                                try:
                                    await index.upsert_item(ds_item, ds_emb, session)
                                    seen_ids.add(ds_item.id)
                                    result.indexed += 1
                                except Exception as exc:
                                    _logger.warning(
                                        "Failed to index design %s: %s", ds_item.id, exc
                                    )
                                    result.failed += 1

                owned_prefixes.append(DESIGN_STORE_PREFIX)
            except Exception as exc:
                result.connector_errors["design_store"] = str(exc)
                _logger.error("Design store connector failed: %s", exc)

        # Deactivate items that a successfully-read source owns but no longer contains.
        to_deactivate = sorted(
            item_id
            for item_id, source_ref in prev_active.items()
            if item_id not in seen_ids
            and any(source_ref.startswith(prefix) for prefix in owned_prefixes)
        )
        if to_deactivate:
            async with session_factory() as session:
                async with session.begin():
                    result.deactivated = await index.mark_inactive(to_deactivate, session)

        await engine.dispose()
        return result


def _repo_slug(url: str) -> str:
    return url.rstrip("/").split("/")[-1].replace(".git", "")


def main() -> None:
    database_url = os.environ["ADP_DATABASE_URL"]
    embedding_model = os.environ["ADP_EMBEDDING_MODEL"]
    embedding_dim = int(os.environ.get("ADP_EMBEDDING_DIM", "384"))
    git_urls = [u for u in os.environ.get("ADP_GIT_REPO_URLS", "").split(",") if u]
    git_path = os.environ.get("ADP_GIT_LOCAL_CLONE_PATH", "/tmp/adp-knowledge")  # nosec B108 - path configurable via env var

    indexer = Indexer(
        database_url=database_url,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        git_repo_urls=git_urls,
        git_local_path=git_path,
    )

    result = asyncio.run(indexer.run())
    print(f"✓ Re-index complete: {result.indexed} indexed, "
          f"{result.deactivated} deactivated, {result.failed} failed")
    if result.connector_errors:
        for connector, err in result.connector_errors.items():
            print(f"⚠ Connector error [{connector}]: {err}")
