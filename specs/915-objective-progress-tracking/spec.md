# Feature Specification: Objective Progress Tracking, Lifecycle Status & Theme Management

**Feature Branch**: `915-objective-progress-tracking`
**Created**: 2026-08-13
**Status**: Draft
**Input**: User description: "adp-d8u.5" (bead ADP-d8u.5, itself a pointer to `docs/strategy-domain-expansion-specs.md` SPEC-STRAT-01)

## Ground-Truth Correction *(found during specification — not a normal spec section, kept because it changes scope)*

The source bead and doc describe themes as "a free-text tag column with no independent record" that this feature must "promote... to a first-class entity table." **That premise is stale.** A direct read of `src/adp/strategy/models.py`/`router.py` and migration `025_strategic_objectives.py` confirms `strategic_themes` already exists as a real table (`id`, `name` unique, `created_at`) with `strategic_objectives.theme_id` already a proper foreign key — not a tag column — and `POST`/`GET /strategy/themes` already exist. What genuinely does **not** exist yet: theme `description`/`owner`/`priority` fields, `GET /themes/{id}` (single-item read), `PATCH`/`DELETE /themes/{id}`, any objective progress history, and any objective status concept at all (confirmed: no `status` column on `strategic_objectives`, no progress table). This specification is written against that corrected, verified starting point — it extends the existing theme entity rather than creating one, and adds progress/status as genuinely new capability.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: objective status becomes a *derived* read, computed from the progress history already in the model — never a value a human sets directly for its three non-terminal states. The heat map and any future rollup (a sibling, later feature) read this status rather than re-deriving it themselves.
- **ART-IX** — Provenance and Auditability: every progress entry records who recorded it and when; abandoning an objective requires a stated reason, itself an audit-relevant fact.
- **ART-XIII** — Typed Contracts Everywhere: all new request/response payloads are strictly typed Pydantic models (`extra="forbid"`), matching the existing `adp.strategy` convention.

## Threat Model *(mandatory — ART-V)*

Low-risk, internal-only feature — no new trust boundary, no AI involvement.

**Assets at risk**: Strategic progress data and theme metadata are internal planning records (not customer data, not credentials); the main risk is an unauthorized user recording false progress to misrepresent an objective's health, or deleting a theme other objectives still depend on.

**Trust boundaries crossed**: Browser → API only (same boundary every existing `adp.strategy` write already crosses). No new external integration, no LLM call — this feature is explicitly out of scope for **ART-VII (Grounded AI Only)**; progress entries are human-entered only in this version, and any future AI-assisted ingestion must go through the standard AI-proposes/human-confirms gate as its own, later feature.

**Abuse cases**:
- An unauthenticated or under-permissioned actor records fabricated progress to make an objective appear on-track → mitigated by reusing the existing `strategy:write` permission gate already enforced on every other `adp.strategy` mutation.
- A user deletes a theme that objectives still reference, silently orphaning them → mitigated by blocking the delete (409) while any objective references the theme, matching the existing platform-wide "referenced entities are protected, never silently cascaded away" pattern.

**Residual risk**: A permitted user can record a value that doesn't match reality (e.g., typo, optimistic rounding) — accepted, since this is a human-attested planning record, not a system-of-record financial or safety value; the `recorded_by` + timestamp on every entry gives full accountability after the fact.

## Clarifications

### Session 2026-08-13

- Q: The source doc left open how a same-day progress-entry correction should work (today's stated default is reject-only, with no edit path). → A: Add the ability to edit an already-recorded entry for a given date, correcting the value/note in place — keeps the one-entry-per-day rule while giving a real fix path, matching how objectives themselves are already editable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record progress and see an objective's status update automatically (Priority: P1)

An objective owner periodically records the actual measured value against their objective's target. Every time they do, the objective's status (on track / at risk / achieved) updates itself — nobody has to look at a target and a number side by side and judge it themselves, and nobody has to remember to update a separate "status" field by hand.

**Why this priority**: This is the feature's whole reason for existing — today nobody can answer "is this objective on track?" without leaving the system and doing the comparison themselves. Without this story, the feature delivers nothing.

**Independent Test**: Create an objective with a numeric target, record a sequence of actual values over several dates, and confirm the displayed status changes appropriately as the values move toward, away from, or past the target — fully verifiable without any of the other stories existing.

**Acceptance Scenarios**:

1. **Given** an objective with a target and no recorded progress yet, **When** an owner views the objective, **Then** its status reads as newly proposed / not yet started (no progress recorded is not the same as "at risk" — there's nothing to be at risk of yet).
2. **Given** an objective with a target, **When** an owner records an actual value that has reached or passed the target (respecting the objective's stated direction — increase, decrease, or reach a value), **Then** the objective's status reads as achieved.
3. **Given** an objective with several recorded values trending steadily away from its target over its most recent entries, **When** an owner views the objective, **Then** its status reads as at risk.
4. **Given** an objective with recorded values trending toward its target but not yet there, **When** an owner views the objective, **Then** its status reads as active/on track.
5. **Given** an owner has already recorded a value for a specific date, **When** they attempt to record a brand-new entry for that same date, **Then** the system rejects the duplicate — but offers editing the existing entry as the way to correct it, rather than leaving them stuck.
6. **Given** a recorded progress history, **When** an owner (or anyone with read access) views the objective, **Then** they can see the full history of recorded values over time, not just the latest one.
7. **Given** a progress entry recorded earlier, **When** an owner edits its value or note to correct a mistake, **Then** the correction is saved in place (the date stays the same, one entry per date is preserved) and the objective's status recomputes from the corrected value.

---

### User Story 2 - Mark an objective as abandoned (Priority: P2)

Sometimes an objective is no longer being pursued — priorities shifted, it became obsolete, or leadership cancelled it. An owner needs to mark it as abandoned, with a stated reason, so it stops appearing as "on track" or "at risk" and instead honestly reflects that work on it has stopped.

**Why this priority**: Real but less frequent than routine progress recording (Story 1) — most objectives are actively tracked far more often than they're abandoned — and it doesn't block Story 1 from delivering value on its own.

**Independent Test**: Take any existing objective, mark it abandoned with a reason, and confirm its status now reads as abandoned and that the reason is visible — independently verifiable without any progress-recording history existing on that objective at all.

**Acceptance Scenarios**:

1. **Given** an active objective, **When** an owner marks it abandoned and provides a reason, **Then** its status becomes abandoned and the reason is visible wherever the objective's status is shown.
2. **Given** an owner attempts to mark an objective abandoned, **When** they don't provide a reason, **Then** the system rejects the request and explains a reason is required.
3. **Given** an objective already marked abandoned, **When** anyone attempts to set its status directly to on-track, at-risk, or achieved, **Then** the system rejects it — those three states are always computed from progress, never set by hand.

---

### User Story 3 - Manage richer theme information (Priority: P3)

A strategy lead organizing objectives by theme wants each theme to carry more than just a name — a short description of what it covers, who owns it, and a rough priority ranking — and wants to be able to edit or retire a theme, not just create new ones.

**Why this priority**: Valuable to a different persona (a portfolio/strategy lead curating taxonomy) than Stories 1–2 (an objective owner tracking their own objective), and existing themes already work fine as bare name-only labels today — this enriches them but blocks nothing else.

**Independent Test**: Create a theme with a description, owner, and priority; edit each of those fields; attempt to delete a theme that has objectives assigned to it (must be blocked) and one that doesn't (must succeed) — fully testable independent of any progress or status work.

**Acceptance Scenarios**:

1. **Given** the theme list, **When** a strategy lead creates a new theme, **Then** they can optionally provide a description, an owner, and a priority ranking alongside the name that's already required today.
2. **Given** an existing theme, **When** a strategy lead edits its description, owner, or priority, **Then** the change is saved and visible the next time the theme is viewed.
3. **Given** a theme with one or more objectives currently assigned to it, **When** someone attempts to delete it, **Then** the system blocks the deletion and explains why, rather than silently orphaning those objectives.
4. **Given** a theme with no objectives assigned to it, **When** someone deletes it, **Then** it's removed and no longer appears in the theme list.

### Edge Cases

- What happens when an objective has no numeric target at all (target fields are optional today)? Status computation has nothing to compare against — the system must not error, and must show a status that honestly reflects "not measurable" rather than guessing.
- What happens when an owner needs to correct a mistaken entry for a date that already has one? Resolved via Clarifications: they edit the existing entry in place rather than submitting a new one.
- What happens to an objective's progress history and status if the objective itself is deleted? Progress entries are objective-scoped detail — they're removed along with the objective, the same way its capability/value-stream links already are.
- What happens when a theme delete is attempted on a theme with zero objectives but objectives existed and were later reassigned away — is that theme now safely deletable? Yes — the block is purely "does anything currently reference it," not historical.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Owners MUST be able to record a dated, numeric progress entry (an "actual value") against any objective they can already edit.
- **FR-002**: The system MUST reject a *new* progress entry for a date that already has one for the same objective, and MUST tell the user an entry for that date already exists.
- **FR-002a**: Owners MUST be able to edit an existing progress entry's value and note (the date is fixed once recorded) — this is the correction path for FR-002's rejected duplicates.
- **FR-003**: Anyone able to view an objective MUST be able to see its full recorded progress history, ordered by date, not just the most recent value.
- **FR-004**: The system MUST compute and display an objective's status automatically from its progress history and target — owners MUST NOT be able to set on-track, at-risk, or achieved directly.
- **FR-005**: An objective with no recorded progress yet MUST show a distinct "not yet started" status, never conflated with "at risk."
- **FR-006**: An objective whose latest recorded value has reached or passed its target (honoring the objective's stated direction) MUST show as achieved.
- **FR-007**: An objective whose recent recorded values are trending away from its target MUST show as at risk; one trending toward but not yet at its target MUST show as on track/active.
- **FR-008**: An objective with no numeric target at all MUST show a status that honestly reflects it isn't measurable, rather than an error or a misleading on-track/at-risk guess.
- **FR-009**: Owners MUST be able to mark an objective abandoned, and MUST provide a reason when doing so; the system MUST reject an abandon request with no reason.
- **FR-010**: An abandoned objective's status and reason MUST be visible wherever its status is otherwise shown.
- **FR-011**: The system MUST reject any attempt to set an objective's status directly to a value other than "abandoned" (the three other states stay derived-only, per FR-004).
- **FR-012**: Users MUST be able to create a theme with an optional description, owner, and priority ranking, in addition to the name already required today.
- **FR-013**: Users MUST be able to edit an existing theme's description, owner, and priority.
- **FR-014**: The system MUST block deleting a theme that any objective currently references, and MUST explain why, rather than orphaning those objectives.
- **FR-015**: The system MUST allow deleting a theme that no objective currently references.
- **FR-016**: Deleting an objective MUST also remove its recorded progress history (no orphaned progress entries left behind).

### Key Entities

- **Objective Progress Entry**: A single dated, human-recorded actual value against one objective's target — who recorded it, when, an optional note, and the value itself. One entry per objective per date; the value and note can be corrected in place after the fact, but the date is fixed once recorded. Together, an objective's entries form its progress history.
- **Objective Status**: Not a stored fact for three of its four possible values — a computed read reflecting where an objective stands (not yet started / on track / at risk / achieved), derived from its progress history and target. The fourth value, abandoned, is the one a human sets directly, always with a stated reason.
- **Theme** *(existing entity, extended)*: Already exists today as a named grouping for objectives. This feature adds an optional description, an owner, and a priority ranking, and completes its lifecycle (today only creating and listing themes is possible; editing and deleting are new).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An objective owner can determine whether any given objective is on track without doing any manual comparison themselves — the answer is visible at a glance wherever the objective appears.
- **SC-002**: Recording a new progress entry takes an owner under 30 seconds from deciding to record it to seeing it reflected in the objective's status.
- **SC-003**: Zero duplicate or silently-overwritten progress entries occur for the same objective and date — every attempt either succeeds as a new entry or is clearly rejected.
- **SC-004**: 100% of abandoned objectives carry a human-readable reason, visible without extra navigation, wherever their status is shown.
- **SC-005**: A strategy lead can fully organize themes (create, describe, assign an owner, prioritize, retire) without needing any workaround (e.g., encoding priority into the theme name).

## Assumptions

- The at-risk trend window (how many recent entries count as "recent" for judging trend direction) defaults to the last 3 recorded entries; this default is not user-configurable in this version.
- Abandoned is a genuinely terminal state in this version — there is no "un-abandon" action; reviving an objective's tracking means creating a new one. This matches how the source specification frames the state ("the one manually-set terminal value").
- Progress entries are human-entered only in this version; no automatic ingestion from any external KPI source is in scope (a future feature, if pursued, would need its own AI-proposes/human-confirms gate per ART-VII).
- Theme priority is a coarse ranking (a small ordered scale), not a precise numeric score — consistent with how similar ranking fields already work elsewhere in the platform (e.g., maturity/strategic-relevance scoring).
- No new user-facing permission is introduced — recording progress, setting abandoned status, and managing themes all reuse the same write permission objectives and themes already require today.
- Cross-objective rollups (e.g., "how many objectives are at risk portfolio-wide," a heat map, an Overview dashboard tile breakdown by status) are explicitly out of scope here — a separate, later feature (already tracked) builds on this one's status field to deliver those views.
