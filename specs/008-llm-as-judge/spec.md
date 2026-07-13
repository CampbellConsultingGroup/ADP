# Feature Specification: LLM-as-a-Judge Validation

**Feature Branch**: `008-llm-as-judge`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-008 — LLM-as-a-Judge Validation"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — The Model is the Single Source of Truth: `Verdict` and `Finding` records are written to the canonical model (ADP-SPEC-001); validation operates on the canonical design, not a copy
- **ART-IV** — Test-Driven Development: always applies; every critic path and gating rule requires a test before implementation
- **ART-V** — Security by Design: in scope; design content is sensitive organizational IP — same LLM endpoint and data-residency constraints as ADP-SPEC-006/007 apply
- **ART-VI** — Observability is Not Optional: every critic MUST emit a telemetry span (FR-007 / QG-11)
- **ART-VII** — Grounded AI Only: central concern; every finding MUST cite the specific standard, principle, or pattern it judges against, with version (FR-002 / QG-12)
- **ART-VIII** — Human-in-the-Loop for Consequence: in scope; human overrides of verdicts are consequential actions requiring explicit justification and audit (FR-006 / QG-13, QG-14)
- **ART-IX** — Provenance and Auditability: in scope; verdict history is linked to design versions; overrides carry actor and justification (NFR-002 / QG-13)
- **ART-X** — Deterministic Validation Gating: the primary article this spec implements; given the same critic scores the gate decision MUST be identical every time (FR-004 / QG-15)
- **ART-XI** — Traceability End to End: in scope; orphan elements (no satisfied requirement) MUST fail validation (FR-005 / QG-16)
- **ART-XIII** — Typed Contracts Everywhere: `Verdict`, `Finding`, and `CriticOutput` are typed entities; no untyped dicts at critic boundaries

## Threat Model *(mandatory — ART-V)*

Validation handles design content (organizational IP) and produces authoritative governance decisions. A corrupted or biased validation could approve a non-compliant design or block a compliant one.

**Assets at risk**: Design content sent to the LLM (confidential architectural decisions); the `Verdict` record (authoritative pass/fail for a design version); the audit trail of overrides.

**Trust boundaries crossed**: Architect → Platform API → validation orchestrator → LLM (same configurable endpoint as ADP-SPEC-006/007); validation orchestrator → ADP-SPEC-005 knowledge retrieval.

**Abuse cases**:
- **Non-deterministic verdict**: Two identical validation runs produce different pass/fail outcomes → Mitigation: FR-004 (deterministic gating); QG-15 enforces that given identical critic scores the decision is always the same
- **Uncited finding**: A critic flags a violation without citing a standard → Mitigation: FR-002 (citation required); uncited findings are marked advisory only and MUST NOT block a design without human review
- **Verdict override without justification**: A reviewer approves a failing design without explanation → Mitigation: FR-006 (justification required); ADP-SPEC-003's confirmation endpoint enforces this via QG-14
- **Stale verdict**: A design is modified after validation and the old passing verdict is misrepresented as current → Mitigation: NFR-002 (verdicts linked to design version); the API MUST surface the verdict's design version alongside the verdict

**Residual risk**: LLM bias toward approving designs that match training distribution — mitigated by knowledge-grounded critics (ART-VII) and explicit scoring rubrics.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate a Design and Receive Cited Findings (Priority: P1)

An architect requests validation of their design. The system fans out to independent critics — standards critic, principles critic, pattern-fit critic, consistency critic — each retrieving and citing the specific knowledge items it judges against. The results aggregate into a `Verdict` with a score and a list of cited findings.

**Why this priority**: Cited findings are the core value. Without them, validation is a black box and architects cannot act on the results.

**Independent Test**: Submit a known design with deliberate violations; assert findings are returned for each violated standard/principle; assert every finding cites a knowledge item id and version; assert no finding lacks a citation.

**Acceptance Scenarios**:

1. **Given** a design is submitted for validation, **When** all critics complete, **Then** the result contains a `Verdict` with a score, a pass/fail decision, and a list of `Finding` records each identifying the offending element, the violated knowledge item (with id and version), a severity, and a human-readable description
2. **Given** a critic judges a design element against a standard, **When** it produces a finding, **Then** the finding MUST cite the specific standard id and version from the knowledge base (ADP-SPEC-005); uncited findings are marked advisory
3. **Given** no violations are found, **When** all critics complete, **Then** the `Verdict` has a passing decision and zero blocking findings

---

### User Story 2 - Review Aggregated Verdict with Deterministic Pass/Fail Decision (Priority: P1)

An architect reviews the aggregated verdict. The pass/fail decision is deterministic — running validation twice on the same design version with the same critic scores produces the same result. The gating thresholds are explicitly configured and visible to the architect.

**Why this priority**: Deterministic gating is the ART-X mandate. Without it, "approved" has no consistent meaning. Builds on US1 (critics must run first).

**Independent Test**: Run two validation passes on the same design with mocked critics returning identical scores; assert the pass/fail decisions are identical; change one score past a configured threshold; assert the decision changes accordingly.

**Acceptance Scenarios**:

1. **Given** the same set of critic scores, **When** the gating rule is applied twice, **Then** the pass/fail decision is identical both times
2. **Given** configured thresholds (`critical=0`, `major≤2`, `minor≤5`), **When** findings count at each severity falls within the threshold, **Then** the design passes; when any threshold is exceeded, the design fails
3. **Given** a design passes validation, **When** the verdict is queried, **Then** it carries the design version id and the threshold configuration in effect at the time — so the decision can be reconstructed

---

### User Story 3 - Detect Orphan Elements and Dangling References (Priority: P2)

Structural validation catches elements that have no satisfied requirement (orphan elements) and elements that reference a non-existent peer (dangling reference). These fail validation regardless of any LLM critic score.

**Why this priority**: Structural integrity is a prerequisite for meaningful semantic validation. Builds on US1 (validation framework must exist).

**Independent Test**: Submit a design with one orphan element and one dangling element reference; assert two structural findings are returned; assert both are severity "critical"; assert overall verdict is fail.

**Acceptance Scenarios**:

1. **Given** a design contains an element with an empty `satisfies` list and no relationship to any requirement, **When** validated, **Then** a structural finding is raised for that element with severity `critical` and no LLM critic is needed to fail the design
2. **Given** a design contains a `Relationship` with a `target` that does not exist in the design's elements, **When** validated, **Then** a dangling-reference finding is raised
3. **Given** a design has no structural violations, **When** the structural check runs, **Then** it completes without findings and LLM critics proceed

---

### User Story 4 - Override a Verdict with Recorded Justification (Priority: P2)

A reviewer with appropriate permissions overrides a failing verdict — for example, accepting a design that violates a pattern because a documented exception applies. The override is explicit, requires a justification, and is permanently recorded in the audit trail with the reviewer's identity.

**Why this priority**: Override capability makes validation governable rather than blocking. Without it, a single misconfigured threshold could halt all work.

**Independent Test**: Submit a failing verdict; attempt override without justification and assert rejection; submit override with justification; assert verdict status changes to `overridden`; assert audit trail carries reviewer id, timestamp, and justification text.

**Acceptance Scenarios**:

1. **Given** a failing verdict, **When** a reviewer submits an override without a justification, **Then** the override is rejected with a clear error; the verdict remains failing
2. **Given** a failing verdict, **When** a reviewer submits an override with a justification, **Then** the verdict status becomes `overridden`; the justification, reviewer id, and timestamp are recorded in the audit trail
3. **Given** an overridden verdict, **When** a subsequent validation run produces a new verdict, **Then** the new verdict starts fresh; the prior override is in history and does not carry forward

---

### User Story 5 - Inspect Each Critic's Telemetry (Priority: P2)

Every critic emits an observable telemetry span that records: the knowledge items retrieved, the design element(s) evaluated, the LLM input and output token counts, the cost, and the latency. This enables debugging, cost attribution, and audit.

**Why this priority**: ART-VI / QG-11 mandate. Without per-critic spans, the validation pipeline cannot be trusted, debugged, or governed.

**Independent Test**: Run a validation job; assert one span is emitted per critic; assert each span carries retrieved knowledge refs with versions, input/output token counts, cost estimate, and latency; assert all spans share the job's correlation ID.

**Acceptance Scenarios**:

1. **Given** a validation job runs, **When** all critics complete, **Then** one telemetry span is emitted per critic (minimum: standards, principles, pattern-fit, consistency, structural) recording retrieved-knowledge refs, tokens, cost, and latency
2. **Given** a critic fails, **When** its span is emitted, **Then** the error type is recorded; no partial results from the failed critic contribute to the verdict
3. **Given** all critic spans for one job, **When** correlated, **Then** they share a correlation ID linking them to the originating API request

---

### Edge Cases

- What happens when the knowledge base has no items relevant to the design's domain?
- How is the verdict handled when one critic times out but others complete?
- What happens when a design version is re-validated after being updated?
- How does gating behave when a critic produces zero findings (success) versus failing to run?
- What is the minimum number of critics required for a valid verdict?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Validation MUST fan out to at least four independent critic dimensions in parallel: (a) standards — does the design comply with applicable organizational standards?; (b) principles — does the design follow applicable architecture principles?; (c) pattern-fit — does the design appropriately compose retrieved patterns?; (d) consistency — is the design consistent with prior approved solutions in the knowledge base?
- **FR-002**: Each critic MUST retrieve relevant knowledge from ADP-SPEC-005 before judging; every finding a critic produces MUST cite the specific knowledge item id and version it judges against; findings without a resolvable citation MUST be marked `advisory` and MUST NOT count toward blocking thresholds
- **FR-003**: Critic outputs MUST aggregate into a single `Verdict` per validation run, carrying: a composite score (0–1), a list of `Finding` records (each with element id, severity, description, citation), and a deterministic pass/fail decision derived from the configured thresholds
- **FR-004**: Gating thresholds — maximum counts of `critical`, `major`, and `minor` severity findings before a design fails — MUST be explicit, versioned configuration; given identical critic scores and thresholds, the pass/fail decision MUST be the same on every evaluation
- **FR-005**: The structural critic MUST check referential integrity before LLM critics run; any element with no `satisfies` link (orphan) or any relationship with an unresolvable endpoint (dangling reference) MUST produce a `critical` finding that immediately fails the design
- **FR-006**: A human reviewer MAY override a failing verdict; the override MUST carry a non-empty justification text; the override, the reviewer's principal id, and the timestamp MUST be recorded in the audit trail via ADP-SPEC-004's `write_audit_record`; the override is a single-use consequential action per ADP-SPEC-003's confirmation endpoint
- **FR-007**: Each critic MUST emit one telemetry span per ADP-SPEC-012 carrying: critic name, retrieved knowledge refs with versions, element ids evaluated, input/output token counts, estimated cost in USD, latency in milliseconds, and the correlation ID from the originating request

### Non-Functional Requirements

- **NFR-001**: Validation MUST run asynchronously; the operation handle MUST be available within 2 seconds; full fan-out completion MUST occur within 120 seconds for typical designs (≤ 500 elements) under normal LLM endpoint conditions
- **NFR-002**: Each `Verdict` MUST record the design version id it evaluated; for v1, verdicts are accessible via their operation handle within the operation TTL (24 hours); long-term verdict history queryable by design id and version number is deferred to v2 when a persistent `validation_verdicts` table will be added; a verdict MUST NOT be interpreted as valid for a design version other than the one it evaluated

### Key Entities

- **ValidationJob**: The async job for one validation run; carries status, design id, design version, operation handle, and result reference
- **CriticOutput**: The raw output of one critic; carries critic name, score (0–1), list of `Finding` records, retrieved knowledge citations, and token usage
- **Finding**: One identified issue or compliance observation; carries element id, severity (`critical`, `major`, `minor`, `advisory`), description, citation (`CitationRef` from ADP-SPEC-005), and the critic that raised it
- **Verdict**: The aggregated result of one validation run; carries composite score, pass/fail decision, design version id, threshold configuration snapshot, list of all findings, status (`pass`, `fail`, `overridden`), and override details if applicable
- **GatingThreshold**: The configurable threshold set in force for a validation run; carries max `critical`, `max_major`, `max_minor` finding counts; versioned alongside the design

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of findings produced by any critic carry a verifiable citation (knowledge item id + version); zero uncited findings counted toward blocking thresholds; verified by citation completeness tests
- **SC-002**: Given the same design version and critic scores, the pass/fail decision is identical on every evaluation run; verified by determinism tests that run gating twice with the same inputs and assert equality
- **SC-003**: Full fan-out validation (all critics) completes within 120 seconds for designs of up to 500 elements; verified by performance tests with mocked critics
- **SC-004**: Every validation job emits one telemetry span per critic with all required fields; zero jobs with missing or incomplete spans; verified by telemetry tests
- **SC-005**: 100% of human verdict overrides carry a non-empty justification and a recorded actor identity; zero overrides without an audit entry; verified by override audit tests

## Assumptions

- **Gating thresholds (resolved)**: Default thresholds for v1 are: `max_critical=0` (any critical finding fails), `max_major=3`, `max_minor=10`. These are configurable per deployment via `ADP_VALIDATION_MAX_CRITICAL`, `ADP_VALIDATION_MAX_MAJOR`, `ADP_VALIDATION_MAX_MINOR`. Organizations can also configure per-design-type overrides via an explicit `GatingThreshold` record. This is the v1 baseline; threshold management per organization is a v2 governance configuration feature.
- **Critic calibration (resolved)**: Score stability across model versions is maintained by including explicit scoring rubrics in each critic's system prompt — e.g., "score 1.0 = fully compliant; 0.7 = minor deviation acceptable; 0.4 = significant gap; 0.0 = clear violation with citation." Combined with `temperature=0` sampling and deterministic gating (ART-X), this approach prevents score drift from causing unexpected gate reversals. Formal calibration datasets are a v2 concern.
- Validation uses the same configurable LLM endpoint as ADP-SPEC-006/007 (`ADP_LLM_BASE_URL`, `ADP_LLM_MODEL`). No separate LLM is required.
- The four LLM critics (standards, principles, pattern-fit, consistency) run in parallel; the structural critic runs first as a pre-check and blocks LLM critics if structural failures are found.
- A validation run evaluates the **latest committed version** of the design. Uncommitted (pending) changes are not validated.
- The `advisory` severity is for informational findings that do not count toward any blocking threshold but are visible to the reviewer.
- Critic scores are per-critic (0–1) and aggregate to a composite score using an equal-weighted mean. Weighted aggregation is a v2 configuration feature.

## Out of Scope

- Recommendation generation (ADP-SPEC-007 — consumed but not owned here)
- Authoring or editing standards, principles, and patterns (knowledge authoring)
- Per-organization gating threshold management UI (deferred to v2)
- Formal calibration datasets and automated calibration runs (deferred to v2)
- Validation of AI-generated content within the design (circular — ADP handles design structures, not the quality of design narrative prose)
