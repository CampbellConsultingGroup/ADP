# Research: Requirements Intake & Normalization

**Branch**: `006-requirements-intake` | **Date**: 2026-07-01  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: LLM Client — OpenAI-Compatible HTTP API

**Decision**: Call the configurable LLM endpoint using `httpx` against the OpenAI Chat Completions API format (`POST /v1/chat/completions`). No SDK dependency — raw HTTP with structured output via the `response_format: { type: "json_schema", json_schema: {...} }` parameter where supported, falling back to JSON mode (`response_format: { type: "json_object" }`).

**Rationale**: The OpenAI Chat Completions format is the de-facto standard for LLM APIs. It is supported by: OpenAI, Azure OpenAI, Anthropic (via `/v1/messages` with an adapter), Ollama, vLLM, LM Studio, and most on-premise inference servers. Using raw `httpx` with no SDK avoids vendor lock-in and keeps the dependency surface minimal. The `ADP_LLM_BASE_URL` env var points to any compatible endpoint.

**Alternatives considered**:
- LiteLLM — excellent abstraction but adds a heavy dependency; raw httpx achieves the same for our limited use case (one endpoint, one call pattern)
- Anthropic SDK — vendor-specific; contradicts the configurable-endpoint requirement
- LangChain — rejected: far too much abstraction and weight for a single structured extraction call

---

## Decision 2: Structured Extraction via JSON Schema in the Prompt

**Decision**: Send a system prompt that defines the exact JSON structure required, plus a user prompt containing the source text. The response is parsed as a JSON array of requirement objects. For models that support `response_format: json_schema`, use it; otherwise rely on the system prompt to enforce structure and parse defensively.

**Extraction prompt schema** (what the LLM is instructed to return):
```json
{
  "requirements": [
    {
      "statement": "The system must ...",
      "kind": "functional | non-functional | constraint | driver",
      "source_excerpt": "verbatim text from the source that this requirement derives from",
      "confidence": 0.0-1.0,
      "referenced_principles": ["named principle or capability, if any"]
    }
  ]
}
```

**Rationale**: Structured JSON output is reliable for requirement extraction. Providing an explicit schema in the prompt (and using `response_format` where available) significantly reduces parse failures. Requiring `source_excerpt` in the schema enforces grounding discipline at the prompt level.

---

## Decision 3: Source Excerpt Verification

**Decision**: After parsing the LLM response, each proposal's `source_excerpt` is checked as a verbatim substring of the original submitted text (case-insensitive match allowed). Proposals that fail are flagged with `verification_status: "unverified"` and surfaced to the human with a warning. They are not blocked.

**Rationale**: FR-007 requires source excerpts to be verbatim. Blocking unverified proposals would create friction when the LLM paraphrases slightly; surfacing them with a warning preserves usability while satisfying the governance requirement. The human confirms knowing the excerpt is not verbatim.

**Alternatives considered**:
- Fuzzy match (edit distance) — more lenient but harder to reason about; verbatim + case-insensitive is simple and deterministic
- Block unverified proposals entirely — too strict; LLMs often clean up whitespace or formatting

---

## Decision 4: Token Counting and Cost Estimation

**Decision**: Use `tiktoken` with `cl100k_base` encoding (OpenAI's most common tokenizer, compatible with GPT-3.5/4 and many other models) to count input tokens. Output tokens are counted from the response `usage` field if returned by the endpoint; otherwise estimated from the response character count. Cost in USD is estimated using configurable per-token rates from env vars (`ADP_LLM_INPUT_COST_PER_1K`, `ADP_LLM_OUTPUT_COST_PER_1K`).

**Rationale**: `tiktoken` is lightweight and already a transitive dependency via sentence-transformers. Per-token cost rates vary by model; making them configurable allows accurate cost tracking across deployments.

---

## Decision 5: Knowledge Linker Integration

**Decision**: After extraction, the `KnowledgeLinker` calls `KnowledgeRetrieval.keyword_search()` (ADP-SPEC-005) for each named principle/capability string returned by the LLM in `referenced_principles`. Matches above a configurable confidence threshold (`ADP_LINK_CONFIDENCE_THRESHOLD`, default 0.7) are included as proposed `satisfies` links on the proposal.

**Rationale**: The LLM already extracts named references in the extraction step (requested in the prompt). The linker just resolves those names against the knowledge base. Using `keyword_search` (not vector search) for name resolution is more precise — exact matches are more reliable for principle names than semantic similarity.

---

## Decision 6: Telemetry Span — OpenTelemetry

**Decision**: Use `opentelemetry-sdk` to emit one span per extraction job. The span is named `adp.intake.extraction` and carries attributes: `source_char_count`, `proposal_count`, `proposal_ids` (list), `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `model`, `endpoint`, `correlation_id`. The span is exported to whatever OTel exporter is configured in the deployment (ADP-SPEC-012 owns the exporter; this spec only emits).

**Rationale**: OpenTelemetry is the CNCF standard for observability. Using the SDK (not a vendor-specific library) keeps the span compatible with any backend (Jaeger, Zipkin, Datadog, etc.). The span carries exactly the fields required by QG-11.

**Alternatives considered**:
- Logging-based telemetry — simpler but not a proper span; doesn't integrate with distributed tracing
- Prometheus metrics — wrong abstraction for per-job span data

---

## Decision 7: In-Process Proposal Store

**Decision**: `ExtractedProposal` records are stored in the same in-process `operations_store` as other ADP-SPEC-003 operation results (a dict keyed by operation_id, TTL 24h). The proposals are attached to the `OperationHandle.result_summary` field as a JSON payload. When the architect polls the operation, proposals are returned.

**Rationale**: No additional storage infrastructure required. The proposals are transient — they exist only until confirmed or rejected. The existing TTL mechanism handles cleanup. For v1 with a single-process deployment, in-process storage is sufficient.

---

## Decision 8: Proposal Expiry and Partial Confirmation

**Decision**: Unconfirmed proposals expire with the operation handle (24h TTL). Proposals are confirmed individually; partial batch confirmation is allowed — some proposals in a batch may be confirmed while others are rejected or left pending until TTL. The operation handle tracks per-proposal confirmation status.

**Rationale**: Forcing all-or-nothing confirmation is too rigid for real workflows where some requirements are clear and others need further discussion. Individual confirmation with a shared TTL is the right balance.

---

## Decision 9: ADP-SPEC-003 Integration Point

**Decision**: The intake orchestrator is invoked by ADP-SPEC-003's operations router when a `POST /api/v1/operations` request carries `kind=intake`. The router creates an `OperationHandle` with status `pending`, then dispatches `asyncio.create_task(orchestrator.run(submission, operation_id))` without awaiting. Proposals are attached to the handle when extraction completes. The standard confirmation endpoint (`POST /api/v1/operations/{id}/confirm`) handles individual proposal confirmations with a `proposal_id` field in the `ConfirmationPayload`.

**Rationale**: Reuses the existing async operation infrastructure from ADP-SPEC-003 (submit → poll → confirm). Minimal new API surface — just a new `kind` value and an extended `ConfirmationPayload` with `proposal_id`.
