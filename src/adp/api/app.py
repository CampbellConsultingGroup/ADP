"""ADP Platform API — FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request, Response

from adp.agentic import router as agentic_router_module
from adp.agentic import store as agstore
from adp.api.limits import (
    BodySizeLimitMiddleware,
    enforce_llm_rate_limit,
    refresh_llm_settings,
)
from adp.api.routers import (
    admin_prompts_router,
    admin_rubrics_router,
    ai_process,
    auth_proxy,
    calm,
    config,
    designs,
    documents,
    elements,
    export_router,
    governance,
    health,
    intake,
    knowledge,
    layouts,
    lifecycle,
    portfolio,
    reasoning,
    recommend,
    render,
    search,
    tags,
    theme,
    validate,
)
from adp.api.routers.me import router as me_router
from adp.application import app_capabilities_router
from adp.application import store as astore
from adp.application.router import (
    applications_router,
    initiatives_router,
    integrations_router,
    tech_caps_router,
)
from adp.auth.middleware import AuthMiddleware, log_auth_mode
from adp.authz.enforcement import enforce_route_permission
from adp.business import agent_review_router as business_agent_review_router_module
from adp.business import router as business_router_module
from adp.business import store as bstore
from adp.business import value_chains_router as business_value_chains_router_module
from adp.chat import router as chat_router_module
from adp.compliance import applicability_router as compliance_applicability_router_module
from adp.compliance import router as compliance_router_module
from adp.diagrams import router as diagrams_router
from adp.export import agentic as agentic_export
from adp.export import application_arch, business_arch
from adp.export import patterns as patterns_export
from adp.export import strategy as strategy_export
from adp.organization import links_router as organization_links_router_module
from adp.organization import router as organization_router_module
from adp.patterns import adoptions_router as pattern_adoptions_router_module
from adp.patterns import router as patterns_router_module
from adp.patterns import store as patterns_store
from adp.strategy import router as strategy_router
from adp.strategy import store as sstore
from adp.telemetry.context import TraceIdFilter, generate_trace_id, set_trace_id
from adp.telemetry.metrics import ACTIVE_REQUESTS, ERROR_COUNTER, REQUEST_COUNTER, REQUEST_LATENCY


def start_business_arch_export() -> asyncio.Task[None] | None:
    """ADP-SPEC-044: start the continuous business architecture export sync.
    No-op unless ADP_BUSINESS_ARCH_EXPORT_ROOT is set (research.md Decision 4
    — opt-in, never a silent default write)."""
    export_root = os.environ.get("ADP_BUSINESS_ARCH_EXPORT_ROOT")
    interval = float(os.environ.get("ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS", "60"))
    return business_arch.start_background_sync(
        export_root, interval, bstore._get_session_factory()
    )


async def stop_business_arch_export(task: asyncio.Task[None] | None) -> None:
    """ADP-SPEC-044: stop the continuous business architecture export sync."""
    await business_arch.stop_background_sync(task)


def start_application_arch_export() -> asyncio.Task[None] | None:
    """ADP-SPEC-045: start the continuous Application registry export sync.
    Reuses the SAME ADP_BUSINESS_ARCH_EXPORT_ROOT/_INTERVAL_SECONDS env vars
    as ADP-SPEC-044 -- no new configuration surface for this feature. No-op
    unless that root is set."""
    export_root = os.environ.get("ADP_BUSINESS_ARCH_EXPORT_ROOT")
    interval = float(os.environ.get("ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS", "60"))
    return application_arch.start_background_sync(
        export_root, interval, astore._get_session_factory()
    )


async def stop_application_arch_export(task: asyncio.Task[None] | None) -> None:
    """ADP-SPEC-045: stop the continuous Application registry export sync."""
    await application_arch.stop_background_sync(task)


def start_strategy_export() -> asyncio.Task[None] | None:
    """ADP-81p.3: start the continuous Strategy domain export sync. Reuses the
    SAME ADP_BUSINESS_ARCH_EXPORT_ROOT/_INTERVAL_SECONDS env vars as
    ADP-SPEC-044/045 -- no new configuration surface for this feature. No-op
    unless that root is set."""
    export_root = os.environ.get("ADP_BUSINESS_ARCH_EXPORT_ROOT")
    interval = float(os.environ.get("ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS", "60"))
    return strategy_export.start_background_sync(
        export_root, interval, sstore._get_session_factory()
    )


async def stop_strategy_export(task: asyncio.Task[None] | None) -> None:
    """ADP-81p.3: stop the continuous Strategy domain export sync."""
    await strategy_export.stop_background_sync(task)


def start_agentic_export() -> asyncio.Task[None] | None:
    """933-agent-registry: start the continuous agent registry export sync, sharing the same
    ADP_BUSINESS_ARCH_EXPORT_ROOT/_INTERVAL_SECONDS env vars as the other export domains. No-op
    unless that root is set."""
    export_root = os.environ.get("ADP_BUSINESS_ARCH_EXPORT_ROOT")
    interval = float(os.environ.get("ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS", "60"))
    return agentic_export.start_background_sync(
        export_root, interval, agstore._get_session_factory()
    )


async def stop_agentic_export(task: asyncio.Task[None] | None) -> None:
    """933-agent-registry: stop the continuous agent registry export sync."""
    await agentic_export.stop_background_sync(task)


def start_pattern_export() -> asyncio.Task[None] | None:
    """935-pattern-registry: start the continuous export of current pattern versions as YAML,
    sharing ADP_BUSINESS_ARCH_EXPORT_ROOT/_INTERVAL_SECONDS. No-op unless that root is set."""
    export_root = os.environ.get("ADP_BUSINESS_ARCH_EXPORT_ROOT")
    interval = float(os.environ.get("ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS", "60"))
    return patterns_export.start_background_sync(
        export_root, interval, patterns_store._get_session_factory()
    )


async def stop_pattern_export(task: asyncio.Task[None] | None) -> None:
    """935-pattern-registry: stop the continuous pattern export sync."""
    await patterns_export.stop_background_sync(task)


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
    """Startup: mark stale operations failed + schedule cleanup + start the
    business architecture / application registry / strategy domain export
    syncs (ADP-SPEC-044/045/ADP-81p.3, all opt-in). Shutdown: cancel every
    background task."""
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

    log_auth_mode()  # ADP-blp.3: say loudly when authentication is off
    # Load the embedding model now, in a thread, rather than inside the first write request.
    from adp.knowledge.embedder import start_warmup

    start_warmup()
    # ADP-SPEC-044: opt-in continuous export of business architecture data to
    # versioned files. start_business_arch_export is a no-op (returns None,
    # writes nothing) unless ADP_BUSINESS_ARCH_EXPORT_ROOT is set.
    _export_task = start_business_arch_export()
    # ADP-SPEC-045: opt-in continuous export of the Application registry,
    # sharing the same env vars/root as ADP-SPEC-044 above.
    _app_export_task = start_application_arch_export()
    # ADP-81p.3: opt-in continuous export of the Strategy domain, sharing the
    # same env vars/root as ADP-SPEC-044/045 above.
    _strategy_export_task = start_strategy_export()
    # 933-agent-registry: opt-in continuous export of the agent registry, same env vars/root.
    _agentic_export_task = start_agentic_export()
    # 935-pattern-registry: opt-in continuous export of current pattern versions, same root.
    _pattern_export_task = start_pattern_export()

    yield

    if _cleanup_task:
        _cleanup_task.cancel()
    await stop_business_arch_export(_export_task)
    await stop_application_arch_export(_app_export_task)
    await stop_strategy_export(_strategy_export_task)
    await stop_agentic_export(_agentic_export_task)
    await stop_pattern_export(_pattern_export_task)
    # ADP-blp.24: let audit/provenance writes still in flight finish before the pool closes.
    from adp import background as _background

    await _background.drain()
    # ADP-blp.15: close the shared connection pool.
    from adp import db as _db

    await _db.dispose()
    # ADP-blp.22: close the shared LLM HTTP client.
    from adp.llm.client import aclose_shared_clients

    await aclose_shared_clients()


# ADP-blp.11. The SPA is served from this origin and talks only to it (Keycloak is reached
# through /auth on the same origin). Inline styles are allowed because the UI sets them on
# almost every element; inline and third-party scripts are not. Override the whole policy with
# ADP_CONTENT_SECURITY_POLICY, or set it to an empty string to send none.
_DEFAULT_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def _content_security_policy() -> str:
    return os.environ.get("ADP_CONTENT_SECURITY_POLICY", _DEFAULT_CSP).strip()


def _metric_route(request: Request) -> str:
    """The matched route's template, e.g. /api/v1/designs/{design_id} (ADP-blp.9).

    The raw URL path used to be the label, so every distinct id -- and every made-up path an
    unauthenticated caller cared to request -- created a new time series that was never freed,
    and put entity ids into the public /metrics output. Anything that matched no route is
    counted under one "unmatched" label. Read after the request is routed.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else "unmatched"


def create_app() -> FastAPI:
    _install_trace_id_logging()

    app = FastAPI(
        title="ADP Platform API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        lifespan=_lifespan,
        # Action-based authorization for every mutating route (ADP-SPEC-004).
        # ADP-blp.5: plus a per-user rate limit on the routes that call the model.
        dependencies=[
            Depends(enforce_route_permission),
            Depends(enforce_llm_rate_limit),
            Depends(refresh_llm_settings),
        ],
    )

    # Auth middleware — validates Bearer tokens for all /api/v1/ routes (ADP-SPEC-026)
    # Must be added before other middleware; no-op when ADP_AUTH_ENABLED=false
    app.add_middleware(AuthMiddleware)
    # ADP-blp.5: cap request body size for every route (outermost, so it runs first).
    app.add_middleware(BodySizeLimitMiddleware)

    # ── Security headers (ZAP pentest findings — ADP-SPEC-026) ──────────────────
    # Applied to every response to prevent MIME sniffing and cross-origin reads.
    _SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # ADP-blp.11: browsers that have seen the site over HTTPS keep using HTTPS. Ignored
        # over plain HTTP, so local development is unaffected.
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    def _apply_security_headers(request: Request, response: Response) -> None:
        response.headers.update(_SECURITY_HEADERS)
        # ADP-blp.11: a Content-Security-Policy limits what an injected script could do. Not on
        # the Keycloak pages relayed under /auth (Keycloak sets its own policy for its login
        # theme), and never over a policy a response already carries.
        policy = _content_security_policy()
        if (
            policy
            and not request.url.path.startswith("/auth/")
            and "content-security-policy" not in response.headers
        ):
            response.headers["Content-Security-Policy"] = policy

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> Response:
        """Catch-all handler: return generic 500 without exposing stack traces."""
        import logging as _logging
        _logging.getLogger("adp.api").error(
            "Unhandled exception on %s %s: %s", request.method, request.url.path, exc,
            exc_info=True,
        )
        resp = Response(
            content='{"detail":"An unexpected error occurred."}',
            status_code=500,
            media_type="application/json",
        )
        _apply_security_headers(request, resp)
        return resp

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next) -> Response:  # type: ignore[type-arg]
        """Combined observability + security headers middleware (ADP-SPEC-012 / ADP-SPEC-026).

        Order of operations:
        1. Extract/generate trace ID → set ContextVar (FR-002 / QG-10)
        2. Track active request count (saturation metric)
        3. Time the request, record latency and status (rate/error/duration metrics)
        4. Inject security headers on every response
        5. Return X-Trace-ID header in response
        """
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()
        set_trace_id(trace_id)

        ACTIVE_REQUESTS.inc()
        t0 = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            ERROR_COUNTER.labels(route=_metric_route(request)).inc()
            ACTIVE_REQUESTS.dec()
            raise
        else:
            route = _metric_route(request)
            elapsed = time.monotonic() - t0
            status_str = str(response.status_code)
            method = request.method
            REQUEST_COUNTER.labels(method=method, route=route, status=status_str).inc()
            REQUEST_LATENCY.labels(route=route).observe(elapsed)
            if response.status_code >= 400:
                ERROR_COUNTER.labels(route=route).inc()
            ACTIVE_REQUESTS.dec()
            response.headers["X-Trace-ID"] = trace_id
            _apply_security_headers(request, response)
            return response

    app.include_router(me_router)
    app.include_router(designs.router)
    app.include_router(layouts.router)
    app.include_router(theme.router)
    app.include_router(render.router)
    app.include_router(documents.router)
    app.include_router(export_router.router)
    app.include_router(health.router)
    app.include_router(intake.router)
    app.include_router(recommend.router)
    app.include_router(validate.router)
    app.include_router(ai_process.router)
    app.include_router(knowledge.router)
    app.include_router(calm.router)
    app.include_router(governance.router)
    app.include_router(lifecycle.router)
    app.include_router(portfolio.router)
    app.include_router(reasoning.router)
    app.include_router(tags.router)
    app.include_router(elements.router)
    app.include_router(config.router)
    # 940-org-units-geography: before the business router (both under /api/v1/business).
    app.include_router(organization_router_module.router)
    # 947 GEO-02: legal entities and typed geography links (two routers, never nested).
    app.include_router(organization_links_router_module.router)
    app.include_router(organization_links_router_module.applications_router)
    app.include_router(business_router_module.router)
    # Split out of the business router (ADP-blp.27); same prefix, registered straight after it.
    app.include_router(business_agent_review_router_module.router)
    app.include_router(business_value_chains_router_module.router)
    app.include_router(search.router)
    app.include_router(applications_router)
    app.include_router(tech_caps_router)
    app.include_router(app_capabilities_router.router)
    app.include_router(integrations_router)
    app.include_router(initiatives_router)
    app.include_router(chat_router_module.router)
    app.include_router(auth_proxy.router)
    app.include_router(admin_prompts_router.router)
    app.include_router(admin_rubrics_router.router)
    app.include_router(diagrams_router.router)
    app.include_router(strategy_router.router)
    app.include_router(compliance_router_module.router)
    # 948 GEO-03: framework jurisdiction and derived applicability (same prefix, not nested).
    app.include_router(compliance_applicability_router_module.router)
    app.include_router(agentic_router_module.router)
    # 936: adoption routes first, so /adoptions and /evaluate are never taken as a {key}.
    app.include_router(pattern_adoptions_router_module.router)
    app.include_router(patterns_router_module.router)

    # Serve Vite-built frontend static files when running in Docker (ADP-SPEC-025)
    import os
    static_dir = os.environ.get("ADP_STATIC_DIR", "")
    if static_dir and os.path.isdir(static_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
