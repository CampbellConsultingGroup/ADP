"""Health and metrics endpoints (ADP-SPEC-012 FR-004 / US3).

GET /health  — liveness check; always returns HTTP 200 with structured JSON
GET /metrics — Prometheus scrape endpoint; unauthenticated (metrics are not sensitive)
"""

from __future__ import annotations

from typing import Literal

import prometheus_client
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Structured health response (I1 remediation: defined inline, not in adp.docs.models)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "unhealthy"]
    reason: str | None = None
    version: str = "0.1.0"


@router.get("/health", response_model=HealthStatus)
async def get_health() -> HealthStatus:
    """Return service liveness status.

    Always returns HTTP 200 — orchestrators check the `status` field, not the
    HTTP status code, to distinguish healthy from unhealthy. This prevents
    retry storms when the service is degraded but still responding.
    """
    return HealthStatus(status="healthy", reason=None)


@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics() -> PlainTextResponse:
    """Return Prometheus-format metrics for scraping (FR-004).

    Metrics contain only counts, latencies, and resource saturation — never
    design content or credentials (FR-006 / QG-08).
    """
    data = prometheus_client.generate_latest()
    return PlainTextResponse(
        data,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
