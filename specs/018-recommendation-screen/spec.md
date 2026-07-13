# Feature Specification: Architecture Recommendation Screen

**Feature Branch**: `018-recommendation-screen`
**Created**: 2026-07-02
**Status**: Draft
**Input**: `/home/jmuir/projects/ADP/docs/018-recommendation-screen.md`

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-VII** — Grounded AI Only: all recommendation options carry `grounded_on` citations; options without full grounding are marked `advisory` and require explicit architect acknowledgement before acceptance
- **ART-VIII** — Human-in-the-Loop: accepting a recommendation is consequential; the architect must explicitly confirm before proposed elements are written to the canonical model
- **ART-IX** — Provenance and Auditability: every accepted option writes an audit entry recording the actor, option ID, and timestamp
- **ART-XI** — Traceability: accepted option's proposed elements carry `provenance = option_id`, linking every element back to the recommendation that produced it

**ART-V (security)**: Low risk — same Anthropic API pattern as intake. No new credential surfaces.

## Threat Model

No new threat surface beyond what ADP-SPEC-015 introduced for LLM calls. The accept endpoint is a consequential mutation requiring explicit confirmation (ART-VIII / QG-14).

## User Scenarios

### User Story 1 — Request and View Recommendations (Priority: P1)

The architect has confirmed requirements on their design and wants AI-generated solution options. They open the Recommendations screen, see their confirmed requirements listed, click "Get Recommendations", and wait (the pipeline is async — same polling pattern as intake). Within 30 seconds, up to 3 ranked options appear. Each shows: rank number, title, a rationale paragraph, a trade-off table, the proposed C4 elements that would be added, and the knowledge items cited.

**Why this priority**: The core value of the recommendation engine. Without this screen it is completely inaccessible.

**Independent Test**: POST `/recommend` with requirement IDs; poll until complete; assert ≥ 1 option with title, rationale, and proposed_elements.

**Acceptance Scenarios**:

1. **Given** a design with confirmed requirements, **When** the architect clicks "Get Recommendations", **Then** an operation is started and the screen shows a progress indicator.
2. **Given** the pipeline completes successfully, **When** the results are shown, **Then** each option displays its rank, title, rationale, trade-off table, and list of proposed elements (name, kind, description).
3. **Given** the pipeline completes with advisory options, **When** displayed, **Then** a warning badge appears on advisory options.
4. **Given** the knowledge base is empty, **When** recommendations complete, **Then** all options are marked advisory; the screen explains why rather than showing an error.

---

### User Story 2 — Accept a Recommendation (Priority: P1)

The architect reviews the ranked options and decides to accept one. They click "Accept this option" and see a confirmation dialog naming the option and listing the elements that will be added. They click "Confirm" and are navigated to the C4 canvas where the new elements appear.

**Why this priority**: Accepting a recommendation is the payoff — it materialises the AI-generated architecture into the canonical model.

**Independent Test**: POST `/recommend/.../options/{id}/accept` with `confirmation_id`; assert 200; assert design has new elements with `provenance = option_id`; assert audit entry written.

**Acceptance Scenarios**:

1. **Given** a pending option, **When** the architect clicks "Accept this option", **Then** a confirmation dialog appears listing the option title and the elements that will be added before any change is made (ART-VIII).
2. **Given** the architect confirms acceptance, **When** the request completes, **Then** the proposed elements appear in the design and the screen navigates to the C4 canvas.
3. **Given** an advisory option, **When** the architect attempts acceptance, **Then** the confirmation dialog includes an additional warning that the option lacks full grounding, and the architect must check an acknowledgement checkbox before confirming.
4. **Given** an already-accepted option, **When** acceptance is attempted again, **Then** the API returns 409 and the UI shows "Already accepted".

---

### User Story 3 — Select Requirements for Recommendation (Priority: P2)

By default all confirmed requirements are included in the recommendation request. The architect can deselect individual requirements to narrow the recommendation scope (for example, to get options focused only on performance NFRs).

**Why this priority**: P2 because the default (all requirements) is the common case. Deselection is an enhancement.

**Acceptance Scenarios**:

1. **Given** 5 confirmed requirements, **When** the Recommendations screen loads, **Then** all 5 are shown checked by default.
2. **Given** the architect unchecks 2 requirements, **When** "Get Recommendations" is clicked, **Then** only the 3 checked requirement IDs are sent in the request.

---

### Edge Cases

- What if there are no confirmed requirements? The "Get Recommendations" button is disabled with "Add requirements first via the Intake screen."
- What if the LLM call fails? The operation status is "failed" with an error description; the architect can retry.
- What if all proposed elements already exist on the canvas (e.g. name collision)? The `materialize_option()` method creates new elements regardless; the architect can then merge or delete duplicates on the canvas.

## Requirements

### Functional Requirements

- **FR-001**: `POST /api/v1/designs/{id}/recommend` MUST accept `requirement_ids: list[str]` and return `operation_id` and `status: "pending"` immediately (async background task).
- **FR-002**: `GET /api/v1/designs/{id}/recommend/{operation_id}` MUST return status and, when complete, a list of `SolutionOptionResponse` records sorted by rank ascending.
- **FR-003**: `POST /api/v1/designs/{id}/recommend/{operation_id}/options/{option_id}/accept` MUST require a non-empty `confirmation_id` (ART-VIII); on success write elements + audit entry; return the list of created elements.
- **FR-004**: Each `SolutionOptionResponse` MUST include: `option_id`, `rank`, `title`, `rationale`, `advisory` (bool), `satisfies` (requirement IDs), `trade_offs` (list of criterion/stance/rationale), `proposed_elements` (name/kind/description), `grounded_on` (citation IDs), `ranking_score`, `status`.
- **FR-005**: Advisory options MUST be visually distinguished with a warning badge; the accept confirmation dialog MUST include an advisory acknowledgement checkbox for advisory options.
- **FR-006**: After successful acceptance, the UI MUST navigate to the C4 canvas.
- **FR-007**: The workspace navigation header MUST include "Recommendations" between "Intake" and "Canvas" (accessible from the intake screen header and canvas header).
- **FR-008**: The screen MUST list confirmed requirements with checkboxes; all checked by default; the "Get Recommendations" button is disabled when no requirements are checked.

### Key Entities

- **RecommendRequest**: `requirement_ids: list[str]`, `model: str | None` (optional LLM model override, same as intake)
- **RecommendStatusResponse**: `operation_id`, `design_id`, `status`, `options: list[SolutionOptionResponse]`, `result_summary`, `error_description`
- **SolutionOptionResponse**: All `SolutionOption` fields in API-serializable form (dataclass → Pydantic)
- **AcceptOptionRequest**: `confirmation_id: str` (non-empty, ART-VIII)
- **AcceptOptionResponse**: `option_id`, `elements_created: list[ElementSummary]`

## Success Criteria

- **SC-001**: A recommendation request for a design with 2+ requirements returns ≥ 1 option within 60 seconds (same latency budget as intake, SC-001 in ADP-SPEC-018).
- **SC-002**: Accepting an option produces elements on the canvas with `provenance` fields pointing to the accepted option ID — verifiable via `GET /api/v1/designs/{id}`.
- **SC-003**: No option is materialised without an explicit architect confirmation — zero silent auto-accepts (ART-VIII / QG-14).
- **SC-004**: The workspace header shows Intake → Recommendations → Canvas navigation in all three views.

## Assumptions

- `RecommendationOrchestrator` from ADP-SPEC-007 is the complete backend; this spec only wires HTTP and React UI.
- The knowledge base (pgvector) may be empty; options will be advisory. The UI handles this gracefully with explanatory text.
- The same Anthropic LLM client and model selection from ADP-SPEC-015 is reused.
- `confirmation_id` for accept follows the same non-empty-string pattern as export (ADP-SPEC-011 / ART-VIII).
- The `materialize_option()` audit ID generation will use `_next_audit_id()` (ADP-SPEC-017 fix) to avoid collisions.
