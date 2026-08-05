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

The domain-agnostic mechanics (path safety, atomic writes, content-diff-aware
writes, orphan cleanup, background-loop lifecycle) live in `adp.export.common`
as of ADP-SPEC-045 (research.md Decision 5) -- imported here rather than
redefined, so this module's own tests (which reference these names as
`business_arch._write_file_atomic` etc.) keep working unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.business import store as bstore
from adp.business.models import BusinessCapability, BusinessDomain, ValueStream, ValueStreamStage
from adp.export.common import (
    _cleanup_orphan_dirs,
    _cleanup_orphan_files,
    _safe_filename,
    _safe_path_component,
    _write_entity_file,
    _write_file_atomic,  # noqa: F401 -- re-exported for existing test references
    stop_background_sync,  # noqa: F401 -- re-exported
)
from adp.export.common import start_background_sync as _common_start_background_sync

_logger = logging.getLogger("adp.export.business_arch")


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
# _write_entity_file / _cleanup_orphan_files / _cleanup_orphan_dirs are now
# defined in adp.export.common (imported above) and used here unchanged.

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
# The generic loop/lifecycle now lives in adp.export.common (imported above);
# this is a thin, domain-bound wrapper so existing call sites/tests keep the
# exact same 3-arg signature (no reconcile_fn parameter to pass themselves).

def start_background_sync(
    export_root: str | None,
    interval_seconds: float,
    session_factory: Callable[[], Any],
) -> asyncio.Task[None] | None:
    """Start the periodic reconciliation loop. A no-op (returns None, starts
    nothing, writes nothing) when `export_root` is falsy -- this feature is
    opt-in, never a silent default write to some assumed path (research.md
    Decision 4)."""
    return _common_start_background_sync(
        export_root,
        interval_seconds,
        session_factory,
        run_reconciliation_cycle,
        logger_name="adp.export.business_arch",
    )
