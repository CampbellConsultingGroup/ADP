"""Build the per-caller portfolio snapshot from the live registries (936 FR-005–FR-007, D3).

A fixed number of queries, independent of estate size (no N+1): one per registry table, plus
the gated tables only when the caller may read them. Reads go through narrow read-only mirror
tables on ``adp.patterns.store._metadata`` (research.md D1); the one exception is application TCO,
which reuses ``adp.application.store.list_all_costs`` rather than duplicating its eight-bucket
formula (the ``adp.portfolio`` heat-map precedent, 919).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from adp.patterns.snapshot import (
    COST_FIELDS,
    GOVERNANCE_FIELDS,
    RISK_FIELDS,
    Element,
    PortfolioSnapshot,
    derive_application_domains,
)
from adp.patterns.store import _applications_mirror, _metadata

_TEXT_LIST = sa.JSON().with_variant(ARRAY(sa.Text()), "postgresql")

# ── Read-only registry mirrors ─────────────────────────────────────────────────────────
_integrations = sa.Table(
    "application_integrations",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("source_app_id", sa.String(36)),
    sa.Column("target_app_id", sa.String(36)),
    sa.Column("integration_type", sa.Text()),
    sa.Column("description", sa.Text()),
)
_cap_links = sa.Table(
    "application_capability_links",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("capability_id", sa.String(36), primary_key=True),
)
_tcap_links = sa.Table(
    "application_tech_cap_links",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("tech_cap_id", sa.String(36), primary_key=True),
    sa.Column("usage_type", sa.Text()),
)
_capabilities = sa.Table(
    "business_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255)),
    sa.Column("level", sa.Integer()),
    sa.Column("parent_id", sa.String(36)),
    sa.Column("domain_id", sa.String(36)),
    sa.Column("strategic_relevance", sa.SmallInteger()),
    sa.Column("maturity_level", sa.SmallInteger()),
)
_domains = sa.Table(
    "business_domains",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255)),
    sa.Column("classification", sa.Text()),
    sa.Column("risk_flags", _TEXT_LIST),
)
_value_streams = sa.Table(
    "value_streams",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255)),
)
_stages = sa.Table(
    "value_stream_stages",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("value_stream_id", sa.String(36)),
    sa.Column("position", sa.Integer()),
)
_tech_caps = sa.Table(
    "technical_capabilities",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255)),
    sa.Column("level", sa.Integer()),
    sa.Column("parent_id", sa.String(36)),
)
_agents = sa.Table(
    "agents",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255)),
    sa.Column("lifecycle_status", sa.Text()),
    sa.Column("autonomy_level", sa.SmallInteger()),
    sa.Column("human_approval", sa.Text()),
    sa.Column("data_classification_max", sa.Text()),
)
_solution_agents = sa.Table(
    "solution_agents",
    _metadata,
    sa.Column("solution_app_id", sa.String(36), primary_key=True),
    sa.Column("agent_id", sa.String(36), primary_key=True),
)
_risk = sa.Table(
    "application_risk",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    *(
        sa.Column(f, sa.Text())
        for f in ("security_posture", "vulnerability_status", "data_classification", "dr_bc_status")
    ),
    sa.Column("end_of_life_date", sa.Date()),
    sa.Column("end_of_support_date", sa.Date()),
)
_contracts = sa.Table(
    "application_contracts",
    _metadata,
    sa.Column("app_id", sa.String(36), primary_key=True),
    sa.Column("renewal_date", sa.Date()),
    sa.Column("sla", sa.Text()),
)

# Element tables by type, for the polymorphic pin existence check (adoptions.py).
ELEMENT_TABLES: dict[str, sa.Table] = {
    "application": _applications_mirror,
    "integration": _integrations,
    "business_capability": _capabilities,
    "business_domain": _domains,
    "value_stream": _value_streams,
    "technical_capability": _tech_caps,
    "agent": _agents,
}

CostLoader = Callable[[AsyncSession], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class SnapshotPermissions:
    """Which gated application attribute groups the caller may read (FR-006)."""

    risk: bool = False
    cost: bool = False
    governance: bool = False

    @property
    def unavailable_fields(self) -> frozenset[str]:
        out: set[str] = set()
        if not self.risk:
            out |= RISK_FIELDS
        if not self.cost:
            out |= COST_FIELDS
        if not self.governance:
            out |= GOVERNANCE_FIELDS
        return frozenset(out)


def _plain(value: Any) -> Any:
    """CEL-friendly scalars: ISO dates, floats for decimals."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


async def _default_cost_loader(session: AsyncSession) -> dict[str, Any]:
    from adp.application.store import list_all_costs

    return await list_all_costs(session)


async def build_snapshot(
    session: AsyncSession,
    permissions: SnapshotPermissions,
    *,
    cost_loader: CostLoader | None = None,
) -> PortfolioSnapshot:
    """The whole portfolio as plain element maps, with gated attributes only where permitted."""

    async def rows(stmt: Any) -> list[Any]:
        return list((await session.execute(stmt)).all())

    a = _applications_mirror
    apps: dict[str, Element] = {}
    for r in await rows(sa.select(a)):
        apps[r.id] = {
            "id": r.id,
            "name": r.name,
            "lifecycle_status": r.lifecycle_status,
            "application_type": r.application_type,
            "time_classification": r.time_classification,
            "r_strategy": r.r_strategy,
            "pace_layer": r.pace_layer,
            "hosting_model": r.hosting_model,
            "architecture_pattern": r.architecture_pattern,
            "business_criticality": r.business_criticality,
            "health_score": r.health_score,
            "tech_debt_flags": list(r.tech_debt_flags or []),
            "capability_ids": [],
            "technical_capability_ids": [],
        }
    for r in await rows(sa.select(_cap_links)):
        if r.app_id in apps:
            apps[r.app_id]["capability_ids"].append(r.capability_id)
    realizes: set[tuple[str, str]] = set()
    for r in await rows(sa.select(_tcap_links)):
        if r.app_id in apps:
            apps[r.app_id]["technical_capability_ids"].append(r.tech_cap_id)
            if r.usage_type == "provides":
                realizes.add((r.app_id, r.tech_cap_id))
    for app in apps.values():
        app["capability_ids"].sort()
        app["technical_capability_ids"].sort()

    if permissions.risk:
        for r in await rows(sa.select(_risk)):
            if r.app_id in apps:
                apps[r.app_id].update({f: _plain(getattr(r, f)) for f in sorted(RISK_FIELDS)})
        for app in apps.values():
            for f in RISK_FIELDS:
                app.setdefault(f, None)
    if permissions.cost:
        costs = await (cost_loader or _default_cost_loader)(session)
        for aid, app in apps.items():
            app["tco"] = _plain(costs.get(aid))
    if permissions.governance:
        for r in await rows(sa.select(_contracts)):
            if r.app_id in apps:
                apps[r.app_id].update({"renewal_date": _plain(r.renewal_date), "sla": r.sla})
        for app in apps.values():
            app.setdefault("renewal_date", None)
            app.setdefault("sla", None)

    caps = {
        r.id: {
            "id": r.id,
            "name": r.name,
            "level": r.level,
            "parent_id": r.parent_id,
            "domain_id": r.domain_id,
            "strategic_relevance": r.strategic_relevance,
            "maturity_level": r.maturity_level,
        }
        for r in await rows(sa.select(_capabilities))
    }
    derive_application_domains(apps, caps)

    domains = {
        r.id: {
            "id": r.id,
            "name": r.name,
            "classification": r.classification,
            "risk_flags": list(r.risk_flags or []),
        }
        for r in await rows(sa.select(_domains))
    }
    stage_ids: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for r in await rows(sa.select(_stages)):
        stage_ids[r.value_stream_id].append((r.position or 0, r.id))
    streams = {
        r.id: {
            "id": r.id,
            "name": r.name,
            "stage_ids": [sid for _, sid in sorted(stage_ids.get(r.id, []))],
        }
        for r in await rows(sa.select(_value_streams))
    }
    tcaps = {
        r.id: {"id": r.id, "name": r.name, "level": r.level, "parent_id": r.parent_id}
        for r in await rows(sa.select(_tech_caps))
    }
    solutions: dict[str, list[str]] = defaultdict(list)
    for r in await rows(sa.select(_solution_agents)):
        solutions[r.agent_id].append(r.solution_app_id)
    agents = {
        r.id: {
            "id": r.id,
            "name": r.name,
            "lifecycle_status": r.lifecycle_status,
            "autonomy_level": r.autonomy_level,
            "human_approval": r.human_approval,
            "data_classification_max": r.data_classification_max,
            "solution_ids": sorted(solutions.get(r.id, [])),
        }
        for r in await rows(sa.select(_agents))
    }
    raw_integrations = {
        r.id: {
            "id": r.id,
            "source_id": r.source_app_id,
            "target_id": r.target_app_id,
            "integration_type": r.integration_type,
            "description": r.description,
        }
        for r in await rows(sa.select(_integrations))
    }
    return PortfolioSnapshot.from_parts(
        applications=apps,
        raw_integrations=raw_integrations,
        business_capabilities=caps,
        business_domains=domains,
        technical_capabilities=tcaps,
        value_streams=streams,
        agents=agents,
        realizes_pairs=realizes,
        unavailable_fields=permissions.unavailable_fields,
    )
