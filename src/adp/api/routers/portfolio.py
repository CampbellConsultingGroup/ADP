"""Portfolio Analysis API — ADP-SPEC-031.

Read-only endpoints for cross-portfolio aggregation. All queries use indexed
columns (element_technology_tags B-tree indexes, designs.lifecycle_status index).
No new DB tables or migrations required.

Endpoints:
  GET /api/v1/portfolio/summary                   — portfolio health summary header
  GET /api/v1/portfolio/applications-heatmap      — applications heat map (919-insights-dashboard)
  GET /api/v1/portfolio/application-capability-groups — app-capability links, bulk (ADP-8xo)

ADP-704: /technologies, /designs, and /search (the old design-technology-landscape trio) were
retired here. ADP-8xo's Application Portfolio pivot deleted every UI hook/component that called
them (usePortfolioTechnologies/usePortfolioDesigns/usePortfolioSearch,
TechnologyLandscape.tsx/PortfolioDesignList.tsx/DependencySearch.tsx); the endpoints themselves
were deliberately left in place at the time (Phase-C-style, mirroring the ADP-914.9
C4Canvas-retirement precedent: prove the replacement first, retire old surface only after). No
UI dependency resurfaced in the time since (re-confirmed via a fresh grep before removing), and no
request for a standalone technology/lifecycle browser screen materialized either, so this is a
straight deletion, not a re-home.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.deps import get_kb_session
from adp.application.models import ApplicationCapabilityLink
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


# ── Response models ────────────────────────────────────────────────────────────

class PortfolioSummaryResponse(BaseModel):
    total_designs: int
    by_status: dict[str, int]
    overdue_review_count: int


# 919-insights-dashboard: applications heat map.
class ApplicationHeatmapEntry(BaseModel):
    id: str
    name: str
    health_score: int | None
    business_criticality: int | None
    time_classification: str | None
    # Always None when the caller lacks READ_APPLICATION_COST, regardless of whether the
    # application actually has a cost record -- see ApplicationHeatmapResponse.cost_permitted.
    cost: Decimal | None


class ApplicationHeatmapResponse(BaseModel):
    items: list[ApplicationHeatmapEntry]
    cost_permitted: bool


# ADP-8xo: Application Portfolio pivot, business-capability grouping dimension.
class ApplicationCapabilityGroupsResponse(BaseModel):
    items: list[ApplicationCapabilityLink]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    session: AsyncSession = Depends(get_kb_session),
) -> PortfolioSummaryResponse:
    """Portfolio health summary: counts by lifecycle status and overdue reviews."""
    status_result = await session.execute(
        sa.text(
            """
            SELECT lifecycle_status, COUNT(*) AS cnt
            FROM designs
            GROUP BY lifecycle_status
            """
        )
    )
    status_rows = status_result.fetchall()

    overdue_result = await session.execute(
        sa.text(
            """
            SELECT COUNT(*) AS overdue_count
            FROM designs
            WHERE review_due IS NOT NULL
              AND review_due < NOW()
            """
        )
    )
    overdue_row = overdue_result.fetchone()

    by_status = {r.lifecycle_status: r.cnt for r in status_rows}
    total = sum(by_status.values())
    overdue_count = overdue_row.overdue_count if overdue_row else 0

    return PortfolioSummaryResponse(
        total_designs=total,
        by_status=by_status,
        overdue_review_count=overdue_count,
    )


@router.get("/applications-heatmap", response_model=ApplicationHeatmapResponse)
async def get_applications_heatmap(
    user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_kb_session),
) -> ApplicationHeatmapResponse:
    """Every application as one heat-map cell (919-insights-dashboard, FR-001).

    No route-level permission gate -- health_score/business_criticality/
    time_classification are already open reads today (Ground-Truth Correction 3). The cost
    dimension is checked inline instead (research.md Decision 2): the cost query only runs,
    and cost values only populate, when the caller holds READ_APPLICATION_COST -- mirroring
    adp.chat.tools.get_application_cost's own inline-check pattern rather than gating the
    whole endpoint and blocking the three open dimensions for a cost-denied caller.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT id, name, health_score, business_criticality, time_classification
            FROM applications
            ORDER BY name
            """
        )
    )
    rows = result.mappings().all()

    cost_permitted = is_permitted(user.role, ActionType.READ_APPLICATION_COST)
    cost_by_app: dict[str, Decimal] = {}
    if cost_permitted:
        from adp.application import store as astore

        cost_by_app = await astore.list_all_costs(session)

    items = [
        ApplicationHeatmapEntry(
            id=r["id"],
            name=r["name"],
            health_score=r["health_score"],
            business_criticality=r["business_criticality"],
            time_classification=r["time_classification"],
            cost=cost_by_app.get(r["id"]) if cost_permitted else None,
        )
        for r in rows
    ]
    return ApplicationHeatmapResponse(items=items, cost_permitted=cost_permitted)


@router.get("/application-capability-groups", response_model=ApplicationCapabilityGroupsResponse)
async def get_application_capability_groups(
    session: AsyncSession = Depends(get_kb_session),
) -> ApplicationCapabilityGroupsResponse:
    """Every app-capability link across the portfolio, for client-side grouping by
    business capability (ADP-8xo, Application Portfolio pivot, dimension 1 of 5).

    Open read -- fit_score carries no READ_APPLICATION_* gate (confirmed against
    adp.authz.permissions; only Risk/Cost/Governance are gated), so no route-level
    permission dependency is needed, unlike applications-heatmap's cost dimension.
    """
    from adp.application import store as astore

    links = await astore.list_all_capability_links(session)
    return ApplicationCapabilityGroupsResponse(items=links)
