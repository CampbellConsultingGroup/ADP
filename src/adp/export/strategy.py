"""Continuous export of the Strategy domain to versioned JSON files
(ADP-81p.3, bead ADP-81p.3).

Postgres remains the interactive source of truth (ART-II); this module is a
read-only, best-effort background projection of strategic themes,
objectives (with their computed status, full progress history, and every
cross-domain traceability link), and strategy initiatives (with their
objective links and live compliance-mapping status) onto the filesystem.
See specs/928-strategy-export/ for the full spec, research, and data model.

Sibling to adp.export.business_arch (ADP-SPEC-044) and
adp.export.application_arch (ADP-SPEC-045); reuses the shared,
domain-agnostic mechanics in adp.export.common (that module's own research.md
Decision 5) rather than re-implementing atomic writes, content-diffing,
orphan cleanup, or the background-loop lifecycle a third time. Named
`strategy.py`, not `strategy_arch.py` (research.md Decision 7) -- Strategy is
not itself an architecture domain the way Business/Application are.

Per this feature's own Clarification Q2, adp.export.business_arch is also
extended (not by this module) with a `linked_designs` field on its capability/
value-stream files -- see that module's own docstring/diff.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.export import common
from adp.export.common import (
    _cleanup_orphan_files,
    _safe_filename,
    _write_entity_file,
)
from adp.strategy import initiatives as sinit
from adp.strategy import store as sstore
from adp.strategy.initiatives import ControlMappingRef, StrategyInitiative
from adp.strategy.models import ObjectiveStatus, StrategicTheme

_logger = logging.getLogger("adp.export.strategy")


# ── Serialization (data-model.md) ────────────────────────────────────────────
# Pure functions: no I/O, no `exported_at` (stamped separately at write time by
# adp.export.common._write_entity_file, so that field alone never makes an
# unchanged entity look "changed" to the content-comparison).


def _serialize_theme(theme: StrategicTheme) -> dict[str, Any]:
    return {
        "id": theme.id,
        "name": theme.name,
        "description": theme.description,
        "owner": theme.owner,
        "priority": theme.priority,
        "framework_ids": list(theme.framework_ids),
        "created_at": theme.created_at.isoformat(),
    }


def _serialize_progress_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": entry["as_of_date"].isoformat(),
        "actual_value": str(entry["actual_value"]),
        "note": entry["note"],
        "recorded_by": entry["recorded_by"],
    }


def _serialize_objective(
    row: Any,
    *,
    status: ObjectiveStatus,
    status_reason: str | None,
    capability_ids: list[str],
    value_stream_ids: list[str],
    design_ids: list[str],
    application_ids: list[str],
    control_ids: list[str],
    depends_on_objective_ids: list[str],
    blocked_objective_ids: list[str],
    initiative_ids: list[str],
    progress: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": row.id,
        "theme_id": row.theme_id,
        "owner": row.owner,
        "statement": row.statement,
        "metric_name": row.metric_name,
        "target_value": str(row.target_value) if row.target_value is not None else None,
        "target_unit": row.target_unit,
        "direction": row.direction,
        "fiscal_year": row.fiscal_year,
        "period": row.period,
        "status": status,
        "status_reason": status_reason,
        "capability_ids": capability_ids,
        "value_stream_ids": value_stream_ids,
        "design_ids": design_ids,
        "application_ids": application_ids,
        "control_ids": control_ids,
        "depends_on_objective_ids": depends_on_objective_ids,
        "blocked_objective_ids": blocked_objective_ids,
        "initiative_ids": initiative_ids,
        "progress": [_serialize_progress_entry(p) for p in progress],
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_control_mapping(ref: ControlMappingRef) -> dict[str, Any]:
    return {
        "control_id": ref.control_id,
        "target_type": ref.target_type.value,
        "target_id": ref.target_id,
        "compliance_status": ref.compliance_status.value,
        "evidence_ref": ref.evidence_ref,
        "assessed_at": ref.assessed_at.isoformat() if ref.assessed_at else None,
    }


def _serialize_initiative(initiative: StrategyInitiative) -> dict[str, Any]:
    return {
        "id": initiative.id,
        "name": initiative.name,
        "description": initiative.description,
        "owner": initiative.owner,
        "status": initiative.status,
        "objective_ids": list(initiative.objective_ids),
        "control_mappings": [
            _serialize_control_mapping(cm) for cm in initiative.control_mappings
        ],
        "created_at": initiative.created_at.isoformat(),
        "updated_at": initiative.updated_at.isoformat(),
    }


# ── Bulk read (research.md Decision 4 — small fixed query count; reuses
# adp.strategy.store/adp.strategy.initiatives's existing bulk-list functions
# where they exist, direct Table queries where they don't) ─────────────────


@dataclass(frozen=True)
class StrategyExportSnapshot:
    themes: list[StrategicTheme]
    objective_rows: list[Any]
    initiatives: list[StrategyInitiative]
    capability_ids_by_objective: dict[str, list[str]] = field(default_factory=dict)
    value_stream_ids_by_objective: dict[str, list[str]] = field(default_factory=dict)
    design_ids_by_objective: dict[str, list[str]] = field(default_factory=dict)
    application_ids_by_objective: dict[str, list[str]] = field(default_factory=dict)
    control_ids_by_objective: dict[str, list[str]] = field(default_factory=dict)
    depends_on_by_objective: dict[str, list[str]] = field(default_factory=dict)
    blocks_by_objective: dict[str, list[str]] = field(default_factory=dict)
    initiative_ids_by_objective: dict[str, list[str]] = field(default_factory=dict)
    objective_ids_by_initiative: dict[str, list[str]] = field(default_factory=dict)
    progress_by_objective: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


async def _grouped_ids(
    session: AsyncSession, table: sa.Table, group_col: str, value_col: str
) -> dict[str, list[str]]:
    """Bulk `SELECT group_col, value_col FROM table`, grouped client-side into
    a dict[str, list[str]], sorted for diff stability (mirrors
    _linked_capability_ids's/etc.'s own ORDER BY convention, applied in bulk
    instead of per-objective)."""
    result = await session.execute(
        sa.select(getattr(table.c, group_col), getattr(table.c, value_col))
    )
    out: dict[str, list[str]] = {}
    for row in result:
        out.setdefault(row[0], []).append(row[1])
    for ids in out.values():
        ids.sort()
    return out


async def _fetch_all(session: AsyncSession) -> StrategyExportSnapshot:
    """One reconciliation cycle's complete live snapshot -- a small, fixed
    number of queries (not one per theme/objective/initiative), matching
    ADP-SPEC-045's own research.md Decision 4."""
    themes = (await sstore.list_themes(session)).items

    objective_rows = list(
        (await session.execute(sa.select(sstore._objectives))).fetchall()
    )

    capability_ids_by_objective = await _grouped_ids(
        session, sstore._objective_capabilities, "objective_id", "capability_id"
    )
    value_stream_ids_by_objective = await _grouped_ids(
        session, sstore._objective_value_streams, "objective_id", "value_stream_id"
    )
    design_ids_by_objective = await _grouped_ids(
        session, sstore._objective_design_links, "objective_id", "design_id"
    )
    application_ids_by_objective = await _grouped_ids(
        session, sstore._objective_application_links, "objective_id", "application_id"
    )
    control_ids_by_objective = await _grouped_ids(
        session, sstore._objective_control_links, "objective_id", "control_id"
    )

    depends_on_by_objective = await _grouped_ids(
        session, sinit._objective_dependencies, "objective_id", "depends_on_objective_id"
    )
    blocks_by_objective = await _grouped_ids(
        session, sinit._objective_dependencies, "depends_on_objective_id", "objective_id"
    )

    objective_ids_by_initiative = await _grouped_ids(
        session, sinit._initiative_objective_links, "initiative_id", "objective_id"
    )
    initiative_ids_by_objective = await _grouped_ids(
        session, sinit._initiative_objective_links, "objective_id", "initiative_id"
    )

    progress_rows = (
        await session.execute(
            sa.select(sstore._progress).order_by(sstore._progress.c.as_of_date)
        )
    ).mappings().all()
    progress_by_objective: dict[str, list[dict[str, Any]]] = {}
    for row in progress_rows:
        progress_by_objective.setdefault(row["objective_id"], []).append(dict(row))

    # Deviation from research.md Decision 4's original fully-bulk plan, recorded rather than
    # silently patched over: sinit.list_initiatives() calls get_initiative() once per initiative
    # internally (itself issuing 1 query for objective_ids + 5 mirror-table JOINs for
    # control_mappings), an N+1 shape research.md's own text initially set out to avoid.
    # Reusing it here anyway, rather than duplicating _linked_control_mappings' five-table
    # target_type dispatch a second time in this module: at this domain's stated scale (low
    # hundreds of initiatives), ~7 queries/initiative stays well within "completes within its
    # own interval" (plan.md's actual performance goal), and reusing already-correct, already-
    # tested logic is lower-risk than re-deriving the same dispatch table here for a query-count
    # win this domain's scale doesn't actually need.
    initiatives = (await sinit.list_initiatives(session)).items

    return StrategyExportSnapshot(
        themes=themes,
        objective_rows=objective_rows,
        initiatives=initiatives,
        capability_ids_by_objective=capability_ids_by_objective,
        value_stream_ids_by_objective=value_stream_ids_by_objective,
        design_ids_by_objective=design_ids_by_objective,
        application_ids_by_objective=application_ids_by_objective,
        control_ids_by_objective=control_ids_by_objective,
        depends_on_by_objective=depends_on_by_objective,
        blocks_by_objective=blocks_by_objective,
        initiative_ids_by_objective=initiative_ids_by_objective,
        objective_ids_by_initiative=objective_ids_by_initiative,
        progress_by_objective=progress_by_objective,
    )


# ── Reconciliation orchestration ─────────────────────────────────────────────


async def run_reconciliation_cycle(export_root: Path | str, session: AsyncSession) -> None:
    """One full reconciliation pass: read everything live, write every
    entity's file. Any failure is caught, logged, and swallowed (FR-006) --
    the background loop keeps running on schedule regardless of one bad
    cycle."""
    try:
        snapshot = await _fetch_all(session)
        root = Path(export_root) / "strategy"
        now = datetime.now(timezone.utc)

        for theme in snapshot.themes:
            _write_entity_file(
                root / "themes" / _safe_filename(theme.id), _serialize_theme(theme), now
            )

        for row in snapshot.objective_rows:
            progress = snapshot.progress_by_objective.get(row.id, [])
            progress_tuples: list[tuple[date, Decimal]] = [
                (p["as_of_date"], p["actual_value"]) for p in progress
            ]
            status = sstore.compute_status(
                row.status, row.target_value, row.direction, progress_tuples
            )
            status_reason = row.status_reason if status == "abandoned" else None
            _write_entity_file(
                root / "objectives" / _safe_filename(row.id),
                _serialize_objective(
                    row,
                    status=status,
                    status_reason=status_reason,
                    capability_ids=snapshot.capability_ids_by_objective.get(row.id, []),
                    value_stream_ids=snapshot.value_stream_ids_by_objective.get(row.id, []),
                    design_ids=snapshot.design_ids_by_objective.get(row.id, []),
                    application_ids=snapshot.application_ids_by_objective.get(row.id, []),
                    control_ids=snapshot.control_ids_by_objective.get(row.id, []),
                    depends_on_objective_ids=snapshot.depends_on_by_objective.get(row.id, []),
                    blocked_objective_ids=snapshot.blocks_by_objective.get(row.id, []),
                    initiative_ids=snapshot.initiative_ids_by_objective.get(row.id, []),
                    progress=progress,
                ),
                now,
            )

        for initiative in snapshot.initiatives:
            _write_entity_file(
                root / "initiatives" / _safe_filename(initiative.id),
                _serialize_initiative(initiative),
                now,
            )

        # Orphan cleanup (FR-004): every entity type here is a flat directory
        # of files (no nested subtree like ADP-SPEC-044's value-streams/), so
        # _cleanup_orphan_files alone is sufficient for all three.
        _cleanup_orphan_files(root / "themes", {t.id for t in snapshot.themes})
        _cleanup_orphan_files(
            root / "objectives", {row.id for row in snapshot.objective_rows}
        )
        _cleanup_orphan_files(
            root / "initiatives", {i.id for i in snapshot.initiatives}
        )
    except Exception:
        _logger.warning("strategy_export.cycle_failed", exc_info=True)


# ── Background task lifecycle ─────────────────────────────────────────────────
# Thin, domain-bound wrappers around adp.export.common's generic lifecycle --
# same shape as adp.export.business_arch's/application_arch's, so callers/
# tests don't need to pass a reconcile_fn themselves.


def start_background_sync(
    export_root: str | None,
    interval_seconds: float,
    session_factory: Callable[[], Any],
) -> asyncio.Task[None] | None:
    """Start the periodic reconciliation loop. A no-op (returns None, starts
    nothing, writes nothing) when `export_root` is falsy."""
    return common.start_background_sync(
        export_root,
        interval_seconds,
        session_factory,
        run_reconciliation_cycle,
        logger_name="adp.export.strategy",
    )


async def stop_background_sync(task: asyncio.Task[None] | None) -> None:
    """Cancel and await the background task started by start_background_sync.
    A no-op if `task` is None."""
    await common.stop_background_sync(task)
