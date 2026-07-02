# Implementation Plan: Observability & Telemetry

**Branch**: `012-observability-telemetry` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-observability-telemetry/spec.md`

## Summary

Build the telemetry infrastructure that makes every ADP code path observable. The core deliverable is the `adp.telemetry` package, which defines: (1) canonical span attribute names and metric names as Python constants, (2) a `TraceIdFilter` logging filter that injects the current trace ID into every log line, (3) an `ai_step_span()` context manager that guarantees all AI orchestration spans carry the full required attribute set, and (4) Prometheus metrics collection. Two new FastAPI endpoints (`GET /health`, `GET /metrics`) complete the service observability surface. Existing AI telemetry in ADP-SPEC-006/007/008 is normalized to use the new constants. The CI regression guard (`test_no_sensitive_data.py`) enforces QG-08.

**Cross-cutting nature**: This spec touches `adp.intake`, `adp.recommendation`, and `adp.validation` to normalize attribute names. It also adds middleware to `adp.api.app`. No new APIs are exposed except `/health` and `/metrics`.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `prometheus-client>=0.17` (new, metrics endpoint); `opentelemetry-sdk>=1.25` (already in stack, for spans); Python stdlib `contextvars`, `logging`, `uuid` (no new deps for trace ID or logging)
**Storage**: No persistence; telemetry is write-only (emit-and-forget); correlation IDs live only in `ContextVar` for the duration of a request
**Testing**: `pytest` (existing); `logging.handlers.MemoryHandler` or `caplog` for log capture in tests
**Target Platform**: Linux/WSL (same as existing)
**Project Type**: Internal library extension (new `adp.telemetry` package) + two new FastAPI routes + cross-cutting logging middleware
**Performance Goals**: Telemetry overhead ≤ 50ms per request (NFR-001 / SC-002); health endpoint response ≤ 2s (SC-004)
**Constraints**: No design content in logs or spans (FR-006 / QG-08); trace ID on every log line (FR-001 / QG-10); all AI steps emit spans (FR-003 / QG-11)
**Scale/Scope**: In-process telemetry only; telemetry collection backend is operator-configured (out of scope for v1)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references ADP-SPEC-012 task IDs | ✅ Will be enforced |
| QG-03 | ART-III, ART-XIII | `HealthStatus` Pydantic model; span attributes are typed constants; metric names are string constants | ✅ Planned |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ TDD planned |
| QG-05 | ART-IV, ART-XIII | Contract tests for `/health` and `/metrics` endpoints | ✅ Planned |
| QG-06 | ART-V | `ruff check` clean | ✅ No new SAST surface |
| QG-07 | ART-V | `prometheus-client` has no known high/critical CVEs | ✅ Verify at `pip-audit` time |
| QG-08 | ART-V | **This spec IS QG-08**: `test_no_sensitive_data.py` CI gate enforces zero secret/sensitive-data leakage in logs and spans | ✅ Core deliverable |
| QG-10 | ART-VI | **This spec IS QG-10**: `TraceIdFilter` ensures trace_id on every log line; tested in `test_trace_id_in_logs.py` | ✅ Core deliverable |
| QG-11 | ART-VI | **This spec IS QG-11**: `ai_step_span()` ensures all AI steps emit spans with required attributes; tested in `test_ai_step_span.py` | ✅ Core deliverable |
| QG-18 | ART-II, ART-XIV | No new generated schemas; `adp-generate --check` unaffected | ✅ N/A |

**Constitution Alignment**: ART-VI is the central article. QG-08, QG-10, and QG-11 are the three blocking CI gates this feature implements. All three require buildable test infrastructure, not just policy.

**N/A gates**: QG-09, QG-12–QG-17 — no consequential actions, no LLM, no validation gating, no new model elements.

## Project Structure

### Documentation (this feature)

```text
specs/012-observability-telemetry/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── telemetry-contract.md   # Span attribute names, log fields, metric names
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
src/adp/telemetry/
├── __init__.py
├── contract.py    # Canonical span attribute names, log field names, metric names (constants only)
├── context.py     # ContextVar("trace_id"); get_trace_id(); set_trace_id(); TraceIdFilter
├── spans.py       # ai_step_span(step_name) context manager; _truncate() helper
└── metrics.py     # prometheus-client Counter/Histogram/Gauge registration; MetricsMiddleware

src/adp/api/routers/
└── health.py      # GET /health (HealthStatus response), GET /metrics (Prometheus scrape)

src/adp/api/
└── app.py         # (modified) register health router; install TraceIdFilter on root logger;
                   # add X-Trace-ID middleware (set ContextVar; return X-Trace-ID in response)

# Normalized to use adp.telemetry.contract constants:
src/adp/intake/telemetry.py
src/adp/recommendation/telemetry.py
src/adp/validation/telemetry.py

tests/
├── unit/
│   ├── test_telemetry_contract.py     # Constants exist; no duplicate values
│   ├── test_trace_id_context.py       # ContextVar set/get; TraceIdFilter injects trace_id
│   ├── test_ai_step_span.py           # ai_step_span() emits all required attributes
│   ├── test_no_sensitive_data.py      # QG-08 regression guard
│   └── test_health_metrics.py         # (optional — also covered by contract tests)
└── contract/
    └── test_health_api.py             # GET /health and GET /metrics contract tests
```

**Structure Decision**: New package `adp.telemetry` with four focused modules. No new project or service. Three existing `telemetry.py` files get import updates. The only change to existing API code is in `app.py` (register router + install filter).

## New Dependencies

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `prometheus-client` | `>=0.17` | Prometheus metrics scrape endpoint | `pyproject.toml` |
