"""Continuous export of the Application registry to versioned JSON files
(ADP-SPEC-045 / ADP-81p.2).

Postgres remains the interactive source of truth (ART-II); this module is a
read-only, best-effort background projection of applications, technical
capabilities, transformation initiatives, application-to-application
integrations, and (per Clarification Q1 in spec.md) an application's risk,
cost, and governance records unredacted, onto the filesystem. See
specs/045-application-export/ for the full spec, research, and data model.

Sibling to adp.export.business_arch (ADP-SPEC-044); reuses the shared,
domain-agnostic mechanics in adp.export.common (research.md Decision 5)
rather than re-implementing atomic writes, content-diffing, orphan cleanup,
or the background-loop lifecycle a second time.
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

from adp.application import store as astore
from adp.application.models import (
    Application,
    ApplicationCost,
    ApplicationGovernance,
    ApplicationIntegration,
    ApplicationQualityMetric,
    ApplicationRisk,
    TechnicalCapability,
    TransformationInitiative,
)
from adp.export import common
from adp.export.common import (
    _cleanup_orphan_files,
    _safe_filename,
    _write_entity_file,
)

_logger = logging.getLogger("adp.export.application_arch")

# ── Serialization (data-model.md §2) ─────────────────────────────────────────
# Pure functions: no I/O, no `exported_at` (stamped separately at write time
# by adp.export.common._write_entity_file, so that field alone never makes an
# unchanged entity look "changed" to the content-comparison, research.md
# Decision 2).


def _serialize_risk(risk: ApplicationRisk | None) -> dict[str, Any]:
    """An application's risk & compliance record, or the all-unset shape
    (never omitted) when it has none (FR-018)."""
    if risk is None:
        risk = ApplicationRisk()
    return {
        "security_posture": risk.security_posture,
        "vulnerability_status": risk.vulnerability_status,
        "data_classification": risk.data_classification,
        "regulatory_tags": list(risk.regulatory_tags),
        "dr_bc_status": risk.dr_bc_status,
        "end_of_life_date": risk.end_of_life_date.isoformat() if risk.end_of_life_date else None,
        "end_of_support_date": (
            risk.end_of_support_date.isoformat() if risk.end_of_support_date else None
        ),
    }


def _serialize_cost(cost: ApplicationCost | None) -> dict[str, Any]:
    """An application's cost/TCO record, or the all-zero shape (never
    omitted) when it has none (FR-018). Decimal amounts are always rendered
    as JSON strings -- money is Decimal-precision throughout this platform,
    never a binary float."""
    if cost is None:
        cost = ApplicationCost()
    from adp.application.models import TCO_BUCKET_NAMES

    buckets = {
        name: {
            "one_time": str(getattr(cost, name).one_time),
            "annual": str(getattr(cost, name).annual),
        }
        for name in TCO_BUCKET_NAMES
    }
    return {"currency": cost.currency, "horizon_years": cost.horizon_years, **buckets}


def _serialize_governance(governance: ApplicationGovernance | None) -> dict[str, Any]:
    """An application's ownership & governance record, or the all-unset
    shape (never omitted) when it has none (FR-018)."""
    if governance is None:
        governance = ApplicationGovernance()
    return {
        "contract_terms": governance.contract_terms,
        "renewal_date": governance.renewal_date.isoformat() if governance.renewal_date else None,
        "sla": governance.sla,
        "business_sponsor": governance.business_sponsor,
        "it_owner": governance.it_owner,
        "decision_rights": governance.decision_rights,
    }


def _serialize_quality(quality: ApplicationQualityMetric | None) -> dict[str, Any]:
    """An application's quality & performance signals, or the all-unset
    shape (never omitted) when it has none."""
    if quality is None:
        quality = ApplicationQualityMetric()
    return {
        "uptime_pct": str(quality.uptime_pct) if quality.uptime_pct is not None else None,
        "incidents_ytd": quality.incidents_ytd,
        "satisfaction_score": quality.satisfaction_score,
        "perf_note": quality.perf_note,
        "ticket_volume_30d": quality.ticket_volume_30d,
    }


def _serialize_application(
    app: Application,
    *,
    risk: ApplicationRisk | None,
    cost: ApplicationCost | None,
    governance: ApplicationGovernance | None,
    quality: ApplicationQualityMetric | None,
    linked_business_capabilities: list[dict[str, Any]],
    linked_technical_capabilities: list[dict[str, Any]],
    linked_value_stream_stages: list[dict[str, Any]],
    domain_integrations: list[dict[str, Any]],
    initiative_links: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": app.id,
        "name": app.name,
        "description": app.description,
        "vendor": app.vendor,
        "primary_owner": app.primary_owner,
        "time_classification": app.time_classification,
        "r_strategy": app.r_strategy,
        "pace_layer": app.pace_layer,
        "health_score": app.health_score,
        "business_value": app.business_value,
        "business_criticality": app.business_criticality,
        "owning_business_unit": app.owning_business_unit,
        "business_owner": app.business_owner,
        "technical_owner": app.technical_owner,
        "lifecycle_status": app.lifecycle_status,
        "hosting_model": app.hosting_model,
        "application_type": app.application_type,
        "architecture_pattern": app.architecture_pattern,
        "tech_debt_flags": list(app.tech_debt_flags),
        "risk": _serialize_risk(risk),
        "cost": _serialize_cost(cost),
        "governance": _serialize_governance(governance),
        "quality": _serialize_quality(quality),
        "linked_business_capabilities": linked_business_capabilities,
        "linked_technical_capabilities": linked_technical_capabilities,
        "linked_value_stream_stages": linked_value_stream_stages,
        "domain_integrations": domain_integrations,
        "initiative_links": initiative_links,
    }


def _serialize_technical_capability(tc: TechnicalCapability) -> dict[str, Any]:
    return {
        "id": tc.id,
        "name": tc.name,
        "description": tc.description,
        "parent_id": tc.parent_id,
        "level": tc.level,
        "strategic_relevance": tc.strategic_relevance,
    }


def _serialize_initiative(
    initiative: TransformationInitiative, *, members: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "id": initiative.id,
        "name": initiative.name,
        "description": initiative.description,
        "target_date": initiative.target_date.isoformat() if initiative.target_date else None,
        "members": members,
    }


def _serialize_integration(intg: ApplicationIntegration) -> dict[str, Any]:
    return {
        "id": intg.id,
        "source_app_id": intg.source_app_id,
        "source_app_name": intg.source_app_name,
        "target_app_id": intg.target_app_id,
        "target_app_name": intg.target_app_name,
        "integration_type": intg.integration_type,
        "description": intg.description,
    }


# ── Bulk read (research.md Decision 4 — small fixed query count; reuses
# adp.application.store's existing bulk-list functions where they exist,
# direct Table queries where they don't) ─────────────────────────────────────


@dataclass(frozen=True)
class ApplicationArchSnapshot:
    applications: list[Application]
    technical_capabilities: list[TechnicalCapability]
    initiatives: list[TransformationInitiative]
    integrations: list[ApplicationIntegration]
    risk_by_app: dict[str, ApplicationRisk] = field(default_factory=dict)
    cost_by_app: dict[str, ApplicationCost] = field(default_factory=dict)
    governance_by_app: dict[str, ApplicationGovernance] = field(default_factory=dict)
    quality_by_app: dict[str, ApplicationQualityMetric] = field(default_factory=dict)
    capability_links_by_app: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    tech_cap_links_by_app: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    stage_links_by_app: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    domain_integrations_by_app: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    initiative_links_by_app: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # Reverse view of initiative_links_by_app, keyed by initiative_id instead
    # of app_id -- both directions come from the same query (data-model.md §2.3).
    members_by_initiative: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


async def _fetch_all(session: AsyncSession) -> ApplicationArchSnapshot:
    """One reconciliation cycle's complete live snapshot -- a small, fixed
    number of queries (not one per application), reusing
    adp.application.store's existing bulk-list functions where they exist
    and direct Table queries (joined for display names) where they don't
    (research.md Decision 4)."""
    apps_resp = await astore.list_applications(session)
    tech_caps_resp = await astore.list_technical_capabilities(session)
    initiatives_resp = await astore.list_initiatives(session)
    integrations_resp = await astore.list_integrations(None, session)

    risk_by_app: dict[str, ApplicationRisk] = {}
    for row in (await session.execute(sa.select(astore._application_risk))).mappings().all():
        risk_by_app[row["app_id"]] = astore._row_to_risk(row)

    cost_by_app: dict[str, ApplicationCost] = {}
    for row in (await session.execute(sa.select(astore._application_cost))).mappings().all():
        cost_by_app[row["app_id"]] = astore._row_to_cost(row)

    governance_by_app: dict[str, ApplicationGovernance] = {}
    for row in (await session.execute(sa.select(astore._application_contracts))).mappings().all():
        governance_by_app[row["app_id"]] = astore._row_to_governance(row)

    quality_by_app: dict[str, ApplicationQualityMetric] = {}
    for row in (
        await session.execute(sa.select(astore._application_quality_metrics))
    ).mappings().all():
        quality_by_app[row["app_id"]] = astore._row_to_quality(row)

    capability_links_by_app: dict[str, list[dict[str, Any]]] = {}
    cap_link_stmt = sa.select(
        astore._app_cap_links.c.app_id,
        astore._app_cap_links.c.capability_id,
        astore._biz_caps.c.name.label("capability_name"),
        astore._app_cap_links.c.fit_score,
    ).select_from(
        astore._app_cap_links.join(
            astore._biz_caps, astore._biz_caps.c.id == astore._app_cap_links.c.capability_id
        )
    )
    for row in (await session.execute(cap_link_stmt)).mappings().all():
        capability_links_by_app.setdefault(row["app_id"], []).append({
            "capability_id": row["capability_id"],
            "capability_name": row["capability_name"],
            "fit_score": row["fit_score"],
        })

    tech_cap_links_by_app: dict[str, list[dict[str, Any]]] = {}
    tc_link_stmt = sa.select(
        astore._app_tech_cap_links.c.app_id,
        astore._app_tech_cap_links.c.tech_cap_id,
        astore._tech_caps.c.name.label("tech_cap_name"),
        astore._app_tech_cap_links.c.usage_type,
    ).select_from(
        astore._app_tech_cap_links.join(
            astore._tech_caps, astore._tech_caps.c.id == astore._app_tech_cap_links.c.tech_cap_id
        )
    )
    for row in (await session.execute(tc_link_stmt)).mappings().all():
        tech_cap_links_by_app.setdefault(row["app_id"], []).append({
            "tech_cap_id": row["tech_cap_id"],
            "tech_cap_name": row["tech_cap_name"],
            "usage_type": row["usage_type"],
        })

    stage_links_by_app: dict[str, list[dict[str, Any]]] = {}
    stage_link_stmt = sa.select(
        astore._app_stage_links.c.app_id,
        astore._app_stage_links.c.stage_id,
        astore._stages.c.name.label("stage_name"),
    ).select_from(
        astore._app_stage_links.join(
            astore._stages, astore._stages.c.id == astore._app_stage_links.c.stage_id
        )
    )
    for row in (await session.execute(stage_link_stmt)).mappings().all():
        stage_links_by_app.setdefault(row["app_id"], []).append({
            "stage_id": row["stage_id"],
            "stage_name": row["stage_name"],
        })

    domain_integrations_by_app: dict[str, list[dict[str, Any]]] = {}
    domain_stmt = sa.select(
        astore._app_domain_integrations.c.id,
        astore._app_domain_integrations.c.app_id,
        astore._app_domain_integrations.c.domain_id,
        astore._domains.c.name.label("domain_name"),
        astore._app_domain_integrations.c.integration_type,
        astore._app_domain_integrations.c.direction,
    ).select_from(
        astore._app_domain_integrations.outerjoin(
            astore._domains, astore._domains.c.id == astore._app_domain_integrations.c.domain_id
        )
    )
    for row in (await session.execute(domain_stmt)).mappings().all():
        domain_integrations_by_app.setdefault(row["app_id"], []).append({
            "id": row["id"],
            "domain_id": row["domain_id"],
            "domain_name": row["domain_name"],
            "integration_type": row["integration_type"],
            "direction": row["direction"],
        })

    initiative_links_by_app: dict[str, list[dict[str, Any]]] = {}
    members_by_initiative: dict[str, list[dict[str, Any]]] = {
        ti.id: [] for ti in initiatives_resp.items
    }
    init_link_stmt = sa.select(
        astore._app_initiative_links.c.app_id,
        astore._applications.c.name.label("app_name"),
        astore._app_initiative_links.c.initiative_id,
        astore._transformation_initiatives.c.name.label("initiative_name"),
        astore._app_initiative_links.c.planned_disposition,
    ).select_from(
        astore._app_initiative_links.join(
            astore._applications, astore._applications.c.id == astore._app_initiative_links.c.app_id
        ).join(
            astore._transformation_initiatives,
            astore._transformation_initiatives.c.id == astore._app_initiative_links.c.initiative_id,
        )
    )
    for row in (await session.execute(init_link_stmt)).mappings().all():
        initiative_links_by_app.setdefault(row["app_id"], []).append({
            "initiative_id": row["initiative_id"],
            "initiative_name": row["initiative_name"],
            "planned_disposition": row["planned_disposition"],
        })
        members_by_initiative.setdefault(row["initiative_id"], []).append({
            "app_id": row["app_id"],
            "app_name": row["app_name"],
            "planned_disposition": row["planned_disposition"],
        })

    return ApplicationArchSnapshot(
        applications=apps_resp.items,
        technical_capabilities=tech_caps_resp.items,
        initiatives=initiatives_resp.items,
        integrations=integrations_resp.items,
        risk_by_app=risk_by_app,
        cost_by_app=cost_by_app,
        governance_by_app=governance_by_app,
        quality_by_app=quality_by_app,
        capability_links_by_app=capability_links_by_app,
        tech_cap_links_by_app=tech_cap_links_by_app,
        stage_links_by_app=stage_links_by_app,
        domain_integrations_by_app=domain_integrations_by_app,
        initiative_links_by_app=initiative_links_by_app,
        members_by_initiative=members_by_initiative,
    )


# ── Reconciliation orchestration ─────────────────────────────────────────────


async def run_reconciliation_cycle(export_root: Path | str, session: AsyncSession) -> None:
    """One full reconciliation pass: read everything live, write every
    entity's file. Any failure is caught, logged, and swallowed (FR-006) --
    the background loop keeps running on schedule regardless of one bad
    cycle."""
    try:
        snapshot = await _fetch_all(session)
        root = Path(export_root) / "applications"
        now = datetime.now(timezone.utc)

        for app in snapshot.applications:
            _write_entity_file(
                root / "applications" / _safe_filename(app.id),
                _serialize_application(
                    app,
                    risk=snapshot.risk_by_app.get(app.id),
                    cost=snapshot.cost_by_app.get(app.id),
                    governance=snapshot.governance_by_app.get(app.id),
                    quality=snapshot.quality_by_app.get(app.id),
                    linked_business_capabilities=snapshot.capability_links_by_app.get(app.id, []),
                    linked_technical_capabilities=snapshot.tech_cap_links_by_app.get(app.id, []),
                    linked_value_stream_stages=snapshot.stage_links_by_app.get(app.id, []),
                    domain_integrations=snapshot.domain_integrations_by_app.get(app.id, []),
                    initiative_links=snapshot.initiative_links_by_app.get(app.id, []),
                ),
                now,
            )
        for tc in snapshot.technical_capabilities:
            _write_entity_file(
                root / "technical-capabilities" / _safe_filename(tc.id),
                _serialize_technical_capability(tc),
                now,
            )
        for ti in snapshot.initiatives:
            _write_entity_file(
                root / "transformation-initiatives" / _safe_filename(ti.id),
                _serialize_initiative(
                    ti, members=snapshot.members_by_initiative.get(ti.id, [])
                ),
                now,
            )
        for intg in snapshot.integrations:
            _write_entity_file(
                root / "integrations" / _safe_filename(intg.id),
                _serialize_integration(intg),
                now,
            )

        # Orphan cleanup (FR-004): every entity type here is a flat directory
        # of files (no nested subtree like ADP-SPEC-044's value-streams/), so
        # _cleanup_orphan_files alone is sufficient for all four.
        _cleanup_orphan_files(
            root / "applications", {a.id for a in snapshot.applications}
        )
        _cleanup_orphan_files(
            root / "technical-capabilities",
            {tc.id for tc in snapshot.technical_capabilities},
        )
        _cleanup_orphan_files(
            root / "transformation-initiatives", {ti.id for ti in snapshot.initiatives}
        )
        _cleanup_orphan_files(
            root / "integrations", {intg.id for intg in snapshot.integrations}
        )
    except Exception:
        _logger.warning("application_arch_export.cycle_failed", exc_info=True)


# ── Background task lifecycle ─────────────────────────────────────────────────
# Thin, domain-bound wrappers around adp.export.common's generic lifecycle --
# same shape as adp.export.business_arch's, so callers/tests don't need to
# pass a reconcile_fn themselves.

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
        logger_name="adp.export.application_arch",
    )


async def stop_background_sync(task: asyncio.Task[None] | None) -> None:
    """Cancel and await the background task started by start_background_sync.
    A no-op if `task` is None."""
    await common.stop_background_sync(task)
