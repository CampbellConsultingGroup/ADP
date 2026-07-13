# Feature Specification: Immutable LLM Reasoning Store

**Feature Branch**: `027-llm-reasoning-store`
**Created**: 2026-07-04
**Status**: Draft
**Prerequisite for**: ADP-SPEC-028 (Recommendation Reasoning Display)

## Context

Every LLM call ADP makes produces reasoning that has value beyond the immediate response. Currently that reasoning is transient — it lives in the `operations` table payload for 24 hours and then expires. Once gone, it cannot be audited, explained, or contested. 

For AI-assisted architecture decisions to be trustworthy, every significant LLM output must be:
1. **Permanently preserved** — reasoning that supported a decision must be available as long as the design exists
2. **Immutable** — reasoning cannot be altered after the fact to rewrite history
3. **Traceable** — each reasoning record links to the specific operation, option, and step that produced it

This spec creates the storage infrastructure. It does not change any user-facing behaviour — the reasoning records are written silently alongside the existing pipeline and exposed via a read API that ADP-SPEC-028 builds upon.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-VII** — AI Grounding: reasoning records are the evidence trail for how AI outputs are grounded in knowledge
- **ART-IX** — Audit Trail: reasoning is an extension of the audit trail — every AI decision has a permanent provenance record
- **ART-XI** — Provenance: each reasoning record carries model ID, token counts, and a prompt hash — sufficient to reconstruct the context without storing raw source text

## Threat Model

**Assets at risk**: Reasoning records containing LLM outputs may reveal internal prompting strategies if the API is exposed without auth. Prompts themselves are never stored (SHA-256 hash only).

**Trust boundaries crossed**: Backend pipeline → PostgreSQL reasoning table.

**Abuse cases**:
- Reasoning records deleted to cover up a poor AI decision: mitigated by DB-level `BEFORE DELETE` trigger that raises an exception — no application-level bypass possible.
- Reasoning records modified to retroactively improve justification: mitigated by DB-level `BEFORE UPDATE` trigger.
- Mass extraction of reasoning texts: mitigated by requiring authentication (ADP-SPEC-026) on the read endpoint.

**Residual risk**: The DB-level triggers prevent deletion via normal SQL but a superuser (`postgres`) could drop the trigger. Accepted — superuser access to production DB is a separate governance concern.

## User Scenarios & Testing

### User Story 1 — Every Recommendation Has a Permanent Reasoning Record (Priority: P1)

When an architect accepts or reviews a recommendation, the reasoning that led to that option can be retrieved at any point in the future — even after the recommendation operation has expired from the operations table.

**Why this priority**: Without permanence, the AI reasoning disappears within 24 hours. Permanent records are the foundation for US2 and US3.

**Independent Test**: Run a recommendation pipeline; wait for the operations TTL to expire; query `GET /api/v1/reasoning?operation_id={op_id}`; assert records are still present with correct content.

**Acceptance Scenarios**:

1. **Given** a recommendation operation completes with 3 options, **When** the generate step finishes, **Then** one reasoning record exists per option in the `llm_reasoning_log` table with the option's rationale and step `"generate"`.
2. **Given** a trade-off analysis step runs for 3 options × 4 criteria, **When** complete, **Then** reasoning records exist for each option's trade-off analysis with step `"analyze_tradeoffs"`.
3. **Given** reasoning records are written, **When** a SQL `UPDATE` or `DELETE` is attempted on the table, **Then** the database raises an exception and the records are unchanged.

---

### User Story 2 — Reasoning Records Cannot Be Altered (Priority: P2)

A database administrator attempts to UPDATE a reasoning record to change the rationale text after an architect has already reviewed it. The database rejects the operation.

**Why this priority**: Immutability is the core safety property. Without it the records are useful but not trustworthy.

**Independent Test**: `UPDATE llm_reasoning_log SET reasoning_text = 'altered' WHERE id = <id>` raises `P0001` exception from the trigger.

**Acceptance Scenarios**:

1. **Given** a reasoning record exists, **When** `UPDATE llm_reasoning_log SET ... WHERE id = ...` is executed, **Then** the DB raises `"llm_reasoning_log is append-only — UPDATE is not permitted"`.
2. **Given** a reasoning record exists, **When** `DELETE FROM llm_reasoning_log WHERE id = ...` is executed, **Then** the DB raises `"llm_reasoning_log is append-only — DELETE is not permitted"`.
3. **Given** `DROP TRIGGER` is attempted by a non-superuser, **Then** PostgreSQL rejects it with insufficient privileges.

---

### User Story 3 — Reasoning API Returns Records by Operation (Priority: P3)

A client (the recommendation UI or an admin tool) queries reasoning records by `operation_id` and receives the reasoning text, model, step, option_id, and token counts for each record.

**Acceptance Scenarios**:

1. **Given** reasoning records exist for operation `OP-001`, **When** `GET /api/v1/reasoning?operation_id=OP-001` is called, **Then** a list of reasoning records is returned sorted by `created_at`.
2. **Given** reasoning records exist for multiple operations, **When** filtered by `operation_id`, **Then** only records for that operation are returned.
3. **Given** no records exist for an operation, **When** queried, **Then** an empty list is returned (not 404).

---

### Edge Cases

- LLM call fails mid-pipeline: no reasoning record written for the failed step (fire-and-forget write, failure is logged but does not block the pipeline).
- Reasoning text exceeds 100,000 characters (e.g. very large LLM output): truncated to 100,000 characters before storage; `truncated: true` flag set in the record.
- Prompt hash: SHA-256 of the full prompt string in UTF-8, stored as a 64-character hex string. The prompt itself is NEVER stored.
- Intake extraction reasoning: also captured (the extracted requirements rationale from the LLM response) — not just recommendation pipeline.

## Requirements

### Functional Requirements

**Schema (FR-001 to FR-003)**

- **FR-001**: An Alembic migration MUST create the `llm_reasoning_log` table with columns: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `operation_id TEXT NOT NULL`, `option_id TEXT`, `step_name TEXT NOT NULL`, `model_id TEXT NOT NULL`, `reasoning_text TEXT NOT NULL`, `truncated BOOLEAN NOT NULL DEFAULT FALSE`, `prompt_hash TEXT NOT NULL` (64-char SHA-256 hex), `input_tokens INTEGER NOT NULL DEFAULT 0`, `output_tokens INTEGER NOT NULL DEFAULT 0`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- **FR-002**: The migration MUST create a `BEFORE UPDATE` trigger on `llm_reasoning_log` that executes `RAISE EXCEPTION 'llm_reasoning_log is append-only — UPDATE is not permitted'`.
- **FR-003**: The migration MUST create a `BEFORE DELETE` trigger on `llm_reasoning_log` that executes `RAISE EXCEPTION 'llm_reasoning_log is append-only — DELETE is not permitted'`.

**Write path (FR-004 to FR-007)**

- **FR-004**: A `ReasoningStore` class MUST be added to `src/adp/store/reasoning.py` with an async `write(record: ReasoningRecord) -> None` method that INSERTs one row.
- **FR-005**: The `ReasoningRecord` dataclass MUST include: `operation_id`, `step_name`, `model_id`, `reasoning_text`, `prompt_hash`, `input_tokens`, `output_tokens`, and optional `option_id`. The `id` and `created_at` are DB-generated.
- **FR-006**: The recommendation pipeline's `generate_step` MUST write one `ReasoningRecord` per generated option, capturing the option's `rationale` as `reasoning_text` and `step_name = "generate"`.
- **FR-007**: The recommendation pipeline's `analyze_tradeoffs_step` MUST write one `ReasoningRecord` per option, capturing the full trade-off analysis text as `reasoning_text` and `step_name = "analyze_tradeoffs"`. The intake extraction pipeline MUST write one record per extraction call with `step_name = "extract"`.

**Read API (FR-008 to FR-009)**

- **FR-008**: `GET /api/v1/reasoning` with query parameter `operation_id` MUST return a list of `ReasoningRecord` summaries (all fields except `prompt_hash`) sorted by `created_at` ascending.
- **FR-009**: The endpoint MUST support an optional `option_id` query parameter to filter records for a specific option.

### Key Entities

- **ReasoningRecord**: id (UUID), operation_id, option_id (nullable), step_name, model_id, reasoning_text (≤ 100,000 chars), truncated, prompt_hash (SHA-256 hex), input_tokens, output_tokens, created_at

## Success Criteria

- **SC-001**: After a recommendation pipeline run, `SELECT count(*) FROM llm_reasoning_log WHERE operation_id = '{op_id}'` returns at least one row per option.
- **SC-002**: `UPDATE llm_reasoning_log SET reasoning_text = 'tampered' WHERE id = <any_id>` raises PostgreSQL error code `P0001`.
- **SC-003**: `DELETE FROM llm_reasoning_log WHERE id = <any_id>` raises PostgreSQL error code `P0001`.
- **SC-004**: Reasoning records persist after the corresponding `operations` row is deleted by the TTL cleanup job.
- **SC-005**: The write path adds < 10ms latency to each pipeline step (write is fire-and-forget, not blocking).

## Assumptions

- UUIDs are generated by PostgreSQL (`gen_random_uuid()`) — no application-side UUID generation for record IDs.
- The `reasoning_text` field stores the LLM's returned rationale/explanation text, not the raw full response body. For the generate step, this is `option.rationale`. For trade-offs, this is the full trade-off analysis as a formatted string.
- Prompt hashing uses SHA-256 of the full prompt (system + user messages concatenated) in UTF-8. This allows cross-referencing without storing the prompt.
- The `ReasoningStore` uses the same shared KB session factory from `adp.api.deps` (ADP-SPEC-023). No new DB connections are created.
- Writes are fire-and-forget (using `asyncio.create_task`) so they do not block the pipeline response time.
- The `llm_reasoning_log` table is separate from `operations` so reasoning persists beyond the operations 24h TTL.
