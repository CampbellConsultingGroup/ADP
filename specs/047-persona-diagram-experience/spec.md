# Feature Specification: Persona-Differentiated Diagram Experience

**Feature Branch**: `047-persona-diagram-experience`
**Created**: 2026-08-11
**Status**: Draft
**Input**: User description: "ADP-914.6: Persona-differentiated diagram experience for the new standalone diagram types (ADP-SPEC-046). Today WRITE_DIAGRAM gates WHO can create/edit diagrams but nothing differentiates WHAT each persona sees or is steered toward -- DiagramsPage.tsx shows the identical generic 5-type list/editor to every role."

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-V** — Security by Design: does **not** meaningfully apply — this feature changes UI presentation/defaults only; it introduces no new data exposure, no new authorization surface, and does not weaken or extend `WRITE_DIAGRAM` (see Assumptions). Reviewed and confirmed low-risk (see Threat Model).
- **ART-VI** — Observability is Not Optional: does not apply — no new mutation type, no new AI orchestration span; this is a pure client-side presentation choice with no server round-trip of its own.
- **ART-VII, ART-VIII, ART-IX, ART-X, ART-XI** — do **not** apply: no AI-generated content, no AI proposal for a human to confirm, nothing added to the audit trail, no validation gating, no traceability thread. Consistent with ADP-SPEC-046, which this feature extends.
- **ART-XII** — Fixed Visual Language: does not apply — governs the locked C4 theme specifically; this feature touches only the non-C4 diagram type selector's presentation, not any rendered diagram's visual styling.
- **ART-XIII** — Typed Contracts Everywhere: applies only incidentally — the persona→default-type mapping is a plain, typed, in-memory constant (no new API boundary, no new Pydantic model, no backend change at all — see Assumptions).
- **ART-XIV, ART-XV** — Reproducible builds / Schema evolution: do not apply — no migration, no schema change of any kind.
- **ART-XVI** — Documentation as Code: applies (SHOULD) — a short note in `web/src/diagrams/README.md` on the persona-mapping convention.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none beyond what ADP-SPEC-046 already accepted — this feature adds no new data, no new storage, no new read/write path. It only changes which diagram type is pre-selected and how the 5 existing types are ordered/labeled in an already-authorized user's own editor.

**Trust boundaries crossed**: none new — the signed-in user's `role` is already available client-side via the existing `useAuth()` hook (used today for role-based UI display like `roleLabel`/`roleColors`); this feature reads that same value to pick a default, nothing more.

**Abuse cases**: none identified beyond ADP-SPEC-046's own threat model — a user's own client-side default/ordering preference cannot affect another user, cannot be spoofed into granting a capability they don't already have (creation is still gated by the existing, unchanged `WRITE_DIAGRAM` check), and at worst a manipulated `role` value client-side would only mis-steer *that same user's own* default selection — an inconvenience, not a security boundary.

**Residual risk**: none beyond ADP-SPEC-046's existing accepted risk. This is presentation-only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New diagram defaults to the type that best fits my role (Priority: P1)

An Enterprise Architect, Solution Architect, or Technical Architect clicks "+ New Diagram." Instead of always starting on the same generic default, the diagram-type selector opens pre-set to the type that best matches their role's typical work — but they can still change it to any of the other 4 types before their first save, exactly as today.

**Why this priority**: This is the core of "persona-differentiated" — the single highest-value, lowest-risk change: it saves every architect a manual selection on the single most common path (starting a brand-new diagram) without taking away any choice.

**Independent Test**: Sign in as each of the three architect roles in turn, click "+ New Diagram," and confirm the diagram-type selector's pre-selected value matches that role's mapped default (see FR-002). Manually change the selection and confirm the override is respected exactly as before this feature (unchanged behavior from ADP-SPEC-046).

**Acceptance Scenarios**:

1. **Given** a signed-in Enterprise Architect, **When** they click "+ New Diagram," **Then** the diagram-type selector is pre-set to their role's mapped default type.
2. **Given** a signed-in Solution Architect, **When** they click "+ New Diagram," **Then** the diagram-type selector is pre-set to their role's mapped default type (different from the Enterprise Architect's default).
3. **Given** a signed-in Technical Architect, **When** they click "+ New Diagram," **Then** the diagram-type selector is pre-set to their role's mapped default type (different from the other two roles' defaults).
4. **Given** the diagram-type selector has opened to a role's default, **When** the user manually selects a different type before their first save, **Then** the new diagram is created with the manually-chosen type, not the default — the default only pre-sets the initial selection, it never overrides an explicit choice.

---

### User Story 2 - The type selector shows me which types are most relevant to my role (Priority: P2)

While choosing a diagram type (either on creation, per User Story 1, or when browsing what's available), a user sees their role's most-relevant type visually distinguished from the other four — e.g. labeled "Recommended for your role" — so they can quickly recognize it without having to already know the mapping, while every type remains equally selectable.

**Why this priority**: Builds on User Story 1's default with a lighter-touch, purely-informational layer that helps users understand *why* a particular type was pre-selected and make an informed choice if they want something else. Lower priority than US1 because the default itself (US1) already delivers most of the time-saving value; this is a clarity/discoverability improvement on top.

**Independent Test**: Open the diagram-type selector as any of the three architect roles and confirm exactly one of the five options is visually marked as recommended, matching that role's mapping from FR-002, while all five remain clickable/selectable.

**Acceptance Scenarios**:

1. **Given** a signed-in architect opens the diagram-type selector, **When** they view the five available types, **Then** the one type matching their role's mapping is visually distinguished (e.g., a "Recommended" label or badge) from the other four.
2. **Given** the recommended type is visually marked, **When** the user selects one of the other four (non-recommended) types, **Then** the selection succeeds exactly as it would for the recommended type — no type is disabled, hidden, or harder to reach.

---

### Edge Cases

- What happens when the signed-in user's role cannot be determined (e.g., `useAuth()` returns an unrecognized or missing role string)? → Falls back to today's pre-feature behavior (the existing hardcoded default, `flowchart` — see `DiagramEditorPage.tsx`), with no "Recommended" badge shown on any type. Never blocks diagram creation.
- What happens for a Reviewer, who has no `WRITE_DIAGRAM` permission? → Not applicable — Reviewers cannot reach "+ New Diagram" at all today (ADP-SPEC-046, unchanged by this feature), so there is no persona-default behavior to define for that role.
- What happens if a user's role changes mid-session (e.g., a Keycloak group change takes effect on next token refresh)? → The default/recommendation is computed fresh each time the "+ New Diagram" flow is entered (not cached), so it reflects the current session's role at that moment — no explicit handling of a mid-edit role change is needed since role doesn't affect an already-open editor, only the initial default.
- What happens when reopening an *existing* diagram (not creating a new one)? → No change — an existing diagram's `diagram_type` is immutable (ADP-SPEC-046, `DiagramUpdate` has no `diagram_type` field) and its type selector is already hidden when editing (per `DiagramEditorPage.tsx`'s `!diagramId` condition); persona defaults only ever apply to the "new diagram" creation path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST determine the signed-in user's persona from the existing role information already available client-side (no new backend call or field).
- **FR-002**: The system MUST map each of the three architect roles to exactly one of the five existing diagram types as that role's default/recommended type:
  - Enterprise Architect → `architecture` (cloud/system-landscape diagrams — the type closest to an enterprise-wide, cross-system view)
  - Solution Architect → `flowchart` (process/decision-flow diagrams — the type closest to solution- and process-level design work)
  - Technical Architect → `sequence` (system-to-system interaction diagrams — the type closest to technical integration detail)
  - This mapping is a fixed, documented convention for v1, not user-configurable (see Assumptions).
- **FR-003**: When a user with a recognized role starts a brand-new diagram, the system MUST pre-select that role's mapped default type in the diagram-type selector.
- **FR-004**: The system MUST allow the user to change the pre-selected type to any of the other four types before the diagram's first save, with identical behavior to today (unchanged from ADP-SPEC-046) — the default MUST NOT restrict which types a role can create.
- **FR-005**: The system MUST visually distinguish the role's mapped type from the other four options wherever the full set of five types is presented for selection (e.g., a "Recommended for your role" indicator), without disabling, hiding, reordering out of reach, or otherwise degrading access to any of the other four.
- **FR-006**: When the user's role cannot be recognized, the system MUST fall back to the existing pre-feature default (`flowchart`) and show no recommendation indicator, rather than failing or blocking diagram creation.
- **FR-007**: The system MUST NOT alter the diagram-type selector's behavior when editing an *existing* diagram (the type is immutable post-creation, per ADP-SPEC-046) — this feature applies only to the new-diagram creation path.

### Key Entities

- No new persisted entities. The persona→default-type mapping is a small, static, in-memory constant on the frontend (analogous to the existing `ROLE_LABELS`/`ROLE_COLORS` constants in `web/src/auth/AuthProvider.tsx`) — not a database table, not part of the `Diagram` model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When starting a new diagram, an architect's role-matched type is already selected without any manual action, for all three architect roles, 100% of the time (deterministic mapping, not a heuristic).
- **SC-002**: A user can always reach and select any of the 5 diagram types regardless of their role — 0% reduction in reachable options compared to today.
- **SC-003**: A user unfamiliar with the persona-mapping convention can identify which diagram type is "recommended" for their role at a glance, without consulting documentation (verified by the presence of a visible, unambiguous indicator in the UI, not a numeric target — this is a qualitative usability property).

## Assumptions

- **The epic's original "Business Architect" (BA) wording is stale and does not map to any real ADP role.** `src/adp/authz/roles.py`'s `PersonaRole` enum has only `enterprise_architect`, `solution_architect`, `technical_architect`, `reviewer`, `platform_admin` — no `business_architect`. This spec reuses the three existing architect roles as-is and does not introduce a fourth persona or any `PersonaRole`/`permissions.py` change.
- **Steering, not restriction.** All three architect roles retain identical `WRITE_DIAGRAM`-gated ability to create any of the 5 diagram types; this feature only changes which type is pre-selected and how types are visually labeled, consistent with the recommendation that a further access restriction would be a distinct, not-yet-made governance decision.
- **The persona→default-type mapping (FR-002) is a reasonable v1 default based on each role's typical scope of work in ADP today** (Enterprise Architect: cross-system/enterprise view; Solution Architect: process/solution design; Technical Architect: technical integration detail), not derived from a formal user study. It is expected to be revisited if usage data or user feedback suggests a better fit — changing it is a one-line constant edit, not a structural change.
- **Curated per-persona starter templates (pre-filled DSL content) are explicitly out of scope for this iteration.** The description's option space included "curated per-persona templates" as one possible interpretation of "persona-differentiated"; this spec resolves to default-type-selection + visual recommendation (User Stories 1–2) as the v1 scope, since starter-content design (what a "good" starter flowchart/sequence/etc. looks like per persona) is a materially larger, separate design effort better suited to its own future iteration.
- **No backend change of any kind.** The signed-in user's role is already exposed client-side via the existing `useAuth()` hook (used today for `roleLabel`/`roleColors` display); this feature adds a pure frontend mapping/lookup, with zero new API surface, zero new database schema, and zero change to `WRITE_DIAGRAM`/`permissions.py`.
- **Out of scope** (per the originating request): adding a new `PersonaRole` or any RBAC/`permissions.py` change; AI-assisted diagram generation (tracked separately as ADP-914.8); generating diagrams from ADP's own business-capability/value-stream data (tracked separately as ADP-914.7); any change to the vendored `diagram-core` parsing/rendering library; a persona-scoped *filtered* diagrams list (all diagrams remain visible to all authorized roles, consistent with ADP-SPEC-046's FR that these are standalone, globally-listed artifacts).
