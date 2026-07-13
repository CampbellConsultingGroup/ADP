# Data Model: Observability & Telemetry

**Branch**: `012-observability-telemetry` | **Date**: 2026-07-02
**Sources**: `spec.md`, `research.md`

---

## Python Entities (Pydantic v2, `extra="forbid"`)

### `HealthStatus`

Response body for `GET /health`.

| Field | Type | Notes |
|---|---|---|
| `status` | `Literal["healthy", "unhealthy"]` | Current liveness state |
| `reason` | `str \| None` | Human-readable reason when `unhealthy`; `None` when healthy |
| `version` | `str` | Service version (e.g., `"0.1.0"`) |

### `AiStepSpanAttributes`

The complete set of required attributes for an AI orchestration step span. Used as a typed record to enforce completeness before span emission — not persisted.

| Field | Type | Notes |
|---|---|---|
| `step_name` | `str` | LangGraph node name (e.g., `"retrieve"`, `"generate"`, `"rank"`) |
| `input_tokens` | `int` | Prompt token count |
| `output_tokens` | `int` | Response token count |
| `estimated_cost_usd` | `float` | `(input_tokens × in_rate + output_tokens × out_rate)` |
| `latency_ms` | `int` | Wall-clock duration of the step in milliseconds |
| `knowledge_item_ids` | `list[str]` | Cited knowledge item IDs; empty list if step cites none |
| `design_id` | `str \| None` | Design being processed (ID only; never design content) |
| `operation_id` | `str \| None` | Outer operation ID |

---

## Telemetry Contract Constants

### Span Attribute Names (`adp.telemetry.contract`)

```python
# AI step span attributes (FR-003)
SPAN_ATTR_STEP_NAME = "adp.step_name"
SPAN_ATTR_INPUT_TOKENS = "adp.input_tokens"
SPAN_ATTR_OUTPUT_TOKENS = "adp.output_tokens"
SPAN_ATTR_ESTIMATED_COST_USD = "adp.estimated_cost_usd"
SPAN_ATTR_LATENCY_MS = "adp.latency_ms"
SPAN_ATTR_KNOWLEDGE_ITEM_IDS = "adp.knowledge_item_ids"  # JSON-serialized list
SPAN_ATTR_DESIGN_ID = "adp.design_id"
SPAN_ATTR_OPERATION_ID = "adp.operation_id"
SPAN_ATTR_ERROR_TYPE = "error.type"    # OTel semantic convention
SPAN_ATTR_ERROR_MSG  = "error.message" # OTel semantic convention

# Service span attributes (HTTP)
SPAN_ATTR_HTTP_METHOD = "http.method"       # OTel semantic convention
SPAN_ATTR_HTTP_ROUTE  = "http.route"        # OTel semantic convention
SPAN_ATTR_HTTP_STATUS = "http.status_code"  # OTel semantic convention
```

### Log Field Names (`adp.telemetry.contract`)

```python
LOG_FIELD_TRACE_ID  = "trace_id"   # FR-001: required on every log line
LOG_FIELD_EVENT     = "event"      # Human-readable message (no sensitive content)
LOG_FIELD_LEVEL     = "level"      # "DEBUG"|"INFO"|"WARNING"|"ERROR"|"CRITICAL"
LOG_FIELD_TIMESTAMP = "timestamp"  # ISO 8601 UTC
LOG_FIELD_MODULE    = "module"     # Python module name
```

### Metric Names (`adp.telemetry.contract`)

```python
# Prometheus metric names (FR-004)
METRIC_REQUEST_TOTAL   = "adp_request_total"              # Counter
METRIC_ERROR_TOTAL     = "adp_error_total"                # Counter
METRIC_REQUEST_LATENCY = "adp_request_latency_seconds"    # Histogram
METRIC_SATURATION      = "adp_active_requests"            # Gauge (active request count)

# AI step metrics
METRIC_AI_TOKENS_INPUT  = "adp_ai_input_tokens_total"    # Counter
METRIC_AI_TOKENS_OUTPUT = "adp_ai_output_tokens_total"   # Counter
METRIC_AI_COST_USD      = "adp_ai_estimated_cost_usd_total"  # Counter
```

---

## Context Variable

```python
# adp.telemetry.context
_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")
```

- Set at request ingress: extracted from `X-Trace-ID` header or generated as `uuid.uuid4().hex`
- Read by the `TraceIdFilter` logging filter to inject into every log record
- Read by `ai_step_span()` to set as `adp.trace_id` attribute on AI spans

---

## Logging Filter

```python
class TraceIdFilter(logging.Filter):
    """Injects trace_id from ContextVar into every log record (FR-001 / FR-002)."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "no-trace"
        return True
```

Installed once at application startup on the root logger. Ensures every log line from every module carries `trace_id`.

---

## Relationships to Existing Code

| New Entity | Existing Code | Notes |
|---|---|---|
| `adp.telemetry.contract` constants | `adp.intake.telemetry`, `adp.recommendation.telemetry`, `adp.validation.telemetry` | Those modules will import constants from here (refactor in scope of this spec) |
| `ContextVar("trace_id")` | `src/adp/api/app.py` correlation middleware | Middleware sets the ContextVar; existing `correlation_id` in app.py will be unified with this |
| `GET /health` | `src/adp/api/app.py` | New router registered in `create_app()` |
| `prometheus-client` Counters/Histograms | `src/adp/api/app.py` | Request metrics collected via FastAPI middleware |
| `AiStepSpanAttributes` | Every LangGraph node in ADP-SPEC-006/007/008 | Used for type-safe attribute emission |
