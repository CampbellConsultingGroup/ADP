# Feature Specification: Recommendation Learning and Knowledge Capture

**Feature Branch**: `019-recommendation-learning`
**Created**: 2026-07-03
**Status**: Draft

## Constitutional Articles Touched

- **ART-I**: Spec-Driven Development — always applies
- **ART-III**: Everything is Machine-Readable — knowledge items written from decisions are typed, schema-validated artifacts
- **ART-IV**: Test-Driven Development — always applies
- **ART-VII**: Grounded AI Only — the fix for empty-KB generation clarifies the grounding model: options generated from requirements alone are labelled "requirements-grounded" not "ungrounded advisory"
- **ART-IX**: Provenance and Auditability — acceptance and rejection decisions with reasons are preserved in the knowledge base as durable records

**ART-V**: Low risk — no new credential surfaces; knowledge writes use the existing pgvector database.

## Threat Model

No new threat surface. The knowledge write path uses the existing PostgreSQL database. Rejection reasons are architect-authored text — no sensitive content policy concerns beyond what the existing knowledge base already governs.

## User Scenarios

### User Story 1 — Recommendations Without Prior Knowledge (Priority: P1)

An architect opens the Recommendations screen for a new design that has requirements but the organisation's knowledge base has never been populated. When they click "Get Recommendations", Claude generates useful architectural options based purely on the requirements — with clear labelling that these are requirement-derived rather than knowledge-base-grounded. The architect does not see an empty result or a screen full of advisory warnings.

**Why P1**: Without this fix, the recommendation feature is effectively unusable for new deployments. "Advisory" should mean "grounded but not fully verified" — not "empty knowledge base".

**Acceptance Scenarios**:

1. **Given** an empty knowledge base and 2+ confirmed requirements, **When** recommendations are requested, **Then** Claude returns ≥ 1 option with a title, rationale, and proposed elements.
2. **Given** options generated without knowledge base context, **When** displayed, **Then** each option shows "Generated from requirements" (not the generic ⚠️ ADVISORY banner that implies a fault).
3. **Given** the knowledge base has entries, **When** options are generated, **Then** they cite those entries as before; the "Generated from requirements" label is NOT shown.

---

### User Story 2 — Accept a Recommendation with Reason (Priority: P1)

When the architect accepts a recommendation, they can provide an optional reason ("Works well for our microservices standard"). The accepted option — including its title, rationale, proposed elements, and the acceptance reason — is written to the knowledge base as a positive pattern under `item_type: "accepted_recommendation"`. Future recommendation runs for similar requirements will retrieve and incorporate this past decision.

**Acceptance Scenarios**:

1. **Given** a pending option, **When** accepted with reason "Aligns with our event-driven standard", **Then** the knowledge base gains a new item containing the option title, rationale, proposed elements, and the reason.
2. **Given** no reason is provided on accept, **Then** the knowledge item is still written with a default reason of "Accepted by architect".
3. **Given** the knowledge write fails (e.g. DB unavailable), **Then** the accept still succeeds — the KB write is best-effort and does not block the HTTP response.

---

### User Story 3 — Reject a Recommendation with Reason (Priority: P1)

A new "Reject" button appears on each pending option card. Clicking it opens a dialog requiring a rejection reason (e.g. "Too complex for our team's current capability"). On submit, the option is marked as rejected on screen and the rejected option — title, rationale, and the rejection reason — is written to the knowledge base as an anti-pattern under `item_type: "rejected_recommendation"`. Future pipelines retrieving similar knowledge will see this as a pattern to avoid.

**Acceptance Scenarios**:

1. **Given** a pending option, **When** the architect clicks Reject and enters "Doesn't meet our security policy", **Then** the option disappears from the pending list and a "Rejected" entry appears in a Rejected section.
2. **Given** the architect clicks Reject but submits no reason, **Then** the reject dialog remains open and shows a validation message — rejection reason is required.
3. **Given** the knowledge write for a rejection fails, **Then** the reject still succeeds — KB write is best-effort.
4. **Given** an already-rejected option, **When** reject is attempted again, **Then** the API returns 409.

---

### Edge Cases

- What if the LLM returns no options even with the requirements-only prompt? The screen shows "No options generated — the requirements may need more detail" rather than an error.
- What if the knowledge base is not configured (no DB)? The KB write is silently skipped; accept/reject still work.
- What if the same option title has been written to the KB before? `upsert_item` handles this with `ON CONFLICT DO UPDATE` on the item ID.

## Requirements

- **FR-001**: When `retrieved_knowledge` is empty, the generation prompt MUST NOT require citations; it MUST instruct the LLM to generate options from requirements alone; the `advisory` flag MUST NOT be set solely because the KB is empty.
- **FR-002**: Options generated without KB context MUST set `knowledge_source: "requirements_only"` on the option (new field) and display "Generated from requirements" in the UI instead of the advisory warning.
- **FR-003**: `AcceptOptionRequest` MUST accept an optional `acceptance_reason: str | None` field alongside `confirmation_id`.
- **FR-004**: `POST .../options/{id}/reject` MUST be added; `rejection_reason: str` is required (non-empty); returns 200 on success; 409 if already actioned; 422 if reason is blank.
- **FR-005**: On accept: write a `KnowledgeItem` with `kind="decision"`, `title=option.title`, `full_text=option.rationale + elements + reason`, `metadata={"item_type": "accepted_recommendation", "satisfies": [...], "reason": reason}` to the knowledge base; write is fire-and-forget.
- **FR-006**: On reject: write a `KnowledgeItem` with `kind="decision"`, `full_text=option.title + rejection_reason`, `metadata={"item_type": "rejected_recommendation", "reason": rejection_reason}` to the knowledge base; write is fire-and-forget.
- **FR-007**: The Recommendation UI MUST show a "Reject" button alongside "Accept" on each pending option.
- **FR-008**: The Reject dialog MUST require a non-empty reason before enabling the submit button.

## Success Criteria

- **SC-001**: With an empty knowledge base and ≥ 1 confirmed requirement, the pipeline returns ≥ 1 option with title and proposed elements.
- **SC-002**: After accepting an option, `GET /api/v1/knowledge/items` (or equivalent) includes a new item with `item_type: "accepted_recommendation"`.
- **SC-003**: After rejecting an option with reason, the knowledge base includes a new item with `item_type: "rejected_recommendation"` and the reason in metadata.
- **SC-004**: The reject endpoint requires a non-empty reason; blank reason returns 422.
- **SC-005**: Accept and reject both succeed even when the knowledge base write fails (KB write is fire-and-forget).

## Assumptions

- `KnowledgeIndex.upsert_item()` requires an embedding; since `sentence-transformers` is not installed in the current environment, the write uses a zero-vector placeholder embedding (`[0.0] * 1536`). The item's `full_text` is preserved for `adp-reindex` to generate real embeddings later.
- The `KnowledgeIndex` requires a DB session; the write is done via `DesignStore`'s session factory (reuse existing DB connection). If the DB is unavailable, the write is silently skipped.
- `knowledge_source: "requirements_only"` is a new field added to `SolutionOption` and `SolutionOptionResponse`.
- The generation prompt is updated to produce options without requiring KB citations when knowledge is empty; `validate_citations_step` is updated to not mark options advisory when KB is empty (only when KB has items but citations are invalid).
