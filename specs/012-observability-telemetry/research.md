# Research: Observability & Telemetry

**Branch**: `012-observability-telemetry` | **Date**: 2026-07-02

---

## Decision 1: Structured Logging Approach — stdlib Filter vs structlog

**Decision**: Use `logging.Filter` injected into the root `logging.Logger` to add `trace_id` to every log record automatically. No new dependency. The filter reads the trace ID from a `contextvars.ContextVar` and attaches it to every `LogRecord`.

**Rationale**: The project already uses `logging.getLogger(__name__)` throughout all modules (ADP-SPEC-003 through ADP-SPEC-011). Introducing `structlog` at this stage would require updating every module's logging calls. A `logging.Filter` works with the existing call sites and adds trace_id transparently. The filter also enforces JSON formatting for all output via a custom `logging.Formatter`.

**Alternatives considered**:
- `structlog` — cleaner API but requires adopting a new logging pattern across all existing modules; deferred to v2
- `python-json-logger` — thin JSON formatter library; provides similar JSON output with less boilerplate; considered but stdlib is sufficient and zero-dep is preferred

---

## Decision 2: Metrics Library — prometheus-client vs OTel Metrics

**Decision**: Use `prometheus-client>=0.17` for the metrics endpoint (`GET /metrics`). This provides a Prometheus-compatible `/metrics` scrape endpoint with minimal setup.

**Rationale**: The OTel metrics API (already in stack via `opentelemetry-sdk`) requires an exporter to push to a collector; it does not natively produce a scrape endpoint. Adding a Prometheus exporter (`opentelemetry-exporter-prometheus`) would also add a dependency. `prometheus-client` is the de-facto Python Prometheus library, widely understood, and produces a standard scrape format that works with any Prometheus-compatible observability stack. The project already uses OTel SDK for tracing; using `prometheus-client` for metrics is a practical split that avoids collector complexity in v1.

**Alternatives considered**:
- `opentelemetry-exporter-prometheus` — consistent OTel stack but adds another dep and requires a collector or push gateway; deferred to v2
- Custom JSON metrics endpoint — non-standard; tools wouldn't scrape it automatically; rejected

---

## Decision 3: Correlation ID Carrier — ContextVar vs Threading.local

**Decision**: Use `contextvars.ContextVar[str]` (Python stdlib, Python 3.7+) as the in-process carrier for the trace/correlation ID. HTTP ingress reads the `X-Trace-ID` header (or generates a new UUID4 if absent) and sets the ContextVar. All subsequent logging and span creation within that async context reads from it.

**Rationale**: `contextvars.ContextVar` is the correct choice for async Python (asyncio/FastAPI) — it is propagated automatically through `asyncio.Task` boundaries and does not leak between concurrent requests the way `threading.local` does. The OpenTelemetry SDK also uses ContextVar internally for span context propagation.

**Alternatives considered**:
- `threading.local` — incorrect for async code; would leak between concurrent requests; rejected
- OTel `context.get_current()` — provides the OTel trace context object but is heavier; our ContextVar simply mirrors the OTel trace ID into logging for zero-overhead extraction

---

## Decision 4: AI Step Span Helper — Context Manager vs Decorator

**Decision**: Implement `ai_step_span()` as a `@contextmanager` function in `adp.telemetry.spans`. Callers wrap their AI step body with `with ai_step_span(step_name) as span:` and call `span.set_attribute(SPAN_ATTR_KNOWLEDGE_ITEM_IDS, ids)` etc. at the end of the step.

**Rationale**: A context manager is more flexible than a decorator for the existing AI orchestration code in ADP-SPEC-006/007/008, which uses LangGraph node functions. Decorating LangGraph nodes is complex; wrapping the inner logic with a `with` block requires minimal changes. The context manager also handles error-status span emission automatically (catches exceptions, sets ERROR status, re-raises).

**Span attribute truncation**: Values exceeding 1024 characters are truncated with `...[truncated]` suffix to prevent oversized span payloads. This is enforced by a `_truncate(v: str, max_len: int = 1024) -> str` utility in `adp.telemetry.spans`.

**Alternatives considered**:
- Decorator (`@ai_step(step_name)`) — cleaner API for simple functions but incompatible with LangGraph node signature requirements; rejected for v1
- Inline span creation at each call site — already done in ADP-SPEC-006/007/008 but inconsistently; replaced by the shared helper

---

## Decision 5: Span Attribute Naming Convention

**Decision**: Use `adp.` prefix for all ADP-specific span attributes. Standard OTel semantic conventions (e.g., `http.method`, `http.status_code`) are used where applicable.

**ADP-specific attributes for AI steps:**

| Attribute | Type | Notes |
|---|---|---|
| `adp.step_name` | string | LangGraph node name (e.g., `"retrieve"`, `"generate"`, `"rank"`) |
| `adp.input_tokens` | int | Token count of the prompt sent to LLM |
| `adp.output_tokens` | int | Token count of the LLM response |
| `adp.estimated_cost_usd` | float | `(input_tokens * input_rate + output_tokens * output_rate)` |
| `adp.latency_ms` | int | Wall-clock time for the step in milliseconds |
| `adp.knowledge_item_ids` | string | JSON array of cited knowledge item IDs (serialized list) |
| `adp.design_id` | string | Design being processed (ID only — never design content) |
| `adp.operation_id` | string | Operation ID for the outer request |

**Rationale**: The `adp.` prefix prevents collisions with standard OTel attributes. Serializing `knowledge_item_ids` as a JSON string in a single attribute (rather than as repeated attributes) avoids OTel attribute list limitations in some exporters.

---

## Decision 6: Health Endpoint Design

**Decision**: Add `GET /health` returning JSON `{"status": "healthy"|"unhealthy", "version": "..."}` and `GET /metrics` (Prometheus scrape format) as two new FastAPI routes in `src/adp/api/routers/health.py`.

**Health status logic**: `healthy` if the FastAPI process is running and has no detected critical dependency failures. `unhealthy` with `reason` during startup or if a required dependency check fails. v1 does no deep health checks (no DB ping) — just liveness. Readiness checks (DB, etc.) are v2.

**Rationale**: Keeping health and metrics in one router file keeps the app.py registrations clean. No new framework — pure FastAPI + `prometheus-client`.

---

## Decision 7: Migration of Existing AI Step Spans

**Decision**: The existing AI step telemetry in ADP-SPEC-006/007/008 uses ad-hoc attribute names (e.g., via individual `span.set_attribute()` calls in `intake/telemetry.py`, `recommendation/telemetry.py`, `validation/telemetry.py`). This spec creates the canonical constants in `adp.telemetry.contract`. The existing telemetry files should be updated to import from `adp.telemetry.contract` rather than using hard-coded strings.

**Scope**: Update existing `telemetry.py` files in `adp.intake`, `adp.recommendation`, `adp.validation` to use `adp.telemetry.contract` attribute constants. This is a refactor (not a new feature) within the scope of this spec.

---

## Summary of New Dependencies

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `prometheus-client` | `>=0.17` | Metrics scrape endpoint (`GET /metrics`) | `pyproject.toml` |

All other requirements use the existing `opentelemetry-sdk` and Python stdlib (`contextvars`, `logging`).
