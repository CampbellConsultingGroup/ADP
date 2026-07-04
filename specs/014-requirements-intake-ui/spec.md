# Feature Specification: Requirements Intake HTTP API and Web Screen

**Feature Branch**: `014-requirements-intake-ui`
**Created**: 2026-07-02
**Status**: Draft
**Input**: `/home/jmuir/projects/ADP/docs/014-requirements-intake-ui.md`

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Canonical Model as Single Source of Truth: confirmed requirements are written to the canonical `ArchitectureDescription.requirements` list — no requirement exists outside the model
- **ART-IV** — Test-Driven Development: always applies
- **ART-VI** — Observability: intake operations emit structured logs and OTel spans per the telemetry contract (ADP-SPEC-012); the LLM extraction step already emits telemetry via `adp.intake.telemetry`
- **ART-VII** — Grounded AI Only: the LLM extraction step is already grounded via ADP-SPEC-006; confirmed proposals carry `source_excerpt` provenance; this spec surfaces that provenance in the UI
- **ART-VIII** — Human-in-the-Loop for Consequence: writing a `Requirement` to the canonical model is consequential; every extracted proposal MUST be individually confirmed or rejected by the architect before it enters the model — never written automatically
- **ART-IX** — Provenance and Auditability: each confirmed requirement writes an audit entry with the actor and the proposal ID that was accepted
- **ART-XIII** — Typed Contracts Everywhere: all API request/response payloads are Pydantic models with `extra="forbid"`; the TypeScript client uses typed interfaces matching the API schema

**ART-V (security)**: Low-moderate risk. Source text submitted for extraction is deleted after extraction (existing ADP-SPEC-006 policy). No source text is logged or stored in spans.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Business requirement text submitted by architects (may contain sensitive organizational plans); the canonical design model (could be corrupted by unreviewed auto-confirmed requirements).

**Trust boundaries crossed**: Browser → FastAPI API → `adp.intake` Python module → LLM endpoint.

**Abuse cases**:
- An architect accidentally confirms a poorly-extracted requirement that doesn't match the source → Mitigated by showing `source_excerpt` alongside each proposal so the architect can see exactly what text the AI cited; edit-before-confirm is always available
- Auto-confirm bypasses human review → Mitigated by ART-VIII: the confirm endpoint requires an explicit per-proposal human action; there is no "confirm all" shortcut in v1
- Source text leaks into logs or spans → Mitigated by ADP-SPEC-006's existing policy (`del submission` after extraction); this spec does not add new logging of source content
- Stale proposals are confirmed after expiry → Proposals expire after 24h (existing ADP-SPEC-006 TTL); expired proposals return 410 Gone

**Residual risk**: Low. The main risk is user error (confirming a bad extraction), mitigated by prominent display of source evidence.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Submit Text and Receive Extracted Proposals (Priority: P1)

An architect has a block of requirements text (from a stakeholder email, a brief, or pasted notes) and wants to capture it in the design. They open the Requirements Intake screen for their design, paste the text into the input area, and click "Extract". The system sends the text to the LLM extraction pipeline and, within seconds, returns a list of AI-extracted requirement proposals — each showing a draft statement, its kind (functional/non-functional/constraint/driver), the source excerpt that produced it, and a confidence indicator. The architect now has proposals to review.

**Why this priority**: This is the core user journey and the primary value of the intake feature. Without it, requirements can only be entered manually one by one.

**Independent Test**: Submit a 500-character requirements text to `POST /api/v1/designs/{id}/intake`; poll `GET /api/v1/designs/{id}/intake/{operation_id}`; verify the response contains at least one proposal with `draft_statement`, `kind`, `source_excerpt`, and `confidence`.

**Acceptance Scenarios**:

1. **Given** a design exists and the architect submits a text block, **When** the extraction completes, **Then** the response contains one or more `ExtractedProposal` records each with a non-empty `draft_statement`, a valid `kind`, a non-empty `source_excerpt`, and a `confidence` between 0 and 1.
2. **Given** an extraction is in progress, **When** the architect polls the status endpoint, **Then** the response includes `status: "pending"` until done and `status: "complete"` with proposals when finished.
3. **Given** the text is very short (< 20 characters), **When** submitted, **Then** the API returns 422 with a clear "text too short for extraction" message rather than wasting an LLM call.
4. **Given** the LLM endpoint is unavailable, **When** extraction is attempted, **Then** the operation fails with a clear error status; no partial proposals are returned; the architect is shown a retry option.

---

### User Story 2 — Review and Confirm Proposals (Priority: P1)

The architect reviews each extracted proposal. For each one they can: confirm it as-is (writes a `Requirement` to the model), edit the draft statement and then confirm (writes the edited version), or reject it (discards it without writing to the model). The source excerpt is always visible alongside the proposal so the architect can judge the extraction quality. Once all proposals are actioned, the confirmed requirements appear in the design's requirements list.

**Why this priority**: Equal to P1 — extraction without review is useless. The confirm/reject actions are the ART-VIII human-in-the-loop gate.

**Independent Test**: Given an extracted proposal, call `POST /api/v1/designs/{id}/intake/{op_id}/confirm/{proposal_id}`; verify the design's requirements list now contains the requirement; verify an audit entry was written.

**Acceptance Scenarios**:

1. **Given** an extracted proposal in `pending` status, **When** the architect confirms it, **Then** the proposal status changes to `confirmed`, a new `Requirement` record appears in `design.requirements` with the proposal's statement and kind, and an audit entry is written with the actor and proposal ID.
2. **Given** an extracted proposal, **When** the architect edits the draft statement before confirming, **Then** the confirmed `Requirement.description` contains the architect's edited text (not the raw AI draft), and the audit entry records the edit.
3. **Given** an extracted proposal, **When** the architect rejects it, **Then** the proposal status changes to `rejected`, no `Requirement` is added to the design, and no audit entry for a requirement addition is created.
4. **Given** a proposal that has already been confirmed, **When** a second confirm request is sent, **Then** the API returns 409 (already actioned) and does not create a duplicate requirement.

---

### User Story 3 — Enter Requirements via Structured Form (Priority: P2)

An architect who already knows their requirement clearly — no AI extraction needed — can enter it directly using a structured form: they type the requirement statement, select its kind (functional/non-functional/constraint/driver), and submit. The requirement is written to the design immediately (no LLM call, no proposal step). This is the fast path for requirements the architect can articulate directly.

**Why this priority**: P2 because the LLM extraction path (US1/US2) is the primary value proposition. The structured form is an important secondary path but does not block the MVP.

**Independent Test**: POST `{"mode": "structured_form", "statement": "The system must...", "kind": "functional"}` to `POST /api/v1/designs/{id}/requirements`; verify the requirement appears in the design.

**Acceptance Scenarios**:

1. **Given** a valid design, **When** an architect submits a structured requirement via the form, **Then** the requirement is immediately written to `design.requirements` with the provided statement and kind, and an audit entry is written.
2. **Given** the structured form is submitted without a `statement` field, **Then** the API returns 422 with "statement is required".
3. **Given** the structured form is submitted with an invalid `kind` value, **Then** the API returns 422 listing the allowed values.

---

### User Story 4 — View All Requirements for a Design (Priority: P2)

An architect or reviewer wants to see all requirements currently on a design — both confirmed from extraction and directly entered — along with their kind, status, and which design elements satisfy them. This is the requirements overview that feeds into the traceability matrix.

**Why this priority**: P2 — the traceability matrix (ADP-SPEC-011) already surfaces this; this user story is specifically about the intake screen's requirements summary view, which gives immediate feedback after confirming proposals.

**Independent Test**: After confirming proposals for a design, `GET /api/v1/designs/{id}/requirements`; verify the response lists all requirements with correct `id`, `title`, `kind`, and `satisfies` lists.

**Acceptance Scenarios**:

1. **Given** a design with requirements, **When** the requirements list endpoint is called, **Then** the response lists all requirements with `id`, `title`, `description`, `kind`, and `satisfies` (element IDs that satisfy each requirement).
2. **Given** a design with no requirements, **When** the list endpoint is called, **Then** the response is 200 with an empty list (not 404).

---

### Edge Cases

- What if the architect submits the same text twice for the same design? The second submission creates a new operation with new proposals; the architect must action them separately. The API does not deduplicate submissions.
- What if the LLM returns no proposals for a valid text? The operation completes with `proposals: []` and an informational message; the architect is shown "No requirements could be extracted — try the structured form."
- What if two architects submit intake for the same design simultaneously? Each gets their own operation ID and proposal set; confirmations apply optimistic concurrency (the design version is checked on write, matching ADP-SPEC-002's existing pattern).
- What if a proposal expires (24h TTL) before the architect actions it? Confirming or rejecting an expired proposal returns 410 Gone with "Proposal has expired — please resubmit."
- What if the text contains sensitive information (credentials, PII)? The API accepts and immediately passes the text to the LLM pipeline; it is never persisted (existing ADP-SPEC-006 policy). The architect is shown an informational notice before submitting.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `POST /api/v1/designs/{id}/intake` MUST accept a requirements text (bulk_text mode) or a structured form entry and return an `operation_id` for status polling. Text MUST be deleted from memory after LLM extraction completes.
- **FR-002**: `GET /api/v1/designs/{id}/intake/{operation_id}` MUST return the current status (`pending`, `complete`, `failed`) and, when complete, the list of `ExtractedProposal` records with `draft_statement`, `kind`, `source_excerpt`, `confidence`, and `status`.
- **FR-003**: `POST /api/v1/designs/{id}/intake/{operation_id}/confirm/{proposal_id}` MUST accept an optional `edited_statement`, write a `Requirement` to the canonical model, write an audit entry, and update the proposal status to `confirmed` (or `edited_confirmed`). It MUST return 409 if the proposal has already been actioned.
- **FR-004**: `POST /api/v1/designs/{id}/intake/{operation_id}/reject/{proposal_id}` MUST update the proposal status to `rejected` and return 200 without writing any `Requirement` to the model.
- **FR-005**: `POST /api/v1/designs/{id}/requirements` MUST accept `statement`, `kind`, and optional `description`, write a `Requirement` directly to the canonical model, write an audit entry, and return the created requirement.
- **FR-006**: `GET /api/v1/designs/{id}/requirements` MUST return all requirements on the design with their `id`, `title`, `description`, `kind`, and `satisfies` lists.
- **FR-007**: The web screen MUST provide: (a) a text area for bulk submission with an "Extract" button; (b) a structured form tab for direct entry; (c) a proposals review panel showing each proposal's draft statement, kind badge, source excerpt, confidence bar, and Confirm / Edit & Confirm / Reject actions; (d) a requirements summary list showing all confirmed requirements for the design.

### Key Entities

- **IntakeOperation**: Transient (in-memory, TTL 24h) record of one extraction job: `operation_id`, `design_id`, `status` (pending/complete/failed), list of `ExtractedProposal` records. Created by `POST /intake`; polled via `GET /intake/{op_id}`.
- **ConfirmRequest**: Request body for confirm endpoint: `edited_statement: str | None` (if None, use `draft_statement`); `confirmed_by: str` (actor from auth context).
- **DirectRequirementInput**: Request body for structured form: `statement: str` (required), `kind: RequirementKind` (required), `description: str | None` (optional).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A requirements text submitted to `POST /intake` returns an `operation_id` within 2 seconds; the extraction completes and proposals are available within 30 seconds for a 1000-word text.
- **SC-002**: A confirmed proposal produces a `Requirement` in the canonical design model within 1 second of the confirm action.
- **SC-003**: The intake screen renders the proposals review panel without a page reload (all actions are in-page).
- **SC-004**: Zero extracted proposals are auto-confirmed — every proposal requires an explicit architect action before a `Requirement` is written.
- **SC-005**: The proposals review panel shows the source excerpt alongside every proposal so the architect can always see the evidence behind the AI extraction.
- **SC-006**: The structured form path (direct entry) completes in under 2 seconds end-to-end.

## Assumptions

- **Existing pipeline**: The `adp.intake.ExtractionOrchestrator` is the complete backend implementation. This spec does not change the extraction logic, LLM prompts, or proposal data model. It only wires the orchestrator to HTTP and builds the web screen.
- **Authentication**: v1 uses the same no-auth pattern as other endpoints (bearer token accepted but not validated for local dev). `confirmed_by` is derived from the `X-Actor` header or defaults to `"architect"`.
- **Async polling**: Extraction is asynchronous. The `POST /intake` endpoint starts the extraction in the background and returns immediately with an `operation_id`. The client polls `GET /intake/{op_id}` until `status === "complete"`. Polling interval: 2 seconds in the web client.
- **In-process operation store**: Operations are stored in the same in-memory dict used by ADP-SPEC-003 (keyed by `operation_id`). No database table needed for proposals.
- **Requirement ID generation**: The confirm endpoint generates `REQ-NNN` IDs by incrementing from the highest existing requirement ID on the design, matching the existing `AuditEntry` ID pattern.
- **One operation per design at a time**: v1 does not limit concurrent operations per design. If two operations exist, both sets of proposals are independently actionable.
- **No real-time push**: The web client uses polling (not WebSockets) for extraction status. This is consistent with the existing LLM-as-Judge async pattern.
- **Structured form writes directly**: The `POST /requirements` endpoint (FR-005, FR-006) does not create a proposal — it writes a `Requirement` directly. It still requires an audit entry (ART-IX) but does not require a separate confirmation step (the form submission IS the human confirmation, per ART-VIII).
