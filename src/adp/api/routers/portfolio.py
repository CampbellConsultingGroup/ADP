"""Portfolio Analysis API — ADP-SPEC-031.

Read-only endpoints for cross-portfolio aggregation. All queries use indexed
columns (element_technology_tags B-tree indexes, designs.lifecycle_status index).
No new DB tables or migrations required.

Endpoints:
  GET /api/v1/portfolio/technologies              — technology landscape aggregation
  GET /api/v1/portfolio/designs                   — combined technology + lifecycle filter
  GET /api/v1/portfolio/search                    — cross-design element/technology search
  GET /api/v1/portfolio/summary                   — portfolio health summary header
  GET /api/v1/portfolio/applications-heatmap      — applications heat map (919-insights-dashboard)
  GET /api/v1/portfolio/application-capability-groups — app-capability links, bulk (ADP-8xo)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
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

class TechnologyCountItem(BaseModel):
    technology: str
    design_count: int


class TechnologiesResponse(BaseModel):
    technologies: list[TechnologyCountItem]
    total_unique: int


class PortfolioDesignSummary(BaseModel):
    id: str
    title: str
    lifecycle_status: str
    overdue_review: bool
    element_count: int
    primary_technology: str | None


class PortfolioDesignsResponse(BaseModel):
    designs: list[PortfolioDesignSummary]
    total: int
    page: int
    page_size: int


class PortfolioSearchResult(BaseModel):
    id: str
    title: str
    lifecycle_status: str
    overdue_review: bool
    element_count: int
    primary_technology: str | None
    matched_elements: list[str]


class PortfolioSearchResponse(BaseModel):
    designs: list[PortfolioSearchResult]
    total: int
    truncated: bool


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

@router.get("/technologies", response_model=TechnologiesResponse)
async def get_portfolio_technologies(
    session: AsyncSession = Depends(get_kb_session),
) -> TechnologiesResponse:
    """Top technologies across portfolio by distinct design count."""
    result = await session.execute(
        sa.text(
            """
            SELECT technology, COUNT(DISTINCT design_id) AS design_count
            FROM element_technology_tags
            WHERE technology IS NOT NULL
            GROUP BY technology
            ORDER BY design_count DESC
            LIMIT 50
            """
        )
    )
    rows = result.fetchall()
    items = [
        TechnologyCountItem(technology=r.technology, design_count=r.design_count)
        for r in rows
    ]
    return TechnologiesResponse(technologies=items, total_unique=len(items))


@router.get("/designs", response_model=PortfolioDesignsResponse)
async def get_portfolio_designs(
    technology: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_kb_session),
) -> PortfolioDesignsResponse:
    """Designs filtered by technology and/or lifecycle status using indexed columns."""
    now = datetime.now(timezone.utc)
    offset = (page - 1) * page_size

    # Build optional filter clauses dynamically — asyncpg cannot infer NULL param types
    # and '::text' cast suffix confuses SQLAlchemy's text() parameter parser.
    filter_clauses: list[str] = []
    filter_params: dict = {}
    if technology is not None:
        filter_clauses.append("ett.technology ILIKE '%' || :technology || '%'")
        filter_params["technology"] = technology
    if status is not None:
        filter_clauses.append("d.lifecycle_status = :status")
        filter_params["status"] = status

    where = ("WHERE " + " AND ".join(filter_clauses)) if filter_clauses else ""

    result = await session.execute(
        sa.text(
            f"""
            SELECT DISTINCT
                d.id,
                d.title,
                d.lifecycle_status,
                d.review_due,
                ett.technology AS primary_technology
            FROM designs d
            LEFT JOIN element_technology_tags ett ON d.id = ett.design_id
            {where}
            ORDER BY d.title
            LIMIT :limit OFFSET :offset
            """  # nosec B608 - filter clauses are hardcoded; values bound as params
        ),
        {**filter_params, "limit": page_size, "offset": offset},
    )
    rows = result.fetchall()

    designs = []
    for r in rows:
        overdue = bool(r.review_due and r.review_due < now.replace(tzinfo=None))
        designs.append(PortfolioDesignSummary(
            id=r.id,
            title=r.title,
            lifecycle_status=r.lifecycle_status,
            overdue_review=overdue,
            element_count=0,
            primary_technology=r.primary_technology,
        ))

    return PortfolioDesignsResponse(
        designs=designs,
        total=len(designs),
        page=page,
        page_size=page_size,
    )


@router.get("/search", response_model=PortfolioSearchResponse)
async def search_portfolio(
    q: str = Query(min_length=2),
    session: AsyncSession = Depends(get_kb_session),
) -> PortfolioSearchResponse:
    """Cross-design element and technology keyword search."""
    now = datetime.now(timezone.utc)

    result = await session.execute(
        sa.text(
            """
            SELECT DISTINCT
                d.id AS design_id,
                d.title,
                d.lifecycle_status,
                d.review_due,
                ett.element_id,
                ett.element_name,
                ett.technology
            FROM element_technology_tags ett
            JOIN designs d ON d.id = ett.design_id
            WHERE ett.technology ILIKE '%' || :q || '%'
               OR ett.element_name ILIKE '%' || :q || '%'
            ORDER BY d.title
            LIMIT 200
            """
        ),
        {"q": q},
    )
    rows = result.fetchall()

    truncated = len(rows) == 200

    designs_map: dict[str, dict] = {}
    for r in rows:
        did = r.design_id
        if did not in designs_map:
            overdue = bool(r.review_due and r.review_due < now.replace(tzinfo=None))
            designs_map[did] = {
                "id": did,
                "title": r.title,
                "lifecycle_status": r.lifecycle_status,
                "overdue_review": overdue,
                "element_count": 0,
                "primary_technology": r.technology,
                "matched_elements": [],
            }
        tech_label = f" (technology: {r.technology})" if r.technology else ""
        elem_label = r.element_name or r.element_id
        designs_map[did]["matched_elements"].append(f"{elem_label}{tech_label}")

    results = [PortfolioSearchResult(**d) for d in designs_map.values()]
    return PortfolioSearchResponse(designs=results, total=len(results), truncated=truncated)


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
