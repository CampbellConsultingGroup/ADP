"""TIME rationalization projection (APM US1, ADP-SPEC-038).

Places each assessed application on the business-value × technical-health plot:
Tolerate / Invest / Migrate / Eliminate. An application is *placed* only when
both ``business_value`` and ``health_score`` are present; otherwise it is
reported as unassessed and never defaulted into a quadrant.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from adp.application.models import (
    Quadrant,
    RationalizationEntry,
    RationalizationResponse,
)

# 1–5 scale midpoint; a score >= 3 counts as "high".
_HIGH_THRESHOLD = 3


def quadrant_for(business_value: int | None, health_score: int | None) -> Quadrant | None:
    """Map (business_value, health_score) to a TIME quadrant, or None if unassessed.

    high value + high health → invest;  high value + low health → migrate;
    low value + high health  → tolerate; low value + low health  → eliminate.
    """
    if business_value is None or health_score is None:
        return None
    value_high = business_value >= _HIGH_THRESHOLD
    health_high = health_score >= _HIGH_THRESHOLD
    if value_high and health_high:
        return "invest"
    if value_high and not health_high:
        return "migrate"
    if not value_high and health_high:
        return "tolerate"
    return "eliminate"


def build_projection(rows: Iterable[Mapping[str, Any]]) -> RationalizationResponse:
    """Split rows into placed (has a quadrant) vs unassessed, preserving input order.

    Each row must expose ``id``, ``name``, ``business_value``, ``health_score``.
    """
    assessed: list[RationalizationEntry] = []
    unassessed: list[RationalizationEntry] = []
    for row in rows:
        business_value = row["business_value"]
        health_score = row["health_score"]
        quadrant = quadrant_for(business_value, health_score)
        entry = RationalizationEntry(
            app_id=row["id"],
            name=row["name"],
            business_value=business_value,
            health_score=health_score,
            quadrant=quadrant,
        )
        (assessed if quadrant is not None else unassessed).append(entry)
    return RationalizationResponse(
        assessed=assessed,
        unassessed=unassessed,
        total=len(assessed) + len(unassessed),
    )
