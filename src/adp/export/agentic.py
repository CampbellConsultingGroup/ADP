"""Continuous export of the agent registry to versioned JSON files (933-agent-registry, ADP-hii).

Writes `<root>/agentic/agents/<agent_id>.json` -- every agent's fields plus the solutions it
belongs to (`solutions: [{app_id, role, position}]`). Cost estimates are exported unredacted,
matching adp.export.application_arch's documented treatment of application cost (research.md D8).
944-agent-traceability adds `automates` (capabilities / stages / activities, id and name) and
`compliance_mappings` (control, framework, status). A fixed six queries per cycle -- no N+1.
Reuses adp.export.common verbatim: atomic,
content-diff-aware writes, orphan cleanup, opt-in background loop sharing
ADP_BUSINESS_ARCH_EXPORT_ROOT/_INTERVAL_SECONDS with the other export domains.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.agentic import store as agstore
from adp.compliance import store as cstore
from adp.export import common
from adp.export.common import _cleanup_orphan_files, _safe_filename, _write_entity_file

_logger = logging.getLogger("adp.export.agentic")


_EMPTY_AUTOMATES: dict[str, list[dict[str, str]]] = {
    "capabilities": [], "stages": [], "activities": [],
}


def _serialize_agent(
    row: Any,
    solutions: list[dict[str, Any]],
    automates: dict[str, list[dict[str, str]]] | None = None,
    compliance_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure: one agent row + its memberships, links and mappings → the exported JSON document."""
    cost = row.est_cost_per_run
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "owner": row.owner,
        "lifecycle_status": row.lifecycle_status,
        "model_provider": row.model_provider,
        "model_id": row.model_id,
        "model_version": row.model_version,
        "framework": row.framework,
        "prompt_ref": row.prompt_ref,
        "autonomy_level": row.autonomy_level,
        "human_approval": row.human_approval,
        "data_classification_max": row.data_classification_max,
        "a2a_card_url": row.a2a_card_url,
        "est_cost_per_run": str(cost) if cost is not None else None,
        "runs_per_month": row.runs_per_month,
        "external_registry_ref": row.external_registry_ref,
        "solutions": sorted(solutions, key=lambda s: s["app_id"]),
        "automates": {
            kind: sorted(items, key=lambda t: t["id"])
            for kind, items in (automates or _EMPTY_AUTOMATES).items()
        },
        "compliance_mappings": sorted(
            compliance_mappings or [], key=lambda m: m["control_id"]
        ),
    }


async def _fetch_automates(session: AsyncSession) -> dict[str, dict[str, list[dict[str, str]]]]:
    """agent_id -> {capabilities, stages, activities}: three queries, inner-joined to the target
    mirrors so a dangling link never surfaces."""
    out: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: {"capabilities": [], "stages": [], "activities": []}
    )
    for key, (table, col, mirror) in (
        ("capabilities", agstore._LINKS["capability"]),
        ("stages", agstore._LINKS["stage"]),
        ("activities", agstore._LINKS["activity"]),
    ):
        result = await session.execute(
            sa.select(table.c.agent_id, mirror.c.id, mirror.c.name).select_from(
                table.join(mirror, mirror.c.id == table.c[col])
            )
        )
        for r in result:
            out[r.agent_id][key].append({"id": r.id, "name": r.name})
    return out


async def _fetch_compliance(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """agent_id -> its control mappings with control code and framework: one query."""
    m, c, f = cstore._control_agent_mapping, cstore._controls, cstore._frameworks
    result = await session.execute(
        sa.select(
            m.c.agent_id, m.c.control_id, m.c.compliance_status,
            c.c.code, c.c.framework_id, f.c.name.label("framework_name"),
        ).select_from(m.join(c, c.c.id == m.c.control_id).join(f, f.c.id == c.c.framework_id))
    )
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in result:
        out[r.agent_id].append(
            {
                "control_id": r.control_id,
                "control_code": r.code,
                "framework_id": r.framework_id,
                "framework_name": r.framework_name,
                "compliance_status": r.compliance_status,
            }
        )
    return out


async def run_reconciliation_cycle(export_root: Path | str, session: AsyncSession) -> None:
    """One full pass: write every agent's file, remove files for deleted agents. Failures are
    logged and swallowed so the background loop keeps its schedule."""
    try:
        agents = (await session.execute(sa.select(agstore._agents))).all()
        memberships: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for m in await session.execute(sa.select(agstore._solution_agents)):
            memberships[m.agent_id].append(
                {"app_id": m.solution_app_id, "role": m.role, "position": m.position}
            )

        automates = await _fetch_automates(session)
        compliance = await _fetch_compliance(session)

        root = Path(export_root) / "agentic" / "agents"
        now = datetime.now(timezone.utc)
        for row in agents:
            doc = _serialize_agent(
                row, memberships[row.id], automates.get(row.id), compliance.get(row.id)
            )
            _write_entity_file(root / _safe_filename(row.id), doc, now)
        _cleanup_orphan_files(root, {row.id for row in agents})
    except Exception:
        _logger.warning("agentic_export.cycle_failed", exc_info=True)


def start_background_sync(
    export_root: str | None,
    interval_seconds: float,
    session_factory: Callable[[], Any],
) -> asyncio.Task[None] | None:
    """Start the periodic reconciliation loop; a no-op when `export_root` is falsy."""
    return common.start_background_sync(
        export_root,
        interval_seconds,
        session_factory,
        run_reconciliation_cycle,
        logger_name="adp.export.agentic",
    )


async def stop_background_sync(task: asyncio.Task[None] | None) -> None:
    await common.stop_background_sync(task)
