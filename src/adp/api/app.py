"""ADP Platform API — FastAPI application factory."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request, Response

from adp.api.routers import documents, export_router, health, layouts, render, theme
from adp.telemetry.context import TraceIdFilter, generate_trace_id, set_trace_id
from adp.telemetry.metrics import ACTIVE_REQUESTS, ERROR_COUNTER, REQUEST_COUNTER, REQUEST_LATENCY


def _install_trace_id_logging() -> None:
    """Install TraceIdFilter on the root logger (QG-10 / FR-001).

    Every log.info/warning/error call from any module automatically carries
    record.trace_id after this runs. Called once at app startup.
    """
    root_logger = logging.getLogger()
    if not any(isinstance(f, TraceIdFilter) for f in root_logger.filters):
        root_logger.addFilter(TraceIdFilter())


def create_app() -> FastAPI:
    _install_trace_id_logging()

    app = FastAPI(
        title="ADP Platform API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next) -> Response:  # type: ignore[type-arg]
        """Combined observability middleware: trace ID + Prometheus metrics (ADP-SPEC-012).

        Order of operations:
        1. Extract/generate trace ID → set ContextVar (FR-002 / QG-10)
        2. Track active request count (saturation metric)
        3. Time the request, record latency and status (rate/error/duration metrics)
        4. Return X-Trace-ID header in response
        """
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        set_trace_id(trace_id)

        route = request.url.path
        ACTIVE_REQUESTS.inc()
        t0 = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            ERROR_COUNTER.labels(route=route).inc()
            ACTIVE_REQUESTS.dec()
            raise
        else:
            elapsed = time.monotonic() - t0
            status_str = str(response.status_code)
            method = request.method
            REQUEST_COUNTER.labels(method=method, route=route, status=status_str).inc()
            REQUEST_LATENCY.labels(route=route).observe(elapsed)
            if response.status_code >= 400:
                ERROR_COUNTER.labels(route=route).inc()
            ACTIVE_REQUESTS.dec()
            response.headers["X-Trace-ID"] = trace_id
            return response

    app.include_router(layouts.router)
    app.include_router(theme.router)
    app.include_router(render.router)
    app.include_router(documents.router)
    app.include_router(export_router.router)
    app.include_router(health.router)
    return app


app = create_app()
