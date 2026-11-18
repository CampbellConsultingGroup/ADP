"""Application assessments and 1:1 records: risk, health, business value, cost, governance,
quality (split out of ``adp.application.store``, which re-exports every name here; ADP-blp.27).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application.models import (
    BUSINESS_VALUE_DIMENSIONS,
    BUSINESS_VALUE_EVIDENCE_CAP,
    BUSINESS_VALUE_WEIGHTS,
    HEALTH_DIMENSIONS,
    TCO_BUCKET_NAMES,
    ApplicationCost,
    ApplicationCostUpdate,
    ApplicationGovernance,
    ApplicationGovernanceUpdate,
    ApplicationQualityMetric,
    ApplicationQualityMetricUpdate,
    ApplicationRisk,
    ApplicationRiskUpdate,
    BusinessUnitCostRollup,
    BusinessValueAssessmentEntry,
    BusinessValueAssessmentResponse,
    BusinessValueAssessmentResult,
    BusinessValueAssessmentSubmit,
    BusinessValueDimension,
    CostBucket,
    CostRollupResponse,
    FrameworkNotSelectableError,
    HealthAssessmentEntry,
    HealthAssessmentResponse,
    HealthAssessmentSubmit,
    OutOfSupportEntry,
    OutOfSupportResponse,
    RenewalSoonEntry,
    RenewalsSoonResponse,
    UnknownFrameworkError,
)
from adp.application.store_base import (
    _now,
    get_application,
)
from adp.application.tables import (
    _application_contracts,
    _application_cost,
    _application_framework_tags,
    _application_quality_metrics,
    _application_risk,
    _applications,
    _business_value_assessment,
    _health_assessment,
    _regulatory_frameworks,
)

# ── Application Risk & Compliance CRUD (US3) ──────────────────────────────────


def _row_to_risk(row: Any, regulatory_tags: list[str]) -> ApplicationRisk:
    return ApplicationRisk(
        security_posture=row.security_posture,
        vulnerability_status=row.vulnerability_status,
        data_classification=row.data_classification,
        regulatory_tags=regulatory_tags,
        dr_bc_status=row.dr_bc_status,
        end_of_life_date=row.end_of_life_date,
        end_of_support_date=row.end_of_support_date,
        updated_at=row.updated_at,
    )


async def _linked_framework_ids(app_id: str, session: AsyncSession) -> list[str]:
    """932-regulatory-framework-tags: bare id list -- mirrors list_framework_ids_for_theme's exact
    shape (adp.strategy.store, 927-theme-framework-mapping)."""
    result = await session.execute(
        sa.select(_application_framework_tags.c.framework_id)
        .where(_application_framework_tags.c.application_id == app_id)
        .order_by(_application_framework_tags.c.framework_id)
    )
    return [row.framework_id for row in result]


async def _framework_record(framework_id: str, session: AsyncSession) -> dict[str, Any] | None:
    """932-regulatory-framework-tags: existence + status read against the read-only
    _regulatory_frameworks mirror. Returns None if no such framework exists."""
    result = await session.execute(
        sa.select(_regulatory_frameworks).where(_regulatory_frameworks.c.id == framework_id)
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def get_application_risk(app_id: str, session: AsyncSession) -> ApplicationRisk | None:
    result = await session.execute(
        sa.select(_application_risk).where(_application_risk.c.app_id == app_id)
    )
    row = result.mappings().first()
    if row is None:
        return None
    tags = await _linked_framework_ids(app_id, session)
    return _row_to_risk(row, tags)


async def upsert_application_risk(
    app_id: str, body: ApplicationRiskUpdate, session: AsyncSession
) -> ApplicationRisk:
    """932-regulatory-framework-tags (ADP-bkg, research.md D2/D4/D5): regulatory_tags is the
    complete desired set of framework ids -- de-duplicated, diffed against the currently-linked
    set, with every newly-added id validated (exists + status in_force/amended) before anything is
    written. An id that was already linked is never re-validated against its framework's current
    status (spec.md Edge Cases) -- only ids genuinely new to this application are checked."""
    values: dict[str, Any] = {
        "security_posture": body.security_posture,
        "vulnerability_status": body.vulnerability_status,
        "data_classification": body.data_classification,
        "dr_bc_status": body.dr_bc_status,
        "end_of_life_date": body.end_of_life_date,
        "end_of_support_date": body.end_of_support_date,
        "updated_at": _now(),
    }

    desired_ids = set(body.regulatory_tags)
    current_ids = set(await _linked_framework_ids(app_id, session))
    to_add = desired_ids - current_ids
    to_remove = current_ids - desired_ids

    for framework_id in to_add:
        record = await _framework_record(framework_id, session)
        if record is None:
            raise UnknownFrameworkError(f"No such regulatory framework: {framework_id!r}")
        if record["status"] not in ("in_force", "amended"):
            raise FrameworkNotSelectableError(
                f"Framework {framework_id!r} has status {record['status']!r} "
                "(must be in_force or amended to be newly tagged)"
            )

    exists = (
        await session.execute(
            sa.select(_application_risk.c.app_id).where(_application_risk.c.app_id == app_id)
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_risk.update()
            .where(_application_risk.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(_application_risk.insert().values(app_id=app_id, **values))

    if to_remove:
        await session.execute(
            _application_framework_tags.delete().where(
                _application_framework_tags.c.application_id == app_id,
                _application_framework_tags.c.framework_id.in_(to_remove),
            )
        )
    for framework_id in to_add:
        await session.execute(
            _application_framework_tags.insert().values(
                application_id=app_id, framework_id=framework_id, created_at=_now()
            )
        )

    risk = await get_application_risk(app_id, session)
    assert risk is not None  # just upserted
    return risk


async def list_out_of_support(session: AsyncSession, today: date) -> OutOfSupportResponse:
    stmt = (
        sa.select(
            _application_risk.c.app_id,
            _applications.c.name,
            _application_risk.c.end_of_support_date,
        )
        .join(_applications, _applications.c.id == _application_risk.c.app_id)
        .where(
            _application_risk.c.end_of_support_date.is_not(None),
            _application_risk.c.end_of_support_date < today,
        )
        .order_by(_applications.c.name)
    )
    result = await session.execute(stmt)
    items = [
        OutOfSupportEntry(
            app_id=r.app_id, name=r.name, end_of_support_date=r.end_of_support_date
        )
        for r in result.mappings().all()
    ]
    return OutOfSupportResponse(items=items, total=len(items))


# ── Application Health Assessment (docs/application-health-assessment-spec.md) ─


async def get_health_assessment(app_id: str, session: AsyncSession) -> HealthAssessmentResponse:
    """Caller (router) has already validated app_id exists."""
    result = await session.execute(
        sa.select(_health_assessment)
        .where(_health_assessment.c.application_id == app_id)
        .order_by(_health_assessment.c.dimension)
    )
    entries = [
        HealthAssessmentEntry(
            dimension=row.dimension,
            score=row.score,
            assessed_at=row.assessed_at,
            assessed_by=row.assessed_by,
        )
        for row in result.mappings().all()
    ]
    app = await get_application(app_id, session)
    assert app is not None  # caller already checked
    return HealthAssessmentResponse(
        application_id=app_id, entries=entries, health_score=app.health_score
    )


async def upsert_health_assessment(
    app_id: str, body: HealthAssessmentSubmit, actor: str | None, session: AsyncSession
) -> HealthAssessmentResponse:
    """Upserts all six dimension rows and recomputes applications.health_score
    as their minimum, in one call -- the two can never drift apart (spec §5).
    Caller (router) has already validated app_id exists."""
    now = _now()
    scores = body.as_dimension_scores()

    existing_dims = {
        row.dimension
        for row in (
            await session.execute(
                sa.select(_health_assessment.c.dimension).where(
                    _health_assessment.c.application_id == app_id
                )
            )
        ).all()
    }
    for dimension in HEALTH_DIMENSIONS:
        values = {
            "score": scores[dimension],
            "assessed_at": now,
            "assessed_by": actor,
        }
        if dimension in existing_dims:
            await session.execute(
                _health_assessment.update()
                .where(
                    _health_assessment.c.application_id == app_id,
                    _health_assessment.c.dimension == dimension,
                )
                .values(**values)
            )
        else:
            await session.execute(
                _health_assessment.insert().values(
                    application_id=app_id, dimension=dimension, **values
                )
            )

    health_score = min(scores.values())
    await session.execute(
        _applications.update()
        .where(_applications.c.id == app_id)
        .values(health_score=health_score, updated_at=now)
    )
    return await get_health_assessment(app_id, session)


# ── Application Business Value Assessment
#    (docs/application-business-value-assessment-spec.md) ─────────────────────


def compute_business_value_score(
    scores: dict[BusinessValueDimension, int],
    weights: dict[BusinessValueDimension, float] | None = None,
) -> BusinessValueAssessmentResult:
    """Pure, no-I/O aggregation (spec §5, mirrors adp.strategy.store.
    compute_status()'s own precedent for derived-value functions): a
    weighted average of all six dimensions, soft-capped by the
    evidence_measurability score.

    Unlike Health's MIN() (a hard risk gate), this is a weighted composite
    with a soft ceiling -- one weak dimension pulls the average down but
    doesn't zero it out, except evidence_measurability, which additionally
    caps how high the *result* can land (spec §5.2's cap table), independent
    of its own 10% weight in the average.

    ADP-68z: `weights` is optional and defaults to the hardcoded
    BUSINESS_VALUE_WEIGHTS constant, preserving this function's purity/no-I/O
    guarantee -- callers (both below) resolve the *effective* weights (an
    admin-saved override, if any, else the fallback) via
    adp.admin.rubric_registry.get_effective_weights() BEFORE calling this
    function, mirroring how adp.admin.prompt_registry.get_effective_prompt()
    is the one I/O-touching layer for agent prompts.
    """
    effective_weights = weights if weights is not None else BUSINESS_VALUE_WEIGHTS
    raw_score = sum(scores[dim] * effective_weights[dim] for dim in BUSINESS_VALUE_DIMENSIONS)
    evidence_score = scores["evidence_measurability"]
    cap = BUSINESS_VALUE_EVIDENCE_CAP[evidence_score]
    capped_value = min(raw_score, cap) if cap is not None else raw_score
    # Round-half-up, not Python's banker's-rounding round() (spec §5.4) --
    # e.g. 4.5 must land on 5, not 4, matching what the UI visibly shows.
    business_value = int(capped_value + 0.5)
    business_value = max(1, min(5, business_value))  # clamp -- defensive, should never trigger
    return BusinessValueAssessmentResult(
        business_value=business_value,
        weighted_average=round(raw_score, 2),
        evidence_score=evidence_score,
        cap=cap,
        capped=cap is not None and raw_score > cap,
    )


async def get_business_value_assessment(
    app_id: str, session: AsyncSession
) -> BusinessValueAssessmentResponse:
    """Caller (router) has already validated app_id exists."""
    result = await session.execute(
        sa.select(_business_value_assessment)
        .where(_business_value_assessment.c.application_id == app_id)
        .order_by(_business_value_assessment.c.dimension)
    )
    rows = result.mappings().all()
    entries = [
        BusinessValueAssessmentEntry(
            dimension=row.dimension,
            score=row.score,
            assessed_at=row.assessed_at,
            assessed_by=row.assessed_by,
        )
        for row in rows
    ]
    computed_result = None
    if len(rows) == len(BUSINESS_VALUE_DIMENSIONS):
        # ADP-68z: resolve the effective (admin-overridden, or fallback) weights
        # before calling the pure aggregation function -- see that function's
        # own docstring for why this resolution happens here, not inside it.
        from adp.admin.rubric_registry import get_effective_weights

        effective = await get_effective_weights("business_value")
        # rubric_registry's types are rubric-agnostic (dict[str, float]); the
        # actual keys are always valid BusinessValueDimension literals, enforced
        # by this rubric's own registered validator before ever being stored.
        weights = cast("dict[BusinessValueDimension, float]", effective.weights)
        computed_result = compute_business_value_score(
            {row.dimension: row.score for row in rows}, weights
        )
    return BusinessValueAssessmentResponse(
        application_id=app_id, entries=entries, result=computed_result
    )


async def upsert_business_value_assessment(
    app_id: str, body: BusinessValueAssessmentSubmit, actor: str | None, session: AsyncSession
) -> BusinessValueAssessmentResponse:
    """Upserts all six dimension rows and recomputes applications.business_value
    via compute_business_value_score(), in one call -- the two can never
    drift apart (spec §6). Caller (router) has already validated app_id
    exists."""
    now = _now()
    scores = body.as_dimension_scores()

    existing_dims = {
        row.dimension
        for row in (
            await session.execute(
                sa.select(_business_value_assessment.c.dimension).where(
                    _business_value_assessment.c.application_id == app_id
                )
            )
        ).all()
    }
    for dimension in BUSINESS_VALUE_DIMENSIONS:
        values = {
            "score": scores[dimension],
            "assessed_at": now,
            "assessed_by": actor,
        }
        if dimension in existing_dims:
            await session.execute(
                _business_value_assessment.update()
                .where(
                    _business_value_assessment.c.application_id == app_id,
                    _business_value_assessment.c.dimension == dimension,
                )
                .values(**values)
            )
        else:
            await session.execute(
                _business_value_assessment.insert().values(
                    application_id=app_id, dimension=dimension, **values
                )
            )

    # ADP-68z: resolve the effective (admin-overridden, or fallback) weights first.
    from adp.admin.rubric_registry import get_effective_weights

    effective = await get_effective_weights("business_value")
    weights = cast("dict[BusinessValueDimension, float]", effective.weights)
    computed_result = compute_business_value_score(scores, weights)
    await session.execute(
        _applications.update()
        .where(_applications.c.id == app_id)
        .values(business_value=computed_result.business_value, updated_at=now)
    )
    return await get_business_value_assessment(app_id, session)


# ── Application Cost / TCO CRUD (US4, ADP-9x6) ────────────────────────────────


def _row_to_cost(row: Any) -> ApplicationCost:
    buckets = {
        name: CostBucket(one_time=row[f"{name}_one_time"], annual=row[f"{name}_annual"])
        for name in TCO_BUCKET_NAMES
    }
    return ApplicationCost(
        currency=row["currency"],
        horizon_years=row["horizon_years"],
        updated_at=row["updated_at"],
        **buckets,
    )


async def get_application_cost(app_id: str, session: AsyncSession) -> ApplicationCost | None:
    result = await session.execute(
        sa.select(_application_cost).where(_application_cost.c.app_id == app_id)
    )
    row = result.mappings().first()
    return _row_to_cost(row) if row else None


async def upsert_application_cost(
    app_id: str, body: ApplicationCostUpdate, session: AsyncSession
) -> ApplicationCost:
    values: dict[str, Any] = {
        "currency": body.currency,
        "horizon_years": body.horizon_years,
        "updated_at": _now(),
    }
    for name in TCO_BUCKET_NAMES:
        bucket = getattr(body, name)
        values[f"{name}_one_time"] = bucket.one_time
        values[f"{name}_annual"] = bucket.annual

    exists = (
        await session.execute(
            sa.select(_application_cost.c.app_id).where(_application_cost.c.app_id == app_id)
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_cost.update()
            .where(_application_cost.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(_application_cost.insert().values(app_id=app_id, **values))
    cost = await get_application_cost(app_id, session)
    assert cost is not None  # just upserted
    return cost


async def list_all_costs(session: AsyncSession) -> dict[str, Decimal]:
    """TCO per application, for every application with a cost record.

    919-insights-dashboard: a bulk read for the applications heat map's cost dimension --
    reuses ``_row_to_cost`` (TCO is derived, not stored) rather than duplicating the
    bucket-sum formula in raw SQL. Applications with no cost record are simply absent from
    the returned mapping (caller renders them "unclassified", mirroring health_score/
    business_criticality/time_classification's own null handling).
    """
    result = await session.execute(sa.select(_application_cost))
    return {row["app_id"]: _row_to_cost(row).tco for row in result.mappings().all()}


async def rollup_cost_by_business_unit(session: AsyncSession) -> CostRollupResponse:
    """TCO per business unit, computed in Python (TCO is derived, not stored)."""
    stmt = sa.select(_applications.c.owning_business_unit, _application_cost).select_from(
        _application_cost.join(_applications, _applications.c.id == _application_cost.c.app_id)
    )
    result = await session.execute(stmt)

    bu_totals: dict[str | None, list[Any]] = {}
    grand_total = Decimal("0")
    for row in result.mappings().all():
        cost = _row_to_cost(row)
        bu = row["owning_business_unit"]
        entry = bu_totals.setdefault(bu, [Decimal("0"), 0])
        entry[0] += cost.tco
        entry[1] += 1
        grand_total += cost.tco

    items = [
        BusinessUnitCostRollup(business_unit=bu, app_count=count, tco=total)
        for bu, (total, count) in sorted(
            bu_totals.items(), key=lambda kv: (kv[0] is None, kv[0] or "")
        )
    ]
    return CostRollupResponse(items=items, total_tco=grand_total)


# ── Application Governance CRUD (US7) ─────────────────────────────────────────


def _row_to_governance(row: Any) -> ApplicationGovernance:
    return ApplicationGovernance(
        contract_terms=row.contract_terms,
        renewal_date=row.renewal_date,
        sla=row.sla,
        business_sponsor=row.business_sponsor,
        it_owner=row.it_owner,
        decision_rights=row.decision_rights,
        updated_at=row.updated_at,
    )


async def get_application_governance(
    app_id: str, session: AsyncSession
) -> ApplicationGovernance | None:
    result = await session.execute(
        sa.select(_application_contracts).where(_application_contracts.c.app_id == app_id)
    )
    row = result.mappings().first()
    return _row_to_governance(row) if row else None


async def upsert_application_governance(
    app_id: str, body: ApplicationGovernanceUpdate, session: AsyncSession
) -> ApplicationGovernance:
    values: dict[str, Any] = {
        "contract_terms": body.contract_terms,
        "renewal_date": body.renewal_date,
        "sla": body.sla,
        "business_sponsor": body.business_sponsor,
        "it_owner": body.it_owner,
        "decision_rights": body.decision_rights,
        "updated_at": _now(),
    }
    exists = (
        await session.execute(
            sa.select(_application_contracts.c.app_id).where(
                _application_contracts.c.app_id == app_id
            )
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_contracts.update()
            .where(_application_contracts.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(_application_contracts.insert().values(app_id=app_id, **values))
    governance = await get_application_governance(app_id, session)
    assert governance is not None  # just upserted
    return governance


async def list_renewals_soon(
    session: AsyncSession, today: date, within_days: int = 90
) -> RenewalsSoonResponse:
    horizon = today + timedelta(days=within_days)
    stmt = (
        sa.select(
            _application_contracts.c.app_id,
            _applications.c.name,
            _application_contracts.c.renewal_date,
        )
        .join(_applications, _applications.c.id == _application_contracts.c.app_id)
        .where(
            _application_contracts.c.renewal_date.is_not(None),
            _application_contracts.c.renewal_date >= today,
            _application_contracts.c.renewal_date <= horizon,
        )
        .order_by(_application_contracts.c.renewal_date)
    )
    result = await session.execute(stmt)
    items = [
        RenewalSoonEntry(app_id=r.app_id, name=r.name, renewal_date=r.renewal_date)
        for r in result.mappings().all()
    ]
    return RenewalsSoonResponse(items=items, total=len(items))


# ── Application Quality & Performance CRUD (US8) ──────────────────────────────


def _row_to_quality(row: Any) -> ApplicationQualityMetric:
    return ApplicationQualityMetric(
        uptime_pct=row.uptime_pct,
        incidents_ytd=row.incidents_ytd,
        satisfaction_score=row.satisfaction_score,
        perf_note=row.perf_note,
        ticket_volume_30d=row.ticket_volume_30d,
        updated_at=row.updated_at,
    )


async def get_application_quality(
    app_id: str, session: AsyncSession
) -> ApplicationQualityMetric | None:
    result = await session.execute(
        sa.select(_application_quality_metrics).where(
            _application_quality_metrics.c.app_id == app_id
        )
    )
    row = result.mappings().first()
    return _row_to_quality(row) if row else None


async def upsert_application_quality(
    app_id: str, body: ApplicationQualityMetricUpdate, session: AsyncSession
) -> ApplicationQualityMetric:
    values: dict[str, Any] = {
        "uptime_pct": body.uptime_pct,
        "incidents_ytd": body.incidents_ytd,
        "satisfaction_score": body.satisfaction_score,
        "perf_note": body.perf_note,
        "ticket_volume_30d": body.ticket_volume_30d,
        "updated_at": _now(),
    }
    exists = (
        await session.execute(
            sa.select(_application_quality_metrics.c.app_id).where(
                _application_quality_metrics.c.app_id == app_id
            )
        )
    ).first() is not None
    if exists:
        await session.execute(
            _application_quality_metrics.update()
            .where(_application_quality_metrics.c.app_id == app_id)
            .values(**values)
        )
    else:
        await session.execute(
            _application_quality_metrics.insert().values(app_id=app_id, **values)
        )
    quality = await get_application_quality(app_id, session)
    assert quality is not None  # just upserted
    return quality
