# Feature Specification: Admin UI for Editing Scoring Rubric Weights

**Feature Branch**: `931-admin-ui-editing`
**Created**: 2026-08-26
**Status**: Draft
**Input**: Bead ADP-68z — "UI for editing scoring rubric weights (business value, and future
similar composite scores)." Deferred from the Application Business Value assessment build
(`docs/application-business-value-assessment-spec.md`), 2026-08-15: the six weighted-average
weights (`BUSINESS_VALUE_WEIGHTS`, `adp.application.models`) are hardcoded constants, approved
as-is for the initial build but flagged as "the first of a class of tunable scoring-rubric
parameters ADP will accumulate" — a UI to view/edit them without a code deploy, explicitly
mirroring the existing Agent Prompt Management admin surface (ADP-SPEC-042).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this bead was not yet spec'd.
- **ART-IV** — Test-Driven Development: always applies.
- **ART-VIII** — Human-in-the-Loop for Consequence: changing a live scoring rubric's weights
  changes every future business-value assessment computed platform-wide — the same class of
  consequential, attributable action ADP-SPEC-042 already established for agent prompts. This
  feature reuses that exact confirmation-gate mechanism (`REQUIRES_CONFIRMATION`,
  `confirmation_id`), not a new one.
- **ART-IX** — Provenance/Auditability: every weight change is recorded in an append-only history
  table, mirroring `agent_prompt_history`'s own ART-IX treatment exactly.
- **ART-V** — in scope: a new admin-only permission surface (see Threat Model).

## Ground-Truth Note

Unlike several beads worked earlier this session, this one is **not** partially pre-built — a
direct grep confirms zero existing `rubric`/`RUBRIC` code anywhere in `src/adp/admin/` or
`src/adp/authz/`, and `BUSINESS_VALUE_WEIGHTS`/`BUSINESS_VALUE_EVIDENCE_CAP`
(`adp.application.models`) remain exactly the hardcoded constants the bead describes, consumed by
`compute_business_value_score()` — a deliberately pure, no-I/O function (its own docstring:
"mirrors `adp.strategy.store.compute_status()`'s own precedent for derived-value functions"). This
spec is a genuinely new build, structured as closely as possible to ADP-SPEC-042's own
already-shipped architecture per the bead's explicit instruction, adapted only where the underlying
data shape differs (a dict of named float weights, not free-text).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: the correctness of every future business-value score computed platform-wide —
a bad weight set (e.g. not summing to 1.0, or a missing dimension) would silently skew every
application's business-value assessment, a decision-support number other features (portfolio
rationalization, TIME grouping) already surface to architects.

**Trust boundaries crossed**: none new beyond ADP-SPEC-042's own precedent — this is another
admin-only write surface behind the same `PersonaRole.PLATFORM_ADMIN` role and the same
confirmation-gate mechanism.

**Abuse cases**:
- A non-admin attempting to change scoring weights → blocked by the same route-prefix
  `ActionType`-gate mechanism `MANAGE_AGENT_PROMPTS` already uses (a new
  `ActionType.MANAGE_SCORING_RUBRICS`, granted only to `PLATFORM_ADMIN`).
- An admin submitting an invalid weight set (doesn't sum to 1.0, missing/extra dimension, a
  negative weight) → rejected before it can ever reach `compute_business_value_score()`, both
  client-side (UI blocks Save) and server-side (the API independently validates — never trust the
  client alone).
- Two admins editing the same rubric concurrently → the identical optimistic-concurrency
  (`expected_version`/409) mechanism ADP-SPEC-042 already uses, unchanged in shape.

**Residual risk**: none beyond ADP-SPEC-042's own accepted residual risk for the identical
mechanism.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A platform admin views and edits the Business Value rubric's weights (Priority: P1)

A Platform Admin opens a new "Scoring Rubrics" admin screen (sibling to the existing "Agent
Prompts" one), sees the Business Value rubric's six dimensions and their current weights (whether
the hardcoded default or a previously saved override), edits one or more, and confirms the change —
which becomes effective for every business-value assessment computed from that point on, with zero
code deploy.

**Why this priority**: This is the bead's entire stated deliverable.

**Independent Test**: Change a weight, confirm, then submit a Business Value assessment via the
existing `PUT /api/v1/applications/{id}/business-value-assessment` endpoint and confirm the
computed `weighted_average` reflects the new weights, not the original hardcoded ones.

**Acceptance Scenarios**:

1. **Given** no override has ever been saved, **When** a Platform Admin opens the screen, **Then**
   it shows the Business Value rubric with the six hardcoded default weights (Strategic Alignment
   25%, Revenue/Cost Impact 25%, Customer Impact 15%, Risk/Compliance 15%, Differentiation 10%,
   Evidence & Measurability 10%), labeled as the built-in default (mirroring `AgentPromptView`'s own
   `is_override` badge).
2. **Given** an edited weight set that sums to 100%, **When** the admin confirms the change (with a
   confirmation dialog explaining the platform-wide, immediate effect, mirroring
   `PromptEditor.tsx`'s own confirm-dialog copy), **Then** the new weights become the active set and
   the next business-value computation anywhere in the platform uses them.
3. **Given** an edited weight set that does NOT sum to 100% (e.g. off by even 1%), **When** the
   admin attempts to save, **Then** the UI blocks the save with a clear message before any network
   call, and the API independently rejects it too if somehow reached (422).
4. **Given** a currently-active override, **When** a second Platform Admin has the screen open with
   a stale version and attempts to save, **Then** the save is rejected with a 409 conflict
   (identical `expected_version` mechanism to ADP-SPEC-042), never silently overwritten.

---

### User Story 2 - A platform admin reviews the rubric's change history (Priority: P2)

The admin views every prior confirmed weight change for a rubric — who changed it, when, the full
before/after weight sets — and can restore an earlier version.

**Why this priority**: Direct mirror of ADP-SPEC-042's own User Story 3; same value proposition
(accountability, easy rollback of a bad change) applied to a different kind of admin-tunable data.

**Independent Test**: Make two edits, view history, confirm both appear newest-first with correct
before/after weight sets; restore the first, confirm it becomes active again.

**Acceptance Scenarios**:

1. **Given** two confirmed edits to the same rubric, **When** the admin views its history, **Then**
   both appear in reverse-chronological order with actor, timestamp, and full before/after weight
   sets.
2. **Given** a history entry, **When** the admin restores it, **Then** the SAME confirmation gate as
   a manual edit applies (Clarification, mirroring ADP-SPEC-042's own 2026-07-24 decision: restore
   is not a lower-friction path), and the restored weights become active, recorded as a new
   `change_type="restore"` history row.

### Edge Cases

- A weight set summing to 99.999...% or 100.0001% due to floating-point representation must not be
  spuriously rejected — validation uses a small epsilon tolerance (e.g. weights sum to
  `1.0 ± 1e-6`), not exact float equality.
- The evidence-measurability cap table (`BUSINESS_VALUE_EVIDENCE_CAP`) is a different kind of
  tunable (a score→cap lookup, not a weight distribution) and is explicitly OUT of scope for this
  pass — see Assumptions.
- Only one rubric (`business_value`) is registered today; the screen and its underlying mechanism
  must not hardcode "exactly one rubric exists" anywhere a second registration would later break —
  mirrors `AGENT_REGISTRATIONS`' own generality (six agents today, extensible without a schema
  change).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a registry of "scoring rubrics" (mirroring
  `prompt_registry.AGENT_REGISTRATIONS`), each with a stable `rubric_id`, a display name, its
  dimensions (stable keys + human-readable labels), a fallback provider returning its hardcoded
  default weights, and a validator confirming a proposed weight set is well-formed for that rubric
  specifically (exactly the right dimension keys, each weight in `[0, 1]`, summing to `1.0` within
  a small tolerance).
- **FR-002**: The Business Value rubric (`business_value`) MUST be registered, wrapping the
  existing `BUSINESS_VALUE_WEIGHTS` constant as its fallback and its six
  `BusinessValueDimension` keys as its dimension set.
- **FR-003**: System MUST persist a per-rubric override (absence of a row means "using the
  hardcoded fallback," mirroring `agent_prompt_overrides`' own semantics exactly) and an
  append-only history of every confirmed edit/restore, in the same single-transaction
  (override-write + history-insert) pattern ADP-SPEC-042 already established.
- **FR-004**: `GET .../scoring-rubrics` MUST list every registered rubric's current effective
  weights, whether overridden or default, plus enough metadata (dimension labels) for the UI to
  render an editable form without a second round-trip.
- **FR-005**: `POST .../scoring-rubrics/{rubric_id}/confirm` MUST require a non-empty
  `confirmation_id` (ART-VIII) and an `expected_version` (optimistic concurrency, FR- mirrors
  ADP-SPEC-042's own FR-012), and MUST reject (422) a weight set failing the rubric's own validator
  before writing anything.
- **FR-006**: `GET .../scoring-rubrics/{rubric_id}/history` and
  `POST .../scoring-rubrics/{rubric_id}/restore/{history_id}` MUST mirror ADP-SPEC-042's own
  history/restore endpoints exactly, including the identical confirmation gate on restore.
- **FR-007**: A new `ActionType.MANAGE_SCORING_RUBRICS` MUST gate every route under this new
  prefix (reads included, mirroring `MANAGE_AGENT_PROMPTS`'s own FR-009 "the whole admin surface,
  not just writes" precedent), granted only to `PersonaRole.PLATFORM_ADMIN` — no architect role,
  including Enterprise Architect, gains it via a wildcard grant (identical precedent to
  `MANAGE_AGENT_PROMPTS`'s own Clarification Session 2026-07-24 Q1 decision).
- **FR-008**: `compute_business_value_score()` MUST remain a pure, no-I/O function — it MUST accept
  an optional `weights` parameter (defaulting to the hardcoded `BUSINESS_VALUE_WEIGHTS` constant
  when omitted), so its two existing callers (both already holding a DB session) become
  responsible for resolving the *effective* weights (override, if any, else the fallback) before
  calling it — mirroring exactly how `get_effective_prompt()` is the one I/O-touching layer while
  every AI call site just passes in an already-resolved string.
- **FR-009**: A new "Scoring Rubrics" nav entry MUST appear under the existing "Administration"
  nav section (sibling to "Agent Prompts"), gated on the identical `platform_admin` role check.

### Key Entities

- **Rubric Registration** (code, not persisted — mirrors Agent Prompt Registration): a rubric's
  stable identity, dimension set, default weights, and validator.
- **Rubric Weight Override** (new table, `rubric_weight_overrides`): one row per rubric currently
  running a saved override.
- **Rubric Weight Change Record** (new table, `rubric_weight_history`): one append-only row per
  confirmed edit or restore.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A Platform Admin can change the Business Value rubric's weights and see the effect
  on a real assessment's computed score with zero code deploy or restart.
- **SC-002**: An invalid weight set (wrong dimension count, doesn't sum to 100%) is rejected before
  ever reaching `compute_business_value_score()`, both client- and server-side.
- **SC-003**: Every weight change is attributable (actor, timestamp) and reversible (restore),
  identical to the existing Agent Prompt Management guarantee.
- **SC-004**: Adding a second rubric in the future requires zero schema change — only a new
  `RubricRegistration` entry, mirroring `AGENT_REGISTRATIONS`' own proven extensibility.

## Assumptions

- `BUSINESS_VALUE_EVIDENCE_CAP` (the evidence-measurability score→cap lookup table) is explicitly
  OUT of scope for this pass — the bead's own description names only "weights," and a cap table is
  a structurally different kind of tunable (an integer→integer|null lookup, not a normalized weight
  distribution) that would need its own validator shape; a natural follow-on, not assumed here.
- The UI presents weights as whole-number percentages (25, 25, 15, 15, 10, 10) summing to 100 for
  human legibility, translated to/from the underlying `0.0–1.0` float fractions
  `compute_business_value_score()` and the stored override actually use — no functional difference,
  a presentation choice only.
- No new user-facing screen beyond the admin surface itself — the Application registry's own
  Business Value assessment UI (`BusinessValueAssessmentModal.tsx`) is unchanged; it already shows
  the *computed result*, not the weights themselves, and continues to do so.
