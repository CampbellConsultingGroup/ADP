"""Helpers shared by the application store modules (ADP-blp.27).

Row converters and the two single-row reads the link, roadmap and assessment modules need.
``adp.application.store`` re-exports every name here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.application.models import (
    Application,
    TechnicalCapability,
)
from adp.application.tables import (
    _applications,
    _tech_caps,
)
from adp.db import is_unique_violation


def _rowcount(result: Any) -> int:
    """DML executes return CursorResult at runtime; session.execute is typed
    as Result[Any], which lacks rowcount."""
    return cast("sa.CursorResult[Any]", result).rowcount


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_application(row: Any) -> Application:
    return Application(
        id=row.id,
        name=row.name,
        description=row.description,
        vendor=row.vendor,
        primary_owner=row.primary_owner,
        time_classification=row.time_classification,
        r_strategy=row.r_strategy,
        pace_layer=row.pace_layer,
        health_score=row.health_score,
        business_value=row.business_value,
        business_criticality=row.business_criticality,
        owning_business_unit=row.owning_business_unit,
        owning_org_unit_id=getattr(row, "owning_org_unit_id", None),
        business_owner=row.business_owner,
        technical_owner=row.technical_owner,
        lifecycle_status=row.lifecycle_status,
        hosting_model=row.hosting_model,
        application_type=row.application_type,
        architecture_pattern=row.architecture_pattern,
        tech_debt_flags=list(row.tech_debt_flags or []),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_tech_cap(row: Any) -> TechnicalCapability:
    return TechnicalCapability(
        id=row.id,
        name=row.name,
        description=row.description,
        parent_id=row.parent_id,
        level=row.level,
        created_at=row.created_at,
        strategic_relevance=getattr(row, "strategic_relevance", None),
        lifecycle_status=getattr(row, "lifecycle_status", None) or "current",
        end_of_life_date=getattr(row, "end_of_life_date", None),
    )


def _is_duplicate_error(exc: Exception) -> bool:
    return is_unique_violation(exc)


async def get_application(app_id: str, session: AsyncSession) -> Application | None:
    result = await session.execute(
        sa.select(_applications).where(_applications.c.id == app_id)
    )
    row = result.mappings().first()
    return _row_to_application(row) if row else None


async def get_technical_capability(tc_id: str, session: AsyncSession) -> TechnicalCapability | None:
    result = await session.execute(
        sa.select(_tech_caps).where(_tech_caps.c.id == tc_id)
    )
    row = result.mappings().first()
    return _row_to_tech_cap(row) if row else None
