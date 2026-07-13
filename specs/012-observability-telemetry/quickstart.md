# Quickstart: Observability & Telemetry

**Branch**: `012-observability-telemetry` | **Date**: 2026-07-02
**Prerequisites**: ADP backend running; any request in flight

---

## Tracing a Request

Every request automatically gets a trace ID. You can inject your own with the `X-Trace-ID` header:

```bash
curl -X POST http://localhost:8000/api/v1/designs/D-001/render \
  -H "Authorization: Bearer $ADP_TOKEN" \
  -H "X-Trace-ID: my-trace-abc123" \
  -H "Content-Type: application/json" \
  -d '{"level": "container"}'
```

All log lines and spans emitted during this request carry `trace_id: "my-trace-abc123"`.

---

## Reading Structured Logs

Every log line is JSON:

```json
{"timestamp":"2026-07-02T12:34:56Z","level":"INFO","trace_id":"my-trace-abc123","event":"render.start","module":"adp.api.routers.render","design_id":"D-001"}
{"timestamp":"2026-07-02T12:34:56Z","level":"INFO","trace_id":"my-trace-abc123","event":"export.start","module":"adp.export.bundle","design_id":"D-001","actor":"user@example.com"}
```

Notice: no design content, no credentials, only metadata.

---

## Instrumenting an AI Step

Use the `ai_step_span` context manager in any AI orchestration function:

```python
from adp.telemetry.spans import ai_step_span
from adp.telemetry.contract import SPAN_ATTR_KNOWLEDGE_ITEM_IDS

async def retrieve_step(state: dict) -> dict:
    with ai_step_span("retrieve") as span:
        results = await knowledge_retrieval.hybrid_search(query)
        item_ids = [r["item_id"] for r in results]

        # Set AI-step-specific attributes
        span.set_attribute(SPAN_ATTR_KNOWLEDGE_ITEM_IDS, str(item_ids))
        span.set_attribute("adp.input_tokens", len(query.split()))
        span.set_attribute("adp.output_tokens", 0)  # retrieval has no LLM output
        span.set_attribute("adp.estimated_cost_usd", 0.0)

    return {**state, "knowledge_items": results}
```

The context manager automatically:
- Sets `adp.step_name = "retrieve"`
- Records `adp.latency_ms` at completion
- Sets span status to ERROR on exception and re-raises

---

## Checking Service Health

```bash
curl http://localhost:8000/health
# {"status": "healthy", "reason": null, "version": "0.1.0"}
```

---

## Checking Metrics

```bash
curl http://localhost:8000/metrics
```

Output (Prometheus format):
```
# HELP adp_request_total Total number of requests received
# TYPE adp_request_total counter
adp_request_total{method="POST",route="/api/v1/designs",status="200"} 15.0
adp_request_total{method="GET",route="/api/v1/designs/{id}/document",status="200"} 3.0

# HELP adp_request_latency_seconds Request latency in seconds
# TYPE adp_request_latency_seconds histogram
adp_request_latency_seconds_sum 4.21
adp_request_latency_seconds_count 18.0
...
```

---

## Verifying No Secret Leakage (CI)

The secret scan runs automatically. To run locally:

```bash
python3 -m pytest tests/unit/test_no_sensitive_data.py -v
```

This test:
1. Captures all log output during a full recommendation pipeline run
2. Greps for patterns: `api_key=`, `Bearer `, `password=`, `secret=`, `private_key`
3. Asserts zero matches

---

## No-Trace Scenario

If no `X-Trace-ID` header is provided, a UUID4 trace ID is generated automatically:

```bash
curl http://localhost:8000/health
# Log line: {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "event": "health.check", ...}
```

The generated trace ID is also returned in the response header `X-Trace-ID` so callers can use it for support queries.
