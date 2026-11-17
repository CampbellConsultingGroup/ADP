"""Health and metrics endpoints (ADP-SPEC-012 FR-004 / US3).

GET /health  — liveness check; always returns HTTP 200 with structured JSON
GET /metrics — Prometheus scrape endpoint; unauthenticated (metrics are not sensitive)
"""

from __future__ import annotations

import hmac
import os
from typing import Literal

import prometheus_client
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict

from adp.auth.middleware import _auth_enabled

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


def _metrics_allowed(request: Request) -> bool:
    """Who may read /metrics (ADP-blp.64).

    With authentication off (local development, tests) it is open. With it on, the
    caller must send ``Authorization: Bearer <ADP_METRICS_TOKEN>``; when no token is
    configured nobody can read it. A scraper has no user token, so this is a shared
    secret rather than a role.
    """
    if not _auth_enabled():
        return True
    token = os.environ.get("ADP_METRICS_TOKEN", "")
    if not token:
        return False
    supplied = request.headers.get("authorization", "")
    return hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode())


@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics(request: Request) -> PlainTextResponse:
    """Return Prometheus-format metrics for scraping (FR-004).

    Metrics contain only counts, latencies, and resource saturation — never
    design content or credentials (FR-006 / QG-08).
    """
    if not _metrics_allowed(request):
        # 404, not 401: do not advertise the endpoint to an anonymous caller.
        raise HTTPException(status_code=404, detail="Not found")
    data = prometheus_client.generate_latest()
    return PlainTextResponse(
        data,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
