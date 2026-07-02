# Tasks: Observability & Telemetry

**Input**: Design documents from `/specs/012-observability-telemetry/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). This spec implements three blocking CI quality gates: QG-08 (no-leak), QG-10 (trace ID in logs), QG-11 (AI step spans). Test tasks MUST appear before implementation tasks and MUST fail first.

**Note**: Cross-cutting spec. New package `adp.telemetry`; updates to `adp.api.app`; normalization of `adp.intake.telemetry`, `adp.recommendation.telemetry`, `adp.validation.telemetry`; one new router `src/adp/api/routers/health.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup

**Purpose**: Install new dependency, create package skeleton

- [X] T001 Add `prometheus-client>=0.17` to `pyproject.toml` dependencies section; install with `pip install prometheus-client --break-system-packages`; verify `python3 -c "import prometheus_client; print(prometheus_client.__version__)"` succeeds
- [X] T002 [P] Create `src/adp/telemetry/__init__.py` as empty package marker

**Checkpoint**: `python3 -c "import prometheus_client, adp.telemetry; print('ok')"` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Canonical telemetry contract constants — ALL user stories depend on these names

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create `src/adp/telemetry/contract.py` with ALL canonical telemetry constants (no logic, no imports — constants only):
  - AI step span attributes: `SPAN_ATTR_STEP_NAME = "adp.step_name"`, `SPAN_ATTR_INPUT_TOKENS = "adp.input_tokens"`, `SPAN_ATTR_OUTPUT_TOKENS = "adp.output_tokens"`, `SPAN_ATTR_ESTIMATED_COST_USD = "adp.estimated_cost_usd"`, `SPAN_ATTR_LATENCY_MS = "adp.latency_ms"`, `SPAN_ATTR_KNOWLEDGE_ITEM_IDS = "adp.knowledge_item_ids"`, `SPAN_ATTR_DESIGN_ID = "adp.design_id"`, `SPAN_ATTR_OPERATION_ID = "adp.operation_id"`, `SPAN_ATTR_ERROR_TYPE = "error.type"`, `SPAN_ATTR_ERROR_MSG = "error.message"`
  - Log field names: `LOG_FIELD_TRACE_ID = "trace_id"`, `LOG_FIELD_EVENT = "event"`, `LOG_FIELD_LEVEL = "level"`, `LOG_FIELD_TIMESTAMP = "timestamp"`, `LOG_FIELD_MODULE = "module"`
  - Metric names: `METRIC_REQUEST_TOTAL = "adp_request_total"`, `METRIC_ERROR_TOTAL = "adp_error_total"`, `METRIC_REQUEST_LATENCY = "adp_request_latency_seconds"`, `METRIC_SATURATION = "adp_active_requests"`, `METRIC_AI_TOKENS_INPUT = "adp_ai_input_tokens_total"`, `METRIC_AI_TOKENS_OUTPUT = "adp_ai_output_tokens_total"`, `METRIC_AI_COST_USD = "adp_ai_estimated_cost_usd_total"`
  - `MAX_SPAN_ATTR_LEN: int = 1024` — truncation threshold

**Checkpoint**: `python3 -c "from adp.telemetry.contract import SPAN_ATTR_STEP_NAME, METRIC_REQUEST_TOTAL; print('contract ok')"` succeeds

---

## Phase 3: User Story 1 — Trace a Request End-to-End (Priority: P1) 🎯 MVP

**Goal**: Every log line carries a `trace_id`; AI step spans carry all required attributes; incoming `X-Trace-ID` header is propagated or a new ID is generated and returned.

**Independent Test**: Set a trace ID via `set_trace_id("abc")`; emit a log line; assert the log record has `trace_id == "abc"`; call `ai_step_span("test_step")` and set required attributes; assert span has all required attributes.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [P] [US1] Write failing `test_set_get_trace_id()` and `test_trace_id_filter_injects_trace_id()` in `tests/unit/test_trace_id_context.py`: (a) call `set_trace_id("abc123")`; call `get_trace_id()`; assert returns `"abc123"`; (b) install `TraceIdFilter` on a fresh `logging.Logger`; set trace_id to `"test-trace-001"`; emit a log record using `caplog`; assert `caplog.records[0].trace_id == "test-trace-001"` (QG-10 regression guard)
- [X] T005 [P] [US1] Write failing `test_ai_step_span_emits_required_attributes()` in `tests/unit/test_ai_step_span.py`: use `opentelemetry.sdk.trace` in-memory exporter (`InMemorySpanExporter`); call `ai_step_span("retrieve")` context manager; inside, set `SPAN_ATTR_INPUT_TOKENS=10`, `SPAN_ATTR_OUTPUT_TOKENS=5`, `SPAN_ATTR_ESTIMATED_COST_USD=0.001`, `SPAN_ATTR_KNOWLEDGE_ITEM_IDS='["K-001"]'`; after exiting, assert the exported span has all these attributes plus `SPAN_ATTR_STEP_NAME == "retrieve"` and `SPAN_ATTR_LATENCY_MS >= 0` (QG-11 regression guard)
- [X] T006 [P] [US1] Write failing `test_ai_step_span_sets_error_status_on_exception()` in `tests/unit/test_ai_step_span.py`: use in-memory exporter; call `ai_step_span("generate")` and raise `ValueError("test error")` inside; assert span status is `StatusCode.ERROR`; assert span has attribute `error.type == "ValueError"` and `error.message` contains "test error"; assert the exception propagates out of the context manager
- [X] T007 [P] [US1] Write failing `test_x_trace_id_header_propagated()` in `tests/contract/test_health_api.py`: make `GET /health` with header `X-Trace-ID: my-trace-abc`; assert the response has header `X-Trace-ID: my-trace-abc`; make `GET /health` without `X-Trace-ID` header; assert the response has a non-empty `X-Trace-ID` header with a UUID-like value (new ID generated)

### Implementation for User Story 1

- [X] T008 [US1] Create `src/adp/telemetry/context.py` with: `_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")`; `get_trace_id() -> str` (returns current value or empty string); `set_trace_id(tid: str) -> None`; `generate_trace_id() -> str` (returns `uuid.uuid4().hex`); `class TraceIdFilter(logging.Filter)` with `filter(self, record) -> bool` that sets `record.trace_id = get_trace_id() or "no-trace"` and returns `True`; verify T004 passes
- [X] T009 [US1] Create `src/adp/telemetry/spans.py` with: `_truncate(v: str, max_len: int = MAX_SPAN_ATTR_LEN) -> str` (truncates at max_len-3 and appends `"..."`); `@contextmanager def ai_step_span(step_name: str, *, design_id: str | None = None, operation_id: str | None = None) -> Generator[Span, None, None]` that (1) starts an OTel span named `f"adp.{step_name}"`, (2) sets `SPAN_ATTR_STEP_NAME`, `SPAN_ATTR_DESIGN_ID`, `SPAN_ATTR_OPERATION_ID` at entry, (3) records `t0 = time.monotonic()`, (4) on exception: calls `span.record_exception(exc)`, sets `SPAN_ATTR_ERROR_TYPE = type(exc).__name__`, `SPAN_ATTR_ERROR_MSG = _truncate(str(exc), 256)`, sets span status ERROR, re-raises, (5) in finally: sets `SPAN_ATTR_LATENCY_MS = int((time.monotonic() - t0) * 1000)`; import all attribute names from `adp.telemetry.contract`; verify T005 and T006 pass
- [X] T010 [US1] Add X-Trace-ID middleware and logging setup to `src/adp/api/app.py`: in `create_app()`, (1) install `TraceIdFilter` on `logging.getLogger()` (root logger) so every log record gets `trace_id`, (2) add an `@app.middleware("http")` starlette middleware that extracts `X-Trace-ID` from request headers (or calls `generate_trace_id()`), calls `set_trace_id()`, adds `X-Trace-ID` header to the response; import from `adp.telemetry.context`; verify T007 passes

**Checkpoint**: `pytest tests/unit/test_trace_id_context.py tests/unit/test_ai_step_span.py tests/contract/test_health_api.py::test_x_trace_id_header_propagated -v --no-cov` green

---

## Phase 4: User Story 2 — Verify No Sensitive Data in Telemetry (Priority: P1)

**Goal**: CI regression guard proves zero secret patterns in log output; span attribute values are truncated and never contain raw design content; the QG-08 gate is a passing automated test.

**Independent Test**: Run `DocumentGenerator` with `ADP_LLM_API_KEY=sk-test-SENTINEL` in env; capture all log output; assert `"sk-test-SENTINEL"` not in any log message.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US2] Write failing `test_span_attr_truncation()` in `tests/unit/test_ai_step_span.py`: call `_truncate("x" * 2000)`; assert `len(result) == 1024`; assert result.endswith("..."); call `_truncate("short")`; assert result == `"short"` (no truncation for short strings)
- [X] T012 [P] [US2] Write failing `test_no_api_key_in_logs()` in `tests/unit/test_no_sensitive_data.py` (QG-08 CI gate): use `pytest`'s `caplog` fixture at `logging.DEBUG` level; call `DocumentGenerator().generate(design)` (already exercises the logging path); assert no log record's `message`, `getMessage()`, or `trace_id` field contains any of: `"sk-"`, `"Bearer "`, `"password="`, `"api_key="`, `"secret="`
- [X] T013 [P] [US2] Write failing `test_no_design_content_in_span_attrs()` in `tests/unit/test_no_sensitive_data.py`: use OTel in-memory exporter; call `ai_step_span("test")` and inside call `span.set_attribute(SPAN_ATTR_KNOWLEDGE_ITEM_IDS, '["K-001", "K-002"]')`; exit normally; inspect exported span attributes; assert no attribute value contains a raw `ArchitectureDescription` title like `"Integration Test Design"` (i.e., no model content, only IDs)

### Implementation for User Story 2

- [X] T014 [US2] Verify `_truncate()` in `src/adp/telemetry/spans.py` (created in T009) handles the 1024-char truncation correctly; add a code comment in `ai_step_span()`: `# POLICY (FR-006 / QG-08): Never pass design content (names, descriptions, AI prompts) as attribute values. Pass only IDs, counts, lengths, and latencies.`; verify T011 passes (already implemented in T009, just confirm)
- [X] T015 [US2] Finalize `tests/unit/test_no_sensitive_data.py` as the QG-08 CI gate: ensure T012 passes against the live `DocumentGenerator` and `TraceabilityGenerator` (which call `logger.debug/info` internally); if any test fails due to a log containing sensitive content, trace the log call back to its source in `adp.docs.generator` or `adp.docs.traceability` and fix the log message to use only metadata; verify T012–T013 pass

**Checkpoint**: `pytest tests/unit/test_no_sensitive_data.py tests/unit/test_ai_step_span.py::test_span_attr_truncation -v --no-cov` green; QG-08 gate passes

---

## Phase 5: User Story 3 — Monitor Service Health and Metrics (Priority: P2)

**Goal**: `GET /health` returns structured health status in ≤ 2s; `GET /metrics` returns Prometheus format with all required metric names; request counter increments after each request.

**Independent Test**: Call `GET /health`; assert 200 with `status` field. Call `GET /metrics`; assert all required metric names present in response text.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US3] Write failing `test_health_endpoint_returns_200()` in `tests/contract/test_health_api.py`: call `GET /health` via TestClient; assert 200; assert response JSON has `status` and `version` keys; assert `status` in `("healthy", "unhealthy")`
- [X] T017 [P] [US3] Write failing `test_metrics_endpoint_has_required_metrics()` in `tests/contract/test_health_api.py`: call `GET /metrics` via TestClient; assert 200; assert `"adp_request_total"` in response text; assert `"adp_error_total"` in response text; assert `"adp_request_latency_seconds"` in response text; assert `"adp_active_requests"` in response text
- [X] T018 [P] [US3] Write failing `test_request_counter_increments()` in `tests/contract/test_health_api.py`: make `GET /health` once; call `GET /metrics`; capture counter text; make `GET /health` a second time; call `GET /metrics` again; assert the `adp_request_total` value increased

### Implementation for User Story 3

- [X] T019 [US3] Create `src/adp/telemetry/metrics.py`: import `prometheus_client`; define `REQUEST_COUNTER = Counter(METRIC_REQUEST_TOTAL, "...", ["method", "route", "status"])`; `ERROR_COUNTER = Counter(METRIC_ERROR_TOTAL, "...", ["route"])`; `REQUEST_LATENCY = Histogram(METRIC_REQUEST_LATENCY, "...", ["route"])`; `ACTIVE_REQUESTS = Gauge(METRIC_SATURATION, "...")`; `AI_INPUT_TOKENS = Counter(METRIC_AI_TOKENS_INPUT, "...", ["step"])`; `AI_OUTPUT_TOKENS = Counter(METRIC_AI_TOKENS_OUTPUT, "...", ["step"])`; `AI_COST = Counter(METRIC_AI_COST_USD, "...")`; import all metric names from `adp.telemetry.contract`
- [X] T020 [US3] Create `src/adp/api/routers/health.py` with: (a) a `HealthStatus` Pydantic model defined **inline in this file** — `class HealthStatus(BaseModel, extra="forbid"): status: Literal["healthy","unhealthy"]; reason: str | None = None; version: str = "0.1.0"` (3 fields; keep in `health.py` — not in `adp.docs.models` to avoid cross-package coupling between the API layer and the docs layer; I1 remediation); (b) `GET /health` returning `HealthStatus(status="healthy", reason=None)` as JSON; (c) `GET /metrics` returning `prometheus_client.generate_latest()` as `PlainTextResponse` with `media_type="text/plain; version=0.0.4; charset=utf-8"`; register router in `src/adp/api/app.py`; verify T016–T017 pass
- [X] T021 [US3] Add Prometheus metrics middleware to `src/adp/api/app.py`: `@app.middleware("http")` that increments `ACTIVE_REQUESTS` at start, records wall time, on completion calls `REQUEST_COUNTER.labels(method, route, status).inc()` and `REQUEST_LATENCY.labels(route).observe(elapsed)`, on 4xx/5xx calls `ERROR_COUNTER.labels(route).inc()`, always decrements `ACTIVE_REQUESTS`; verify T018 passes

**Checkpoint**: `pytest tests/contract/test_health_api.py -v --no-cov` green; `GET /health` returns structured status; `GET /metrics` returns Prometheus format

---

## Phase 6: User Story 4 — Explicit Failure Surfacing (Priority: P2)

**Goal**: Every exception in the AI step pipeline produces an errored span with `error.type` and `error.message`; no silent catch-and-continue paths; the QG-11 span test also verifies error propagation.

**Independent Test**: Call `ai_step_span("test")` and raise inside; assert ERROR span is emitted and exception propagates.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T022 [P] [US4] Write `test_exception_propagates_from_ai_step_span()` in `tests/unit/test_ai_step_span.py` (verifies FR-005 / no silent swallowing): call `ai_step_span("test")` with `raise RuntimeError("network timeout")` inside; assert `RuntimeError` propagates out; assert `caplog` has an ERROR-level entry mentioning `"RuntimeError"` (the span context manager should log the error before re-raising)
- [X] T023 [P] [US4] Write `test_no_silent_exceptions_in_docs_pipeline()` in `tests/unit/test_no_sensitive_data.py` (verifies FR-005 applies to non-AI code paths too): patch `DocumentGenerator.generate` to raise `ValueError("pipeline error")`; call the generate endpoint or function directly; assert `caplog` has an ERROR-level log with the exception type; assert the exception is NOT swallowed (it propagates or results in a non-200 response)

### Implementation for User Story 4

- [X] T024 [US4] Update `src/adp/telemetry/spans.py` `ai_step_span()` to also emit a structured ERROR log in the except block: `logger.error("ai_step.error", extra={"event": "ai_step.error", "step_name": step_name, "error_type": type(exc).__name__, "trace_id": get_trace_id()})`; this ensures FR-005 (explicit failure surfacing) is satisfied even if the OTel backend is unavailable; verify T022 passes

**Checkpoint**: `pytest tests/unit/test_ai_step_span.py -v --no-cov` all green; every AI step error produces both an errored span AND a structured ERROR log

---

## Phase 7: Polish & Cross-Cutting Normalization

**Purpose**: Normalize existing telemetry files; full test suite; lint; verify CI gates

- [X] T025 [P] Inspect `src/adp/intake/telemetry.py` and replace any hard-coded span attribute strings with imports from `adp.telemetry.contract`; run `pytest tests/intake/ -q --no-cov` to verify no regressions; fix any broken imports
- [X] T026 [P] Inspect `src/adp/recommendation/telemetry.py` and replace any hard-coded span attribute strings with imports from `adp.telemetry.contract`; run `pytest tests/recommendation/ -q --no-cov`; fix regressions
- [X] T027 [P] Inspect `src/adp/validation/telemetry.py` and replace any hard-coded span attribute strings with imports from `adp.telemetry.contract`; run `pytest tests/validation/ -q --no-cov`; fix regressions
- [X] T028 [P] Run `ruff check src/adp/telemetry/ src/adp/api/routers/health.py src/adp/api/app.py` — fix all lint errors; also `ruff check src/adp/intake/telemetry.py src/adp/recommendation/telemetry.py src/adp/validation/telemetry.py`
- [X] T029 [P] Run `adp-generate --check` — confirm zero schema drift (no changes to ADP-SPEC-001 model or theme schema)
- [X] T030 Run `pytest tests/ --ignore=tests/integration -q --no-cov` — assert all 314+ tests pass; fix any regressions
- [X] T031 Run QG-08, QG-10, QG-11 CI gates explicitly: `pytest tests/unit/test_no_sensitive_data.py tests/unit/test_trace_id_context.py tests/unit/test_ai_step_span.py -v --no-cov`; all must pass; these are blocking CI gates per the constitution
- [X] T032 [P] Write `tests/unit/test_telemetry_overhead.py` to satisfy SC-002 and NFR-001: `test_sc002_telemetry_overhead_under_50ms()` — (a) create a no-op HTTP handler that returns `{"ok": True}`; (b) time 100 calls WITHOUT the `TraceIdFilter` + metrics middleware installed; (c) time 100 calls WITH both installed; (d) assert the per-request overhead delta is ≤ 50ms on average (`(total_with - total_without) / 100 <= 0.050`); use `time.perf_counter()` for timing; run with `pytest tests/unit/test_telemetry_overhead.py -v --no-cov`; this enforces NFR-001 and SC-002 as a CI timing gate

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; contract constants must exist
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; establishes trace ID + AI step span infrastructure
- **US2 (Phase 4)**: Depends on US1 (`ai_step_span` and logging must exist); T011 depends on T009's `_truncate()`
- **US3 (Phase 5)**: Depends on Foundational only (metric names from contract); independently testable
- **US4 (Phase 6)**: Depends on US1 (`ai_step_span` must exist for T022)
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — establishes the entire trace/span infrastructure
- **US2 (P1)**: Depends on US1 (needs `ai_step_span()` and logging to exist); T015 may fix log messages discovered failing in T012
- **US3 (P2)**: Can start after Foundational — metric registration and health endpoint are independent of tracing
- **US4 (P2)**: Depends on US1 (`ai_step_span()` must exist and have correct error handling)

### Parallel Opportunities

- T004, T005, T006, T007 (US1 tests): parallel — independent test functions
- T011, T012, T013 (US2 tests): parallel — independent test functions
- T016, T017, T018 (US3 tests): parallel — independent test functions
- T022, T023 (US4 tests): parallel — independent test functions
- T025, T026, T027, T028, T029, T032 (Polish): parallel — independent files

---

## Implementation Strategy

### MVP First (US1 + QG gates)

1. Phase 1 + 2 → `prometheus-client` installed, `adp.telemetry` package, contract constants
2. Phase 3 (US1) → `context.py` + `spans.py` + X-Trace-ID middleware in app.py
3. Phase 4 (US2) → `test_no_sensitive_data.py` CI gate
4. **STOP and VALIDATE**: `pytest tests/unit/test_no_sensitive_data.py tests/unit/test_trace_id_context.py tests/unit/test_ai_step_span.py` — all three QG gates green

### Incremental Delivery

1. Setup + Foundational → Contract constants established
2. US1 → Trace ID propagation + AI step span helper (MVP)
3. US2 → QG-08 no-leak CI gate
4. US3 → Health + metrics endpoints
5. US4 → Explicit failure surfacing verification
6. Polish → Normalize existing telemetry files; full suite

---

## Notes

- [P] tasks = different files, no dependencies
- Tests MUST fail before implementation; commit failing tests first (ART-IV)
- `adp.telemetry.contract` has ZERO imports from other `adp.*` modules — it is a pure constants file; this prevents circular imports when other modules import from it
- The `HealthStatus` model can be imported from `adp.docs.models` (already has the structure) OR defined inline in `health.py` — check if it already exists before creating a new one
- QG-08, QG-10, QG-11 are **blocking** CI gates per the constitution — T031 must pass before any PR is merged
- `adp-generate --check` must remain exit 0 — no changes to `models.py` or `LockedTheme`
- SC-006 (traceable AI steps): T005 verifies that span attributes are sufficient for post-hoc reconstruction of knowledge citations and token usage without querying the model store
