# Feature Specification: Recommendation Reasoning Display

**Feature Branch**: `028-recommendation-reasoning-ui`
**Created**: 2026-07-04
**Status**: Draft
**Depends on**: ADP-SPEC-027 (Immutable LLM Reasoning Store)

## Context

The recommendation screen shows architects ranked options with rationale summaries and trade-off tables. Currently these are static fields — the reasoning behind each recommendation is summarised in 1-2 sentences and the trade-off stances are listed but the LLM's full analysis is hidden.

Architects need to understand *why* the AI suggested each option before they can responsibly accept or reject it. "Addresses scalability via horizontal scaling" is not enough context for an enterprise architect deciding whether to restructure a platform. The full reasoning — what evidence was used, what alternatives were considered in the trade-off analysis, what limitations were noted — must be visible and readable.

This spec adds a collapsible Reasoning panel to each option card on the recommendation screen, populated from the immutable reasoning log created in ADP-SPEC-027. The reasoning is not an afterthought or a tooltip — it is a primary first-class element that gives architects the transparency to trust and use AI recommendations responsibly.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-VII** — AI Grounding: the displayed reasoning must always link to the specific knowledge items that grounded it
- **ART-VIII** — Human in the Loop: reasoning display is a prerequisite for informed human decision-making; architects cannot responsibly accept recommendations they cannot understand

## Threat Model

**Assets at risk**: Reasoning text may contain internal model behaviour details. Mitigated by requiring authentication (ADP-SPEC-026) to access the reasoning API.

**Trust boundaries crossed**: Browser ↔ ADP API (reasoning endpoint from ADP-SPEC-027).

**Residual risk**: None significant beyond the auth gate from ADP-SPEC-026.

## User Scenarios & Testing

### User Story 1 — Architect Reads Full Reasoning Before Accepting (Priority: P1)

An architect opens the Recommendations screen, sees three ranked options, and before accepting option #1 clicks "Show reasoning". A panel expands showing the LLM's full explanation for why this option addresses the requirements, what trade-offs were considered, which knowledge base items were cited, and when the reasoning was generated.

**Why this priority**: Core value — without this, architects are accepting recommendations they cannot fully understand.

**Independent Test**: Navigate to Recommendations for a completed operation; click "Show reasoning" on an option card; assert the reasoning panel appears with non-empty text content.

**Acceptance Scenarios**:

1. **Given** a completed recommendation operation, **When** the architect clicks "Show reasoning" on an option card, **Then** a panel expands showing the generation rationale, the trade-off analysis, and the knowledge citations.
2. **Given** the reasoning panel is open, **When** the architect clicks "Hide reasoning", **Then** the panel collapses.
3. **Given** reasoning records are loading from the API, **When** the request is in-flight, **Then** a loading skeleton is shown so the card layout does not jump.
4. **Given** reasoning records are not yet available (pipeline still running), **Then** the "Show reasoning" button is disabled with tooltip "Reasoning available once analysis completes".

---

### User Story 2 — Knowledge Citations are Clearly Attributed (Priority: P2)

For each option, the reasoning panel lists the knowledge base items that were retrieved and used to ground the recommendation, with their kind (principle, pattern, standard) and title displayed as readable chips.

**Why this priority**: ART-VII requires AI outputs to be grounded; the display must make this traceability visible to the architect.

**Acceptance Scenarios**:

1. **Given** an option is grounded on two knowledge items, **When** the reasoning panel is expanded, **Then** both items are shown with their kind badge and title.
2. **Given** an option has `knowledge_source = "requirements_only"`, **Then** the citation section shows "Generated from requirements — no prior knowledge base entries available" instead of citations.

---

### User Story 3 — Trade-off Reasoning is Structured and Scannable (Priority: P3)

Each criterion in the trade-off table has an expandable reasoning row that shows the LLM's full assessment text, not just the stance label. An architect reviewing "Security: partially meets" can click to read the full explanation.

**Acceptance Scenarios**:

1. **Given** a trade-off row with stance `"partially_meets"`, **When** the architect clicks the stance, **Then** the full LLM rationale for that criterion is shown.
2. **Given** trade-off reasoning from the `analyze_tradeoffs` step, **When** displayed, **Then** the text is rendered as plain prose (no Markdown, no code fences).

---

### Edge Cases

- No reasoning records (old recommendation before ADP-SPEC-027 was deployed): "Reasoning not available for this recommendation" shown instead of the panel.
- Reasoning text exceeds display threshold: truncated at 2,000 characters with "Read more" expansion.
- Pipeline failed before reasoning was written: same "not available" state as above.

## Requirements

### Functional Requirements

**API Extension (FR-001 to FR-002)**

- **FR-001**: The reasoning read endpoint from ADP-SPEC-027 (`GET /api/v1/reasoning?operation_id=&option_id=`) MUST also accept no `option_id` to return all reasoning for the operation, or a specific `option_id` to return only records for that option.
- **FR-002**: The API response for each record MUST include: `id`, `option_id`, `step_name`, `model_id`, `reasoning_text`, `input_tokens`, `output_tokens`, `created_at`. `prompt_hash` is excluded from the client-facing response.

**Frontend (FR-003 to FR-009)**

- **FR-003**: A `useOptionReasoning(designId, operationId, optionId)` TanStack Query hook MUST be added that fetches reasoning records for a specific option from `GET /api/v1/reasoning?operation_id=&option_id=`.
- **FR-004**: Each `OptionCard` component MUST include a "Show reasoning" / "Hide reasoning" toggle button below the trade-off table.
- **FR-005**: When expanded, the reasoning panel MUST display three sections in order:
  1. **Generation reasoning** — the `reasoning_text` from the `"generate"` step (why this option was proposed)
  2. **Trade-off analysis** — the `reasoning_text` from the `"analyze_tradeoffs"` step (full analysis vs each criterion)
  3. **Knowledge citations** — the option's `grounded_on` list rendered as kind-badged chips with titles resolved from the knowledge base
- **FR-006**: The reasoning panel MUST show the model ID and timestamp of when reasoning was generated (from `model_id` and `created_at` of the first record).
- **FR-007**: When reasoning is loading, a skeleton placeholder MUST be shown that matches the panel's expected height to prevent layout shift.
- **FR-008**: When no reasoning is available for an option, the button MUST be replaced with a disabled "No reasoning recorded" state.
- **FR-009**: The `knowledge_source` field on the option MUST control the citation section: `"requirements_only"` shows the "generated from requirements" notice instead of citation chips.

### Key Entities

- **ReasoningPanel**: displays `generate` + `analyze_tradeoffs` records and citation chips for one option
- Reuses existing `KnowledgeItemSummary` from ADP-SPEC-020 for rendering citation chips

## Success Criteria

- **SC-001**: An architect can read the full LLM reasoning for any option without leaving the recommendation screen.
- **SC-002**: The reasoning panel renders within 1 second of clicking "Show reasoning" (API response is fast since records are pre-written during pipeline execution).
- **SC-003**: Knowledge citations are always displayed with their actual title from the knowledge base (not just raw IDs).
- **SC-004**: The reasoning display works correctly for options with `knowledge_source = "requirements_only"` — no broken citation section.

## Assumptions

- ADP-SPEC-027 is deployed and reasoning records exist for all new recommendation operations before this spec is implemented.
- For existing operations created before ADP-SPEC-027, the "No reasoning recorded" state is the correct fallback — no backfill of historical reasoning is attempted.
- The trade-off analysis reasoning in the `analyze_tradeoffs` reasoning record is the full text from the LLM including all criterion assessments (not one record per criterion). The UI presents it as a single prose block.
- The knowledge citation chips resolve titles by calling the knowledge API or using already-loaded knowledge items.
- Reasoning text is plain text — no Markdown rendering required. Line breaks are preserved.
**Created**: [DATE]  
**Status**: Draft  
**Input**: User description: "$ARGUMENTS"

## Constitutional Articles Touched *(mandatory — ART-I)*

List every article from the ADP Constitution that this feature engages. At minimum state whether
the feature is in scope for ART-V (security/threat model) and ART-VII (AI grounding).

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **[ART-N]** — [Title]: [How this feature engages it]

## Threat Model *(mandatory — ART-V)*

Provide a brief threat model proportional to the feature's risk. For low-risk, internal-only
features a single paragraph is sufficient; for features touching auth, data export, AI outputs,
or external integrations, expand each section.

**Assets at risk**: [What data or capabilities could be harmed — e.g., user designs, auth tokens]

**Trust boundaries crossed**: [Which system borders this feature spans — e.g., browser→API, API→LLM]

**Abuse cases**:
- [Attacker goal]: [How they could abuse this feature] → [Mitigation]

**Residual risk**: [Accepted risks and why they are acceptable at this threat level]

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently - e.g., "Can be fully tested by [specific action] and delivers [specific value]"]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this user journey in plain language]

**Why this priority**: [Explain the value and why it has this priority level]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- What happens when [boundary condition]?
- How does system handle [error scenario]?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: System MUST [specific capability, e.g., "allow users to create accounts"]
- **FR-002**: System MUST [specific capability, e.g., "validate email addresses"]  
- **FR-003**: Users MUST be able to [key interaction, e.g., "reset their password"]
- **FR-004**: System MUST [data requirement, e.g., "persist user preferences"]
- **FR-005**: System MUST [behavior, e.g., "log all security events"]

*Example of marking unclear requirements:*

- **FR-006**: System MUST authenticate users via [NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]
- **FR-007**: System MUST retain user data for [NEEDS CLARIFICATION: retention period not specified]

### Key Entities *(include if feature involves data)*

- **[Entity 1]**: [What it represents, key attributes without implementation]
- **[Entity 2]**: [What it represents, relationships to other entities]

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: [Measurable metric, e.g., "Users can complete account creation in under 2 minutes"]
- **SC-002**: [Measurable metric, e.g., "System handles 1000 concurrent users without degradation"]
- **SC-003**: [User satisfaction metric, e.g., "90% of users successfully complete primary task on first attempt"]
- **SC-004**: [Business metric, e.g., "Reduce support tickets related to [X] by 50%"]

## Assumptions

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right assumptions based on reasonable defaults
  chosen when the feature description did not specify certain details.
-->

- [Assumption about target users, e.g., "Users have stable internet connectivity"]
- [Assumption about scope boundaries, e.g., "Mobile support is out of scope for v1"]
- [Assumption about data/environment, e.g., "Existing authentication system will be reused"]
- [Dependency on existing system/service, e.g., "Requires access to the existing user profile API"]
