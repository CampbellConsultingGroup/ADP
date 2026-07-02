# Feature Specification: Anthropic LLM Integration with Model Selection

**Feature Branch**: `015-anthropic-llm`
**Created**: 2026-07-02
**Status**: Implemented (retroactive spec — code was written before spec; flagged as process violation; corrected here)
**Input**: `/home/jmuir/projects/ADP/docs/015-anthropic-llm-integration.md`

> **⚠️ Process note**: This spec was written after implementation. Per ART-I, specs MUST precede implementation. This retroactive spec exists to maintain the canonical record and prevent recurrence — future features on this branch MUST follow spec → plan → tasks → implement order.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this spec is a retroactive correction; process violation acknowledged
- **ART-IV** — Test-Driven Development: always applies; 350 Python + 23 TypeScript tests pass
- **ART-V** — Security by Design: `ADP_LLM_API_KEY` is never logged, stored in spans, or returned in API responses; `NFR-001` enforces this; QG-08 verifies it
- **ART-VI** — Observability: LLM request metadata (model, char count, correlation ID) is logged without content; ADP-SPEC-012 telemetry patterns followed
- **ART-VII** — Grounded AI Only: the extraction pipeline grounds proposals in source text (`source_excerpt` field); architect confirmation is required before proposals enter the model (ART-VIII)
- **ART-VIII** — Human-in-the-Loop: unchanged from ADP-SPEC-014; every extracted proposal requires explicit per-proposal confirm/reject; no auto-confirm path exists

**ART-V (security)**: Moderate risk. API key handling is a credential concern; key must never appear in any observable output.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: `ADP_LLM_API_KEY` (organizational Anthropic API key); LLM-generated text (may contain organizational context from extraction prompts).

**Trust boundaries crossed**: ADP backend → Anthropic API (HTTPS); browser → Vite dev server → ADP backend (proxy).

**Abuse cases**:
- API key exposed in a log or span → Mitigated by `NFR-001`; QG-08 CI gate scans for secret patterns; key is read from env var and only used in the `Authorization`/`x-api-key` header, never written to any observable output
- Model selection bypasses content policy → Mitigated by Anthropic's own content filtering; ADP does not construct adversarial prompts
- CORS bypass via Vite proxy → Mitigated because the proxy is dev-only; in production, the web app and API run on the same origin

**Residual risk**: Low. The API key risk is the primary concern, mitigated by environment variable isolation and the QG-08 gate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Connect to Anthropic and Extract Requirements (Priority: P1)

An architect sets `ADP_LLM_API_KEY` and starts the ADP server. They open the Requirements Intake screen, paste a block of requirement text into the Bulk Text tab, and click "Extract Requirements." Within 15 seconds, Claude Sonnet 4.6 returns a set of extracted proposals each with a draft statement, kind classification, source excerpt, and confidence score. The architect can then confirm or reject each proposal to add it to their design.

**Why this priority**: The core value of ADP-SPEC-014 (requirements intake) is not realized until a real LLM can extract from text. The stub returned 0 proposals; Anthropic integration makes the feature functional.

**Independent Test**: Set `ADP_LLM_API_KEY` and `ADP_LLM_ENDPOINT=https://api.anthropic.com`; submit 5-sentence requirements text to `POST /intake`; poll for completion; assert ≥ 1 proposal with non-empty `draft_statement`, `source_excerpt`, and `confidence` between 0 and 1.

**Acceptance Scenarios**:

1. **Given** `ADP_LLM_API_KEY` is set, **When** bulk text is submitted to `/intake`, **Then** the extraction completes with `status: "completed"` and at least one proposal.
2. **Given** Claude returns a response wrapped in ` ```json ``` ` code fences, **When** the parser processes it, **Then** the JSON is correctly extracted and parsed (code fences stripped).
3. **Given** `ADP_LLM_API_KEY` is NOT set, **When** bulk text is submitted, **Then** the extraction completes with `status: "completed"` and `proposals: []` — no error, graceful degradation.
4. **Given** the web canvas at `localhost:5173` calls `/api/v1/designs/{id}`, **When** the request is made, **Then** Vite proxies it to `localhost:8001` and returns the design JSON (not HTML).

---

### User Story 2 — Select Model for Extraction and Recommendations (Priority: P1)

An architect opens the "⚙ LLM Settings" tab in the Requirements Intake screen. They can see the current provider (Anthropic), API key status (configured/not configured), and two dropdowns: one for the extraction model and one for the recommendation model. Changing either dropdown immediately updates the active model for subsequent operations without restarting the server.

**Why this priority**: Different tasks have different cost/quality trade-offs. Haiku is appropriate for simple extraction; Opus for complex architectural reasoning. The user explicitly requested model choice.

**Independent Test**: Call `PUT /api/v1/config/llm` with `{"extraction_model": "claude-haiku-4-5-20251001"}`; call `GET /api/v1/config/llm`; assert `extraction_model == "claude-haiku-4-5-20251001"`. Then submit an extraction and assert the correct model was used.

**Acceptance Scenarios**:

1. **Given** the server is running, **When** `GET /api/v1/config/models` is called, **Then** the response lists all 4 Claude models (Sonnet 4.6, Opus 4.8, Haiku 4.5, Fable 5) with `id`, `name`, `tier`, and `recommended_for`.
2. **Given** the architect selects "Claude Opus 4.8" in the Recommendation Model dropdown, **When** `GET /api/v1/config/llm` is called next, **Then** `recommendation_model == "claude-opus-4-8"`.
3. **Given** an unknown model ID is submitted to `PUT /api/v1/config/llm`, **When** processed, **Then** the API returns 422 listing the valid model IDs.
4. **Given** a `POST /intake` request includes `"model": "claude-haiku-4-5-20251001"`, **When** extraction runs, **Then** that model is used for this operation regardless of the global setting.

---

### User Story 3 — Sequential Proposal Actions Without Errors (Priority: P1)

An architect extracts 3 proposals, confirms the first, rejects the second, and confirms the third. All three operations succeed and the design's requirements list shows the two confirmed requirements. No database errors occur between operations.

**Why this priority**: This was a blocking bug — the second mutation always failed with a 500 error, making the intake screen unusable after the first action.

**Independent Test**: Extract 3+ proposals; confirm proposal 1 (gets AUD-001 audit entry); reject proposal 2 (gets AUD-002); confirm proposal 3 (gets AUD-003); verify all three succeed and design has exactly 2 new requirements.

**Acceptance Scenarios**:

1. **Given** 3 proposals from extraction, **When** confirm → reject → confirm are called in sequence, **Then** all three return 200/201 without error.
2. **Given** a design with an existing `AUD-001` entry, **When** a new confirm is executed, **Then** the new audit entry is assigned `AUD-002` (or the next available ID), not `AUD-001`.
3. **Given** a design that has been saved multiple times, **When** `DesignStore.save()` is called with an `audit_log` containing previously-persisted entries, **Then** those entries are silently skipped (ON CONFLICT DO NOTHING) and only new entries are inserted.

---

### Edge Cases

- What if Anthropic is unreachable during extraction? The background task catches the exception, sets `status: "failed"` with `error_description`, and the UI shows an error banner — no 500 to the client.
- What if the model ID in a per-request override is invalid? The request proceeds using the globally configured model (no 422 — the model field is optional and best-effort).
- What if AUD-999 is reached? The existing `adp.audit.writer` already handles this with a `ValueError`; same limit applies here.
- What if two concurrent confirmations race on the same design? The `DesignStore.save()` optimistic concurrency check will cause one to fail with a 409 conflict, same as any other concurrent write.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `LLMClient` MUST detect `anthropic.com` in the endpoint URL and use Anthropic's `/v1/messages` API with `x-api-key` and `anthropic-version` headers; all other URLs use OpenAI-compatible `/v1/chat/completions`.
- **FR-002**: `GET /api/v1/config/models` MUST return all available Claude models with `id`, `name`, `description`, `tier` (lite/standard/premium), `context_window`, and `recommended_for` (extraction/recommendations).
- **FR-003**: `GET /api/v1/config/llm` MUST return `extraction_model`, `recommendation_model`, `endpoint`, `api_key_configured` (bool), and `provider` — never the key value.
- **FR-004**: `PUT /api/v1/config/llm` MUST accept `extraction_model` and/or `recommendation_model` and validate them against the known model list; reject unknown IDs with 422.
- **FR-005**: `IntakeSubmitRequest` MUST accept an optional `model` field that overrides the global extraction model for that single operation.
- **FR-006**: The Anthropic response normalizer MUST strip markdown code fences (` ```json ... ``` `) from the response text before passing to `LLMResponseParser`.
- **FR-007**: The Vite dev server MUST proxy `/api/**`, `/health`, and `/metrics` to `ADP_API_URL` (default `http://localhost:8001`).
- **FR-008**: `DesignStore.save()` MUST use `INSERT ... ON CONFLICT (id) DO NOTHING` for audit entries so that re-saving a design with a full `audit_log` does not violate the `audit_entries` primary key constraint.
- **FR-009**: Audit entry IDs generated by the intake orchestrator and intake router MUST use `max(existing AUD-NNN) + 1` rather than `len(audit_log) + 1` to avoid ID collisions.

### Key Entities

- **LLM Config** (in-process store): `endpoint`, `extraction_model`, `recommendation_model` — defaults from environment variables; overridable per-session via `PUT /api/v1/config/llm`.
- **ModelInfo**: `id`, `name`, `description`, `tier`, `context_window`, `recommended_for` — static list of 4 Claude models.
- **LLMConfigUpdate**: `extraction_model?: str`, `recommendation_model?: str` — partial update request body.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Real Anthropic extraction completes in ≤ 30 seconds for a 500-word text block and returns ≥ 1 correctly classified proposal.
- **SC-002**: Zero extraction proposals are auto-confirmed — all require explicit architect action (inherited from ADP-SPEC-014, unchanged).
- **SC-003**: `GET /api/v1/config/llm` returns `api_key_configured: true` when `ADP_LLM_API_KEY` is set and `false` when absent — key value never returned.
- **SC-004**: Sequential confirm + reject + confirm on 3 proposals all succeed (HTTP 200) without any 5xx error.
- **SC-005**: Switching the extraction model via the UI and submitting a new extraction uses the newly selected model within the same server session, without restart.

## Assumptions

- **Anthropic models**: The 4 models listed (Sonnet 4.6, Opus 4.8, Haiku 4.5, Fable 5) are pinned by the spec. Adding new models requires a spec amendment (ART-XV schema evolution).
- **Model persistence**: Model selection is in-process only; it resets to the environment variable default on server restart. Persistent model preference is v2 scope.
- **Code fence handling**: The `_EXTRACTION_SYSTEM_PROMPT` instructs Claude to return only JSON, but Claude may still add code fences. The parser strips them as a defensive measure.
- **Vite proxy dev-only**: The Vite proxy is a development convenience and is not present in production builds. In production, the web app and API must be served from the same origin or behind a reverse proxy.
- **`ON CONFLICT DO NOTHING` is safe**: Audit entries are immutable; silently skipping a duplicate insert (because the entry already exists from a previous save) cannot mask any mutation.
