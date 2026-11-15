"""Snapshot builder for capability-model analysis (938-capability-model-analysis, research R2).

A fixed number of queries per request, whatever the catalog size. Links are inner-joined to both
ends, so a dangling row (possible on SQLite, where foreign keys aren't enforced) never appears.
Risk and cost are queried ONLY when the caller may read them (research R3): gated data is never
loaded, rather than loaded and redacted.
"""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application import store as astore
from adp.application.cap_analysis import AppInfo, CapabilitySnapshot, Node, RiskInfo, TechNode
from adp.application.store import (
    _app_cap_realizations,
    _app_cap_tech_links,
    _app_caps,
    _application_risk,
    _applications,
    _biz_app_cap_links,
    _biz_caps,
    _tech_caps,
)


async def _nodes(table: sa.Table, session: AsyncSession) -> dict[str, Node]:
    rows = await session.execute(
        sa.select(table.c.id, table.c.name, table.c.level, table.c.parent_id)
    )
    return {r.id: Node(r.id, r.name, r.level or 0, r.parent_id) for r in rows}


async def _pairs(
    link: sa.Table,
    left: sa.Column,
    right: sa.Column,
    left_t: sa.Table,
    right_t: sa.Table,
    session: AsyncSession,
) -> dict[str, frozenset[str]]:
    q = sa.select(left, right).select_from(
        link.join(left_t, left == left_t.c.id).join(right_t, right == right_t.c.id)
    )
    out: dict[str, set[str]] = {}
    for a, b in (await session.execute(q)).all():
        out.setdefault(a, set()).add(b)
    return {k: frozenset(v) for k, v in out.items()}


async def build_snapshot(
    session: AsyncSession, *, risk_visible: bool, cost_visible: bool
) -> CapabilitySnapshot:
    business = await _nodes(_biz_caps, session)
    app_caps = await _nodes(_app_caps, session)
    tech_rows = await session.execute(
        sa.select(
            _tech_caps.c.id,
            _tech_caps.c.name,
            _tech_caps.c.level,
            _tech_caps.c.parent_id,
            _tech_caps.c.lifecycle_status,
            _tech_caps.c.end_of_life_date,
        )
    )
    technical = {
        r.id: TechNode(
            r.id, r.name, r.level, r.parent_id, r.lifecycle_status or "current", r.end_of_life_date
        )
        for r in tech_rows
    }
    biz_to_ac = await _pairs(
        _biz_app_cap_links,
        _biz_app_cap_links.c.business_capability_id,
        _biz_app_cap_links.c.app_capability_id,
        _biz_caps,
        _app_caps,
        session,
    )
    ac_to_tc = await _pairs(
        _app_cap_tech_links,
        _app_cap_tech_links.c.app_capability_id,
        _app_cap_tech_links.c.tech_cap_id,
        _app_caps,
        _tech_caps,
        session,
    )
    ac_to_apps = await _pairs(
        _app_cap_realizations,
        _app_cap_realizations.c.app_capability_id,
        _app_cap_realizations.c.app_id,
        _app_caps,
        _applications,
        session,
    )
    app_rows = await session.execute(
        sa.select(
            _applications.c.id,
            _applications.c.name,
            _applications.c.lifecycle_status,
            _applications.c.health_score,
        )
    )
    apps = {
        r.id: AppInfo(r.id, r.name, r.lifecycle_status or "active", r.health_score)
        for r in app_rows
    }

    risk: dict[str, RiskInfo] = {}
    if risk_visible:
        risk_rows = await session.execute(
            sa.select(
                _application_risk.c.app_id,
                _application_risk.c.security_posture,
                _application_risk.c.vulnerability_status,
                _application_risk.c.end_of_support_date,
            )
        )
        risk = {
            r.app_id: RiskInfo(r.security_posture, r.vulnerability_status, r.end_of_support_date)
            for r in risk_rows
        }
    cost: dict[str, Decimal] = await astore.list_all_costs(session) if cost_visible else {}

    return CapabilitySnapshot(
        business=business,
        app_caps=app_caps,
        technical=technical,
        biz_to_ac=biz_to_ac,
        ac_to_tc=ac_to_tc,
        ac_to_apps=ac_to_apps,
        apps=apps,
        risk=risk,
        cost=cost,
        risk_visible=risk_visible,
        cost_visible=cost_visible,
    )
