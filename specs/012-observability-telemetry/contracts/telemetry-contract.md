# Contract: Telemetry Data Contract

**Module**: `src/adp/telemetry/contract.py`
**Date**: 2026-07-02
**Status**: Normative for all service-bearing specs

This is the canonical telemetry contract that every ADP service and AI step MUST satisfy. All span attribute names, log field names, and metric names are defined here as Python constants. Other modules MUST import from this file rather than using hard-coded strings.

---

## Structured Log Line Schema (FR-001)

Every log line emitted by ADP MUST be valid JSON with at minimum these fields:

```json
{
  "timestamp": "2026-07-02T12:34:56.789Z",
  "level": "INFO",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "event": "recommendation.retrieve.complete",
  "module": "adp.recommendation.orchestrator"
}
```

**Prohibited content** (FR-006):
- API keys, Bearer tokens, passwords, private keys
- Raw design content: element names, requirement descriptions, AI prompt text, AI response text
- Only metadata is permitted: IDs, counts, lengths, latencies, boolean flags

---

## AI Step Span Requirements (FR-003)

Every AI orchestration step (LangGraph node in recommendation or validation pipeline) MUST emit a span with ALL of the following attributes:

| Attribute Name | Type | Required | Permitted to be empty |
|---|---|---|---|
| `adp.step_name` | string | Yes | No |
| `adp.input_tokens` | int | Yes | No (0 if not applicable) |
| `adp.output_tokens` | int | Yes | No (0 if not applicable) |
| `adp.estimated_cost_usd` | float | Yes | No (0.0 if not applicable) |
| `adp.latency_ms` | int | Yes | No |
| `adp.knowledge_item_ids` | string (JSON array) | Yes | Yes (empty array `"[]"`) |
| `adp.design_id` | string | No | Yes |
| `adp.operation_id` | string | No | Yes |

**Error spans**: When a step raises an exception, the span MUST also carry:
- `error.type`: the exception class name
- `error.message`: the exception message (truncated to 256 chars)
- Span status: ERROR

**Truncation rule**: Any string attribute value exceeding 1024 characters MUST be truncated to 1021 characters plus `"..."` suffix.

---

## Health Endpoint Contract

**Endpoint**: `GET /health`
**Auth**: None required (health checks must be unauthenticated)
**Response 200**:
```json
{
  "status": "healthy",
  "reason": null,
  "version": "0.1.0"
}
```
**Response 200** (degraded):
```json
{
  "status": "unhealthy",
  "reason": "Database connection pool exhausted",
  "version": "0.1.0"
}
```

Note: Health endpoint always returns HTTP 200 with structured JSON. Liveness probes distinguish healthy/unhealthy by inspecting the `status` field, not the HTTP status code. This prevents retry storms when a service reports unhealthy.

---

## Metrics Endpoint Contract

**Endpoint**: `GET /metrics`
**Auth**: None required (metrics are not sensitive — they contain only counters and latencies, never content)
**Response**: Prometheus text format (Content-Type: `text/plain; version=0.0.4; charset=utf-8`)

Required metrics:

```
# HELP adp_request_total Total number of requests received
# TYPE adp_request_total counter
adp_request_total{method="POST",route="/api/v1/designs",status="200"} 42.0

# HELP adp_error_total Total number of errors
# TYPE adp_error_total counter
adp_error_total{route="/api/v1/designs"} 1.0

# HELP adp_request_latency_seconds Request latency in seconds
# TYPE adp_request_latency_seconds histogram
adp_request_latency_seconds_bucket{le="0.1",...} ...

# HELP adp_active_requests Number of requests currently being processed
# TYPE adp_active_requests gauge
adp_active_requests 3.0

# HELP adp_ai_input_tokens_total Total AI input tokens consumed
# TYPE adp_ai_input_tokens_total counter
adp_ai_input_tokens_total{step="retrieve"} 15420.0

# HELP adp_ai_output_tokens_total Total AI output tokens produced
# TYPE adp_ai_output_tokens_total counter
adp_ai_output_tokens_total{step="generate"} 8930.0

# HELP adp_ai_estimated_cost_usd_total Total estimated AI cost in USD
# TYPE adp_ai_estimated_cost_usd_total counter
adp_ai_estimated_cost_usd_total 0.842
```

---

## Compliance Test Requirements

The following tests MUST pass in CI (QG-08, QG-10, QG-11):

1. **`test_no_secrets_in_logs`** (QG-08): Run the full recommendation pipeline with a known credential in the environment; capture all log output; assert zero matches for secret patterns (`api_key=`, `Bearer `, `password=`, `secret=`).

2. **`test_ai_span_has_required_attributes`** (QG-11): For each AI step span emitted during a test run, assert all required attributes are present with non-None values.

3. **`test_trace_id_in_every_log_line`** (QG-10): For each log line emitted during a traced request, assert `trace_id` field is present and matches the expected trace ID.

4. **`test_health_endpoint_returns_200`**: `GET /health` returns 200 with `status` field.

5. **`test_metrics_endpoint_has_required_metrics`**: `GET /metrics` response contains all required metric names.
