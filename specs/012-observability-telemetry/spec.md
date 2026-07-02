# Feature Specification: Observability & Telemetry

**Feature Branch**: `012-observability-telemetry`
**Created**: 2026-07-02
**Status**: Draft
**Input**: `/home/jmuir/projects/ADP/docs/012-observability-telemetry.md`

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-V** — Security by Design: central to this feature — FR-006 prohibits secret or sensitive-data leakage into any log or span; QG-08 enforces this in CI
- **ART-VI** — Observability is Not Optional: this feature IS the implementation of ART-VI; every subsequent service-bearing spec builds on the telemetry contract defined here

**ART-VII (AI grounding)**: Partially engaged — AI step spans (FR-003) carry the knowledge references that ground recommendations and verdicts, making AI grounding queryable post-hoc.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Organizational architecture designs and AI prompt/response content (sensitive IP); authentication credentials and API keys; user identity information.

**Trust boundaries crossed**: Application process → structured log output (stdout/files); application process → telemetry collector (network); CI pipeline → secret scan tool.

**Abuse cases**:
- Sensitive design content (element descriptions, requirement text) leaks into log output and becomes readable in log aggregation systems → Mitigated by FR-006 and QG-08 (automated secret scan in CI); by policy, design content and AI prompt/response text are never logged as plain values — only metadata (IDs, counts, latencies) is logged
- API keys or auth tokens appear in a span attribute or log field → Mitigated by QG-08 secret scan; by policy, no credential values appear in any telemetry; only boolean "auth_present" or masked headers are logged
- Telemetry data for AI steps is used to reconstruct proprietary organizational patterns → Mitigated by treating AI telemetry as operationally sensitive; telemetry access is role-gated (operator scope); design content is never included in span attributes

**Residual risk**: Low. Telemetry is write-only from the application's perspective; the telemetry pipeline itself does not feed back into the canonical model. The primary risk is IP disclosure via log verbosity — mitigated by the explicit no-content-in-logs policy.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Trace a Request End-to-End (Priority: P1)

An on-call engineer receives an alert about a slow or failed AI recommendation. They need to reconstruct exactly what happened: which request triggered it, which services it traversed, which knowledge items were retrieved, how many tokens were consumed, and what the latency was at each step. They query the telemetry system with the trace ID and receive a complete picture of the request path without needing to access the canonical model store or application logs separately.

**Why this priority**: End-to-end traceability is the core value of observability. Without it, debugging production incidents becomes guesswork. This story also validates that correlation ID propagation works across all service boundaries.

**Independent Test**: Send a known request through the full recommendation pipeline; retrieve the trace by ID; verify the trace contains spans for every orchestration step with the required attributes (input token count, output token count, estimated cost, latency, knowledge item IDs cited).

**Acceptance Scenarios**:

1. **Given** a request to the AI recommendation service, **When** it completes (successfully or with error), **Then** a single trace ID is present in every log line emitted during that request, including lines from the knowledge retrieval step, the LLM call, and the gating step.
2. **Given** a trace ID, **When** telemetry is queried for that ID, **Then** every AI orchestration step that ran appears as a distinct span with: `input_tokens`, `output_tokens`, `estimated_cost_usd`, `latency_ms`, and `knowledge_item_ids` (list of cited knowledge item IDs).
3. **Given** a failing AI step, **When** it raises an error, **Then** a span is emitted with error status; the error type and message appear as span attributes; no span is silently dropped.
4. **Given** an incoming request without a correlation ID header, **When** it arrives at the ingress point, **Then** a new trace ID is generated and attached to all subsequent telemetry for that request.

---

### User Story 2 — Verify No Sensitive Data in Telemetry (Priority: P1)

A security reviewer needs assurance that neither the API key used to call the LLM endpoint, nor the content of architecture designs (which are organizational IP), nor authentication tokens appear in any log line or span attribute. They run an automated scan against the telemetry output and receive a clean result.

**Why this priority**: Equal to P1 — a single credential leak in log output could expose secrets to anyone with log-aggregation access, which is typically broader than application access. This must be verified at every CI run (QG-08).

**Independent Test**: Exercise the full request pipeline with a known credential pattern; grep all log output and span attribute values for the credential pattern and design content; assert zero matches.

**Acceptance Scenarios**:

1. **Given** any log line emitted during any ADP operation, **When** scanned for secret patterns (API keys, Bearer tokens, passwords, private keys), **Then** zero matches are found.
2. **Given** a span emitted by an AI orchestration step, **When** its attribute values are inspected, **Then** no raw design content (element names, requirement text, AI prompt text, AI response text) appears as a span attribute value — only metadata (IDs, lengths, counts) is permitted.
3. **Given** a request that includes an authorization header, **When** the corresponding log lines and spans are inspected, **Then** the header value does not appear; only a boolean `auth_present: true` or a masked token prefix (e.g., `Bearer eyJ...` truncated to `Bearer [redacted]`) is recorded.

---

### User Story 3 — Monitor Service Health and Metrics (Priority: P2)

An operations engineer needs to know if any ADP service is degraded. They query the health endpoint for a service and receive a clear healthy/unhealthy status. They query the metrics endpoint and receive the four golden signals (rate, error rate, latency distribution, saturation) so they can set alerting thresholds.

**Why this priority**: P2 because health and metrics are important for production operations but do not block the core observability story (P1 is about request tracing and security compliance).

**Independent Test**: Start a service; call its health endpoint; assert 200 with a health payload; call its metrics endpoint; assert the response contains rate, error rate, latency, and saturation metrics.

**Acceptance Scenarios**:

1. **Given** a running ADP service, **When** its health endpoint is queried, **Then** it responds within 2 seconds with a status of `healthy` (when operational) or `unhealthy` (with a reason when degraded).
2. **Given** a running service processing requests, **When** its metrics endpoint is queried, **Then** the response includes: total request count, error count, request latency distribution (p50/p95/p99), and a resource saturation indicator.
3. **Given** a service that is starting up, **When** its health endpoint is queried before it is ready, **Then** it returns `unhealthy` with status `starting` — not a connection error — so orchestrators can distinguish startup from failure.

---

### User Story 4 — Explicit Failure Surfacing (Priority: P2)

An engineer is debugging a silent failure in the recommendation pipeline. They look at the telemetry and find every error — including errors in background steps, retried steps, and partial failures — explicitly represented as errored spans or structured error log events. There are no catch-and-continue paths that swallow exceptions without telemetry signal.

**Why this priority**: P2 because the silent-failure prohibition enforces an existing ART-VI MUST rule, but validating the absence of silent catch-and-continues is primarily a code-quality concern rather than a user-facing feature.

**Independent Test**: Inject a failure into a known code path (e.g., knowledge retrieval timeout); verify that a structured error log line AND an errored span appear; verify the error is not swallowed and the telemetry system shows the failure.

**Acceptance Scenarios**:

1. **Given** any exception raised during request processing, **When** it propagates or is caught, **Then** a structured log event with level `ERROR` and the exception type and message appears in telemetry; no exception is swallowed without at least this log event.
2. **Given** an AI orchestration step that fails, **When** its span is inspected, **Then** the span status is `ERROR` and the `error.type` and `error.message` attributes are populated; the span is never dropped or given a success status when the step failed.
3. **Given** a retry loop that eventually succeeds, **When** intermediate failures occur, **Then** each failed attempt appears as an errored span or event; the final successful attempt appears separately; neither the failures nor the retries are silently absorbed.

---

### Edge Cases

- What if the telemetry backend is unavailable? Telemetry emission failures must not crash the main request path; telemetry is best-effort (emit-and-forget) for spans and metrics. Structured logs to stdout are always emitted regardless of backend availability.
- What if an AI step produces very large inputs or outputs? Span attribute values exceeding a defined maximum size (1024 characters) must be truncated with a `...[truncated]` suffix rather than omitted or causing an error.
- What if multiple correlation IDs arrive (e.g., from a gateway that injects its own)? The first ID in the chain is preserved as the root trace ID; additional IDs are recorded as span attributes.
- What if a sensitive field name is used for a non-sensitive value (e.g., a field called `password_reset_count`)? The no-leakage rule applies to values that match secret patterns, not to field names. Published schema field names are permitted.
- What if telemetry overhead causes the interactive latency budget to be exceeded? The telemetry emission path must be async/non-blocking; overhead exceeding 50ms per request is a violation of NFR-001.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every log line MUST be structured (JSON format) and MUST carry a `trace_id` field matching the request's correlation ID.
- **FR-002**: A correlation/trace ID MUST be generated at the request ingress point (or extracted from an incoming header) and propagated as a context value through every service call and AI orchestration step within that request.
- **FR-003**: Every AI orchestration step (every node in the recommendation graph and every LLM critic in the validation graph) MUST emit a span carrying: `input_tokens` (integer), `output_tokens` (integer), `estimated_cost_usd` (float), `latency_ms` (integer), `knowledge_item_ids` (list of cited item IDs), `step_name` (string identifying the node), and span status (OK or ERROR).
- **FR-004**: Every service MUST expose a health endpoint returning structured health status (healthy/unhealthy + reason) and a metrics endpoint exposing at minimum: total request count, error count, p50/p95/p99 latency, and a saturation metric.
- **FR-005**: Every exception raised during request processing MUST produce at least one structured log event at level ERROR with the exception type and message; no exception may be silently swallowed without this telemetry signal.
- **FR-006**: No log line, span attribute, or metric label value MUST contain: API keys, Bearer tokens, passwords, private keys, or raw design content (element descriptions, requirement text, AI prompt text, AI response text). Only metadata (IDs, counts, lengths, latencies, boolean flags) is permitted.

### Key Entities

- **Trace**: A collection of spans sharing a `trace_id` that together represent one end-to-end request. A trace threads through all services and AI steps for a single request.
- **Span**: A single timed unit of work within a trace. An AI step span carries the full set of attributes defined in FR-003. A service span carries request metadata (route, status, latency).
- **Correlation ID / Trace ID**: A unique identifier generated at request ingress and propagated through all downstream calls. Appears as `trace_id` in logs and as the trace identifier in spans.
- **Structured Log Event**: A JSON log line carrying at minimum: `timestamp`, `level`, `trace_id`, `event` (message), and relevant context fields. Never contains raw content values.
- **Health Status**: A structured response from a health endpoint: `{"status": "healthy"|"unhealthy", "reason": null|"<description>"}`.
- **Telemetry Contract**: The published schema of required span attributes, log fields, and metric names that all service-bearing specs MUST satisfy. This is the normative artifact produced by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A trace ID is present in 100% of log lines emitted during any request that involves at least one AI orchestration step.
- **SC-002**: Every AI orchestration step emits its span within 50 milliseconds of step completion; telemetry overhead does not materially degrade interactive latency.
- **SC-003**: Automated secret scanning of all log output and span attribute values across the full test suite produces zero secret-pattern matches (0 violations).
- **SC-004**: Service health endpoints respond with a valid health payload within 2 seconds under normal load.
- **SC-005**: Every exception raised during request processing produces at least one ERROR-level structured log event within 1 second of the exception occurring; 100% of errors are represented.
- **SC-006**: A telemetry trace for any AI recommendation or validation run contains sufficient data to reconstruct the knowledge citations, token usage, and per-step latency without querying the canonical model store directly.

## Assumptions

- **Telemetry backend**: This spec defines the telemetry contract (log schema, span attribute names, metric names) but does NOT mandate a specific backend. The operator chooses the collection backend (Jaeger, Zipkin, Prometheus, Grafana, etc.) based on their infrastructure. The implementation uses the OpenTelemetry SDK (already a project dependency) for portable instrumentation.
- **Retention period**: Log and span retention is an operator/infrastructure concern and is out of scope for this spec. Reasonable defaults (7 days for logs, 30 days for traces) are assumed for cost estimation but are not normative requirements of this feature.
- **Cost attribution granularity**: Cost is attributed per AI orchestration step (per LangGraph node). Each span carries `estimated_cost_usd` for that step. Cross-step aggregation (per-request or per-design totals) is produced by the telemetry backend's query layer, not by the application.
- **Secret detection scope**: The secret scan covers log output and span attribute values. It does not scan span events or span link attributes (which are not written by v1 instrumentation). This scope is sufficient for QG-08 compliance.
- **Design content policy**: Raw design content (element names, requirement descriptions, AI prompts, AI responses) is never logged or included in span attributes as a policy decision — not only as a constitutional requirement. This is consistent with the existing pattern in ADP-SPEC-006/007/008.
- **Telemetry availability**: Telemetry emission is best-effort (non-blocking, async where possible). A failing telemetry backend does not cause request failures. Structured log output to stdout is always synchronous and available regardless of backend state.
- **Existing instrumentation**: ADP-SPEC-006, 007, and 008 already add OpenTelemetry spans for AI steps. This spec formalizes the contract those specs implement and ensures consistent attribute naming across all AI steps.
