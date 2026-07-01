# Feature Specification: Requirements Intake & Normalization

**Feature Branch**: `006-requirements-intake`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-006 — Requirements Intake & Normalization"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-III** — Everything is Machine-Readable: all normalized requirements validate against the published schema before entering the model
- **ART-IV** — Test-Driven Development: always applies; every extraction and confirmation path requires a test before implementation
- **ART-V** — Security by Design: in scope; source requirement documents may be confidential organizational IP; the configurable LLM endpoint allows on-premise deployment to prevent content from leaving the organization
- **ART-VI** — Observability is Not Optional: every AI extraction step MUST emit a telemetry span with inputs, outputs, and cost (FR-006, QG-11)
- **ART-VII** — Grounded AI Only: in scope; extracted requirements MUST cite their source document and specific source excerpt; an extraction without a source citation MUST be flagged for human review before confirmation
- **ART-VIII** — Human-in-the-Loop for Consequence: central concern; no AI-extracted requirement may enter the canonical model without explicit human confirmation; the confirming actor is recorded (FR-003, FR-004, QG-14)
- **ART-IX** — Provenance and Auditability: every confirmed requirement records origin, confirming actor, and timestamp in the audit trail (FR-004, QG-13)
- **ART-XI** — Traceability End to End: the stable id assigned to each confirmed requirement is the anchor for the full requirement → element → recommendation → verdict traceability thread (QG-16)
- **ART-XIII** — Typed Contracts Everywhere: extracted requirements are typed before human review; untyped or schema-invalid extractions cannot be offered for confirmation

## Threat Model *(mandatory — ART-V)*

Source requirement documents represent confidential organizational intellectual property. Risk is moderate: content sent to an AI extraction service could be exposed if the endpoint is a third-party cloud service.

**Assets at risk**: Source requirement documents (confidential strategic intent, product plans, compliance requirements); extracted requirements before human review (potentially mis-attributed or hallucinated content).

**Trust boundaries crossed**: Architect → Platform API (ADP-SPEC-003) → LLM extraction service; LLM extraction service returns extracted proposals → Platform API → human confirmation UI.

**Abuse cases**:
- **Confidential content exposure**: Source requirements are sent to a third-party LLM endpoint, exposing IP → Mitigation: configurable LLM endpoint (FR-001); organizations with strict data residency use an on-premise endpoint
- **AI hallucination enters model**: The AI invents a requirement that was not in the source document → Mitigation: FR-003 (human confirmation required) + FR-007 (source excerpt cited); a hallucinated requirement has no matching source excerpt, making it detectable during review
- **Unconfirmed requirement committed**: A code path bypasses the confirmation gate → Mitigation: FR-003 enforces the gate at the API layer; ADP-SPEC-003's confirmation endpoint is the sole write path (ART-VIII / QG-14)

**Residual risk**: Social engineering of the confirming architect (they confirm a hallucinated requirement without reading carefully) — mitigated by surfacing the source excerpt and extraction confidence score alongside each proposed requirement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit Requirements and Receive Extracted Proposals (Priority: P1)

An architect pastes raw business requirements text (from a stakeholder email, a meeting transcript, or a requirements document) into ADP. The system runs AI extraction asynchronously and returns a list of proposed typed Requirement records, each citing its source excerpt and carrying a confidence score.

**Why this priority**: Extraction is the entry gate. Without it, no requirements enter the model. All other stories depend on proposals first existing.

**Independent Test**: Submit known text containing 3 distinct requirements; assert 3 proposals are returned; assert each proposal has kind, statement, source excerpt, and confidence score; assert none is committed to the model yet.

**Acceptance Scenarios**:

1. **Given** an architect submits raw text containing multiple requirements, **When** extraction completes, **Then** each proposed requirement carries: a draft statement, a kind classification, a source excerpt from the submitted text, and an extraction confidence score
2. **Given** extraction is submitted, **When** the job is accepted, **Then** the system responds immediately with an operation handle; extraction runs asynchronously and does not block the architect (NFR-001)
3. **Given** extraction is running or complete, **When** the architect polls for status, **Then** the current state is returned; when complete, all proposed requirements are available for review

---

### User Story 2 - Confirm, Edit, or Reject Each Proposed Requirement (Priority: P1)

The architect reviews the extracted proposals. For each one they can confirm as-is, edit the statement or classification then confirm, or reject it entirely. Only confirmed requirements enter the canonical model. The confirming actor is recorded on every confirmation.

**Why this priority**: Human confirmation is the ART-VIII implementation. Without it, AI-hallucinated or mis-classified requirements could corrupt the design record.

**Independent Test**: Create a set of proposals; confirm one, edit-then-confirm a second, reject a third; assert only the two confirmed ones appear as Requirement records in the model; assert the rejected one is absent; assert both confirmations carry the confirming actor's identity.

**Acceptance Scenarios**:

1. **Given** an extracted proposal, **When** the architect confirms it, **Then** it enters the canonical model as a typed `Requirement` with a stable id, and an audit entry records the confirming actor, timestamp, and source
2. **Given** an extracted proposal with an incorrect statement, **When** the architect edits the statement and confirms, **Then** the corrected statement enters the model (not the original AI draft); the audit entry records the edit
3. **Given** an extracted proposal the architect determines is not a valid requirement, **When** they reject it, **Then** it is discarded and MUST NOT enter the model; the rejection is recorded for audit completeness
4. **Given** extraction has completed, **When** no action is taken on a proposal within the session, **Then** it remains pending and is not auto-committed; no requirement enters the model without an explicit human action

---

### User Story 3 - Link Requirements to Referenced Capabilities and Principles (Priority: P2)

Where the extracted requirement text references an existing organizational principle or architecture capability by name, ADP identifies the link and proposes it alongside the requirement. The architect confirms or removes the proposed link during the same confirmation step.

**Why this priority**: Linking is a quality enhancement — it enables richer traceability from the outset. Builds on US1 (proposals must exist) and US2 (confirmation must work); neither depends on US3.

**Independent Test**: Submit text that explicitly references a named principle ("must follow the Stateless Services principle"); assert the extracted proposal includes a proposed link to that principle's id; confirm the proposal; assert the resulting Requirement carries the link.

**Acceptance Scenarios**:

1. **Given** a source text that names a known principle or capability, **When** extraction completes, **Then** the proposal includes a proposed `satisfies` link to the referenced item's id
2. **Given** a proposal with a proposed link, **When** the architect confirms the proposal, **Then** the confirmed Requirement carries the link; if they remove the link during confirmation, the Requirement enters the model without it
3. **Given** a source text that mentions no known principles or capabilities, **When** extraction completes, **Then** the proposal contains no proposed links (not an error)

---

### User Story 4 - Observe Extraction Telemetry (Priority: P2)

Every extraction run emits an observable telemetry span that records inputs (source text length, target kind filters), outputs (number of proposals, proposal ids), cost (token usage, estimated spend), and latency. This span is available to the platform's observability tooling.

**Why this priority**: Telemetry is an ART-VI / QG-11 mandate for AI steps. Builds on US1; independent of US2/US3.

**Independent Test**: Submit a batch of requirements text; after extraction completes, assert one telemetry span was emitted per extraction job; assert the span contains inputs, outputs, cost (token count, estimated spend), and latency fields.

**Acceptance Scenarios**:

1. **Given** an extraction job runs, **When** it completes (success or failure), **Then** exactly one telemetry span is emitted per job recording: source character count, number of proposals generated, token usage, estimated cost, and end-to-end latency
2. **Given** an extraction job fails, **When** the failure span is emitted, **Then** the error type and message are recorded; no partial proposals are committed
3. **Given** a telemetry span, **When** it is queried, **Then** the span carries a correlation ID linking it to the originating API request

---

### Edge Cases

- What happens when the submitted text contains no identifiable requirements?
- How are duplicate or near-identical proposals handled (same requirement extracted twice from the same text)?
- What happens when the LLM endpoint is unreachable at extraction time?
- How does the system handle extremely long source texts that exceed the LLM's context window?
- What if the architect partially confirms proposals from a batch — are the unconfirmed ones held or discarded?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Intake MUST accept requirements in at least two input modes: bulk text (plain text or Markdown pasted into a form field) and structured single-requirement entry (one statement per submission); additional input modes (PDF, Word documents) are out of scope for v1
- **FR-002**: Each extracted proposal MUST be typed with: a draft requirement statement, a kind classification (`functional`, `non-functional`, `constraint`, `driver`), a source excerpt from the submitted text, an extraction confidence score (0–1), and a draft stable id
- **FR-003**: No AI-extracted requirement MUST enter the canonical model without an explicit human confirmation action tied to a specific proposal id; confirmation MUST be a distinct, per-proposal action (one approval MUST NOT generalize to other proposals)
- **FR-004**: Every confirmed requirement MUST record in the audit trail: the confirming actor's principal id, the confirmation timestamp, the original source submission id, and whether the statement was edited before confirmation
- **FR-005**: During extraction, the system MUST identify and propose links between extracted requirements and any named principles or capabilities found in the knowledge base (ADP-SPEC-005); proposed links are presented alongside the proposal and confirmed or discarded by the human
- **FR-006**: Each AI extraction job MUST emit one telemetry span per ADP-SPEC-012 recording inputs, outputs (proposal count and ids), token usage, estimated cost in USD, and latency in milliseconds
- **FR-007**: The source excerpt cited by each proposal MUST be a verbatim substring of the submitted text; proposals without a resolvable source excerpt MUST be flagged for extra-scrutiny human review

### Non-Functional Requirements

- **NFR-001**: Extraction MUST run asynchronously; the architect receives an operation handle within 2 seconds of submission; extraction results are polled, not blocking
- **NFR-002**: Every confirmed Requirement MUST validate against the ADP-SPEC-001 schema before entering the canonical model; schema-invalid proposals MUST be rejected with a descriptive error before the confirmation step completes

### Key Entities

- **IntakeSubmission**: The input package provided by the architect; carries the raw text (or structured form fields), submission mode, and a submission id; never stored after extraction is complete (raw text is not retained)
- **ExtractionJob**: The async AI task processing a submission; carries status (`pending`, `running`, `completed`, `failed`), submission id, and an operation handle for polling
- **ExtractedProposal**: An AI-proposed requirement before human action; carries draft statement, kind, source excerpt, confidence score (0–1), proposed link ids, and proposal id; expires if not acted upon within the session
- **ConfirmedRequirement**: A proposal that passed human confirmation; maps 1:1 to a `Requirement` in the canonical model (ADP-SPEC-001); carries the proposal id it originated from for provenance

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of proposals presented to humans for confirmation before any entry to the canonical model; zero auto-committed requirements; verified by audit trail
- **SC-002**: Every confirmed requirement in the model carries a stable id, kind classification, source submission reference, and confirming actor — verified by schema validation on every write
- **SC-003**: Extraction completes and results are available for human review within 60 seconds for submissions up to 5,000 characters under normal LLM endpoint conditions
- **SC-004**: Every extraction job emits exactly one telemetry span with all required fields (inputs, outputs, token count, cost, latency); zero extraction jobs with missing or incomplete spans
- **SC-005**: Where source text names a known principle or capability, the corresponding link proposal is included in the extracted proposals in ≥ 90% of cases; verified by accuracy tests against labeled reference inputs

## Assumptions

- **Input formats (resolved)**: v1 supports two input modes — bulk text paste (plain text or Markdown) and structured single-requirement form entry. PDF and Word document parsing are explicitly out of scope for v1 due to formatting complexity and the need for format-specific parsers without fidelity guarantees; these are deferred to v2.
- **Confidence surfacing (resolved)**: Extraction confidence scores ARE shown to the confirming human alongside each proposal. This is essential for informed review — a low-confidence proposal signals that the architect should scrutinize the source excerpt more carefully before confirming.
- Raw text submissions are processed in memory and are NOT stored after extraction completes. Only the extracted proposals (not the raw source text) are retained until confirmed or rejected. This limits the data retained by ADP.
- The LLM endpoint is configurable by the deployment; this spec does not prescribe a specific model. Organizations with strict data residency requirements can configure an on-premise endpoint.
- "Session" for the purposes of unconfirmed proposal expiry is defined as: the time until the architect closes or navigates away from the confirmation view, or a maximum of 24 hours from extraction completion. Unconfirmed proposals expire without entering the model.
- FR-005 capability/principle linking uses the ADP-SPEC-005 knowledge base for name resolution; the spec does not require extracting links for organizations that have not yet indexed a knowledge base.
- SC-005's "≥ 90% accuracy" target for knowledge base linking is verified for v1 against a hand-crafted representative test fixture (T024–T026); a labeled evaluation corpus for production-accuracy measurement is a v2 prerequisite and is out of scope here.

## Out of Scope

- PDF and Word document parsing (v1 input is text/Markdown only)
- Document storage or long-term retention of submitted source text
- Multi-language source requirements (v1 assumes English-language input)
- Automated requirement de-duplication (near-duplicates are flagged but the human decides)
- Recommendation generation from confirmed requirements (ADP-SPEC-007)
- The LLM endpoint itself; this spec consumes a configurable endpoint
- ADP-SPEC-012 telemetry pipeline and dashboard (the pipeline is assumed to exist; this spec emits spans to it)
