"""Continuous export of Business Architecture data to versioned JSON files
(ADP-SPEC-044 / ADP-81p.1).

Postgres remains the interactive source of truth (ART-II); this module is a
read-only, best-effort background projection of business_capabilities,
value_streams, value_stream_stages (with their linked capabilities), and
business_domains onto the filesystem, for AI/tool consumption without direct
database access (ART-III). See specs/044-business-arch-export/ for the full
spec, research, and data model.

Sync mechanism (research.md Decision 1): a periodic full-reconciliation scan,
not event-driven write-path hooks -- deliberately touches nothing in
adp.business.store. Change detection (Decision 2) compares candidate file
content against what's already on disk; no new database table is introduced.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.business import store as bstore
from adp.business.models import BusinessCapability, BusinessDomain, ValueStream, ValueStreamStage

_logger = logging.getLogger("adp.export.business_arch")

# File/directory names are always derived from an entity's own internal ID,
# never its user-editable name -- IDs from adp.business.store are UUIDs
# (str(uuid.uuid4())), so this is a defense-in-depth check, not the only
# thing standing between a crafted name and a path-traversal write.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_path_component(entity_id: str) -> str:
    """Validate entity_id is safe to use as a path component (directory or
    filename stem), raising if not (Threat Model: never build a path from
    user-supplied text)."""
    if not _SAFE_ID_RE.match(entity_id):
        raise ValueError(f"Unsafe entity id for a file path: {entity_id!r}")
    return entity_id


def _safe_filename(entity_id: str) -> str:
    """Return f"{entity_id}.json", raising if entity_id isn't a safe path
    component."""
    return f"{_safe_path_component(entity_id)}.json"


# ── Serialization (data-model.md §2) ─────────────────────────────────────────
# Pure functions: no I/O, no `exported_at` (stamped separately at write time,
# see _write_entity_file, so that field alone never makes an unchanged entity
# look "changed" to the content-comparison in research.md Decision 2).

def _serialize_capability(cap: BusinessCapability) -> dict[str, Any]:
    return {
        "id": cap.id,
        "name": cap.name,
        "description": cap.description,
        "level": cap.level,
        "parent_id": cap.parent_id,
        "position": cap.position,
        "domain_id": cap.domain_id,
        "strategic_relevance": cap.strategic_relevance,
        "maturity_level": cap.maturity_level,
    }


def _serialize_domain(domain: BusinessDomain) -> dict[str, Any]:
    return {
        "id": domain.id,
        "name": domain.name,
        "scope_statement": domain.scope_statement,
        "classification": domain.classification,
        "org_unit": domain.org_unit,
        "risk_flags": list(domain.risk_flags),
    }


def _serialize_value_stream(vs: ValueStream) -> dict[str, Any]:
    return {
        "id": vs.id,
        "name": vs.name,
        "description": vs.description,
        "stakeholder": vs.stakeholder,
        "position": vs.position,
    }


def _write_file_atomic(path: Path, content: str) -> None:
    """Write `content` to `path` via temp-file-then-`os.replace` (FR-007) --
    a crash or failure mid-write never leaves a partially-written file in
    place of a previously-good one. The temp file lives in the SAME
    directory as `path` so the final `os.replace` is a same-filesystem
    rename (atomic), not a cross-filesystem copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _serialize_stage(
    stage: ValueStreamStage, linked_capability_ids: list[str]
) -> dict[str, Any]:
    return {
        "id": stage.id,
        "value_stream_id": stage.value_stream_id,
        "name": stage.name,
        "description": stage.description,
        "position": stage.position,
        "linked_capability_ids": sorted(linked_capability_ids),
    }


# ── Bulk read (research.md Decision 1 — full reconciliation, not per-write
# hooks; reuses adp.business.store's existing functions/tables read-only) ────

@dataclass(frozen=True)
class BusinessArchSnapshot:
    capabilities: list[BusinessCapability]
    domains: list[BusinessDomain]
    value_streams: list[ValueStream]
    stages: list[ValueStreamStage]
    # stage_id -> capability_ids linked to it (possibly empty, never missing
    # a key for a stage that exists in `stages`).
    stage_links: dict[str, list[str]] = field(default_factory=dict)


async def _fetch_all(session: AsyncSession) -> BusinessArchSnapshot:
    """One reconciliation cycle's complete live snapshot -- a small, fixed
    number of queries (not one per entity), reusing adp.business.store's
    existing read functions/tables directly rather than duplicating query
    logic. No existing function lists every stage across every value stream
    at once (the closest, `get_value_stream`, is scoped to one value stream),
    so stages and their links are read directly from the store's own Core
    Table objects instead."""
    capabilities = await bstore.list_capabilities(session)
    domains = await bstore.list_domains_full(session)
    value_streams = await bstore.list_value_streams(session)

    stage_rows = await session.execute(sa.select(bstore._stages))
    stages = [bstore._row_to_stage(row) for row in stage_rows.mappings().all()]

    link_rows = await session.execute(sa.select(bstore._stage_caps))
    stage_links: dict[str, list[str]] = {stage.id: [] for stage in stages}
    for row in link_rows.mappings().all():
        stage_links.setdefault(row.stage_id, []).append(row.capability_id)

    return BusinessArchSnapshot(
        capabilities=capabilities,
        domains=domains,
        value_streams=value_streams,
        stages=stages,
        stage_links=stage_links,
    )


# ── Reconciliation orchestration ─────────────────────────────────────────────

def _write_entity_file(path: Path, data: dict[str, Any], now: datetime) -> None:
    """Stamp `exported_at` and write via `_write_file_atomic` -- unless the
    file already exists with identical content (ignoring `exported_at`),
    in which case do nothing at all, not even touch its mtime (research.md
    Decision 2, FR-009)."""
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing is not None:
            existing.pop("exported_at", None)
            if existing == data:
                return
    stamped = {**data, "exported_at": now.isoformat()}
    content = json.dumps(stamped, indent=2, sort_keys=True) + "\n"
    _write_file_atomic(path, content)


def _cleanup_orphan_files(dir_path: Path, live_ids: set[str]) -> None:
    """Remove any `<id>.json` file in `dir_path` whose id is no longer live
    (FR-004). A no-op if `dir_path` doesn't exist (nothing was ever exported
    here, or it was already removed by _cleanup_orphan_dirs)."""
    if not dir_path.is_dir():
        return
    for f in dir_path.glob("*.json"):
        if f.stem not in live_ids:
            f.unlink()


def _cleanup_orphan_dirs(parent_dir: Path, live_ids: set[str]) -> None:
    """Remove any immediate subdirectory of `parent_dir` whose name (an
    entity id) is no longer live -- used for value streams, where a deleted
    value stream's whole directory (value-stream.json + its stages/ subtree)
    is removed in one step rather than reconciled as an empty stage set
    against a value-stream.json that's about to be deleted anyway
    (data-model.md §3 step 5)."""
    if not parent_dir.is_dir():
        return
    for d in parent_dir.iterdir():
        if d.is_dir() and d.name not in live_ids:
            shutil.rmtree(d)


async def run_reconciliation_cycle(export_root: Path | str, session: AsyncSession) -> None:
    """One full reconciliation pass: read everything live, write every
    entity's file. Any failure is caught, logged, and swallowed (FR-006) --
    the background loop (User Story 1, T013) keeps running on schedule
    regardless of one bad cycle."""
    try:
        snapshot = await _fetch_all(session)
        root = Path(export_root) / "business-architecture"
        now = datetime.now(timezone.utc)

        for cap in snapshot.capabilities:
            _write_entity_file(
                root / "capabilities" / _safe_filename(cap.id), _serialize_capability(cap), now
            )
        for domain in snapshot.domains:
            _write_entity_file(
                root / "domains" / _safe_filename(domain.id), _serialize_domain(domain), now
            )
        for vs in snapshot.value_streams:
            vs_dir = root / "value-streams" / _safe_path_component(vs.id)
            _write_entity_file(vs_dir / "value-stream.json", _serialize_value_stream(vs), now)
        for stage in snapshot.stages:
            vs_dir = root / "value-streams" / _safe_path_component(stage.value_stream_id)
            linked = snapshot.stage_links.get(stage.id, [])
            _write_entity_file(
                vs_dir / "stages" / _safe_filename(stage.id),
                _serialize_stage(stage, linked),
                now,
            )

        # Orphan cleanup (FR-004): remove files/directories for entities that
        # no longer exist. A deleted value stream's whole directory (its
        # value-stream.json plus its stages/ subtree) is removed in one step;
        # for each STILL-LIVE value stream, its own stage files are reconciled
        # individually against that value stream's current live stage set.
        live_capability_ids = {c.id for c in snapshot.capabilities}
        live_domain_ids = {d.id for d in snapshot.domains}
        live_vs_ids = {vs.id for vs in snapshot.value_streams}

        _cleanup_orphan_files(root / "capabilities", live_capability_ids)
        _cleanup_orphan_files(root / "domains", live_domain_ids)
        _cleanup_orphan_dirs(root / "value-streams", live_vs_ids)

        stage_ids_by_vs: dict[str, set[str]] = {}
        for stage in snapshot.stages:
            stage_ids_by_vs.setdefault(stage.value_stream_id, set()).add(stage.id)
        for vs_id in live_vs_ids:
            _cleanup_orphan_files(
                root / "value-streams" / vs_id / "stages", stage_ids_by_vs.get(vs_id, set())
            )
    except Exception:
        _logger.warning("business_arch_export.cycle_failed", exc_info=True)


# ── Background task lifecycle (User Story 1) ─────────────────────────────────
# No module-level task handle -- the caller (adp.api.app's lifespan) owns the
# returned Task and passes it back to stop_background_sync, so there's no
# shared mutable state to reset between app instances/tests.

async def _background_loop(
    export_root: Path,
    interval_seconds: float,
    session_factory: Callable[[], Any],
) -> None:
    while True:
        async with session_factory() as session:
            await run_reconciliation_cycle(export_root, session)
        await asyncio.sleep(interval_seconds)


def start_background_sync(
    export_root: str | None,
    interval_seconds: float,
    session_factory: Callable[[], Any],
) -> asyncio.Task[None] | None:
    """Start the periodic reconciliation loop. A no-op (returns None, starts
    nothing, writes nothing) when `export_root` is falsy -- this feature is
    opt-in, never a silent default write to some assumed path (research.md
    Decision 4)."""
    if not export_root:
        _logger.info("business_arch_export.disabled (ADP_BUSINESS_ARCH_EXPORT_ROOT not set)")
        return None
    return asyncio.create_task(
        _background_loop(Path(export_root), interval_seconds, session_factory)
    )


async def stop_background_sync(task: asyncio.Task[None] | None) -> None:
    """Cancel and await the background task started by start_background_sync.
    A no-op if `task` is None (the feature was never started)."""
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
