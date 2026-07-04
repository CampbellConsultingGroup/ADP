"""ADP Platform API — FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response

from adp.api.routers import (
    calm,
    config,
    designs,
    documents,
    export_router,
    health,
    intake,
    knowledge,
    layouts,
    recommend,
    render,
    theme,
)
from adp.auth.middleware import AuthMiddleware
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


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: mark stale operations failed + schedule cleanup. Shutdown: cancel cleanup."""
    from adp.api.deps import get_operation_store

    _cleanup_task: asyncio.Task | None = None
    try:
        op_store = await get_operation_store()
        stale = await op_store.mark_stale_running_as_failed("server restarted during processing")
        if stale:
            logging.getLogger(__name__).info(
                "startup: marked %d stale running operations as failed", stale
            )

        async def _cleanup_loop() -> None:
            while True:
                await asyncio.sleep(600)  # 10 minutes
                try:
                    deleted = await op_store.delete_expired()
                    if deleted:
                        logging.getLogger(__name__).info(
                            "cleanup: deleted %d expired operations", deleted
                        )
                except Exception as exc:
                    logging.getLogger(__name__).warning("cleanup error: %s", exc)

        _cleanup_task = asyncio.create_task(_cleanup_loop())
    except Exception as exc:
        # DB may not be configured — log and continue (graceful degradation)
        logging.getLogger(__name__).warning("lifespan startup skipped: %s", exc)

    yield

    if _cleanup_task:
        _cleanup_task.cancel()


def create_app() -> FastAPI:
    _install_trace_id_logging()

    app = FastAPI(
        title="ADP Platform API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    # Auth middleware — validates Bearer tokens for all /api/v1/ routes (ADP-SPEC-026)
    # Must be added before other middleware; no-op when ADP_AUTH_ENABLED=false
    app.add_middleware(AuthMiddleware)

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

    app.include_router(designs.router)
    app.include_router(layouts.router)
    app.include_router(theme.router)
    app.include_router(render.router)
    app.include_router(documents.router)
    app.include_router(export_router.router)
    app.include_router(health.router)
    app.include_router(intake.router)
    app.include_router(recommend.router)
    app.include_router(knowledge.router)
    app.include_router(calm.router)
    app.include_router(config.router)

    # Serve Vite-built frontend static files when running in Docker (ADP-SPEC-025)
    import os
    static_dir = os.environ.get("ADP_STATIC_DIR", "")
    if static_dir and os.path.isdir(static_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
