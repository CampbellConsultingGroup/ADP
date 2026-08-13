# Feature Specification: Strategy Execution Layer — Initiatives & Objective Dependencies

**Feature Branch**: `916-strategy-initiatives-dependencies`
**Created**: 2026-08-13
**Status**: Draft
**Input**: User description: "ADP-d8u.6" (bead ADP-d8u.6, itself a pointer to `docs/strategy-domain-expansion-specs.md` SPEC-STRAT-03)

## Ground-Truth Corrections *(found during specification — not a normal spec section, kept because they change scope)*

1. **Package placement is resolved, not open.** The bead flagged an unresolved SDD decision (source doc §3.2): should the new initiative concept live as a submodule inside `adp.strategy`, or a new sibling package, decided by measuring `adp.strategy`'s actual line count against the ~2,847-line threshold that triggered the `adp.business` → `adp.strategy` split. Measured directly: `src/adp/strategy/{models,store,router}.py` total **1,434 lines** — well under that threshold. This settles it: a submodule inside the existing package, not a new sibling package.
2. **No `users` table exists anywhere in this codebase** (the same fact already established while building the sibling `915-objective-progress-tracking` feature). The bead's proposed `owner_id FK → users` column doesn't match reality — initiative ownership follows the same plain-`TEXT` convention already used by `strategic_objectives.owner` and `strategic_themes.owner`.
3. **The existing `adp.application` transformation-initiative concept is real and confirmed distinct** (`src/adp/application/{models,store,router}.py` all define `TransformationInitiative`) — this feature's own initiative concept is a separate, strategy-level program-of-work record, not a migration or extension of that one, exactly as the bead states.

## Clarifications

### Session 2026-08-13

- Q: Should a strategy initiative's status (planned/in_progress/blocked/complete/cancelled) follow an enforced transition sequence, mirroring how a Design's lifecycle status already constrains valid transitions elsewhere in this platform — or stay a free-form value settable from any other at any time? → A: Free enum, no enforced sequence. Initiatives are framed as "the newest, thinnest layer" with no other system behavior riding on a particular transition path, unlike Design lifecycle (where transitions auto-set dates and carry retirement implications).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: an objective dependency cycle is rejected at write time by an application-layer check (not a DB constraint — cycles aren't expressible as a single-table CHECK), so the stored graph is always acyclic; nothing downstream needs to re-validate it.
- **ART-IX** — Provenance and Auditability: initiative creation/status changes and dependency link changes follow the same structured-logging convention `915-objective-progress-tracking` established for this domain (no `design_id` exists here for a real `AuditEntry` row — see that feature's own Ground-Truth Correction on this point).
- **ART-XIII** — Typed Contracts Everywhere: all new request/response payloads are strictly typed Pydantic models (`extra="forbid"`), matching the existing `adp.strategy` convention.

## Threat Model *(mandatory — ART-V)*

Low-risk, internal-only feature — no new trust boundary, no AI involvement, no sensitive data.

**Assets at risk**: Strategy initiative records and objective-dependency graphs are internal planning data (not customer data, not credentials, not financial records).

**Trust boundaries crossed**: Browser → API only, the same boundary every existing `adp.strategy` write already crosses. No new external integration.

**Abuse cases**:
- An unauthorized user creates or modifies initiatives, or rewires the objective-dependency graph, to misrepresent delivery status → mitigated by reusing the existing write-permission gate every other `adp.strategy` mutation already requires.
- A malformed or malicious dependency request creates a cycle (A depends on B depends on A) that would make "what's blocking this objective" queries loop forever → mitigated by rejecting any link that would introduce a cycle before it's written, including the degenerate case of an objective depending on itself.

**Residual risk**: None beyond what every other `adp.strategy` write already accepts (a permitted user can record inaccurate initiative status — a human-attested planning label, not a system-of-record value).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Track the program of work delivering an objective (Priority: P1)

A strategy lead creates initiatives — the actual programs of work underway — and links each one to the objective or objectives it serves, so anyone looking at an objective can see what's actually being done to deliver it, not just the target it's aiming for.

**Why this priority**: This is the feature's primary problem statement — today an objective links straight to capabilities and value streams with no representation of the delivery work itself. Without this story, the feature delivers nothing.

**Independent Test**: Create an initiative, link it to one or more objectives, view it from both directions (the initiative shows which objectives it serves; each linked objective shows which initiatives are delivering it), then unlink and delete — fully testable without any dependency-graph work existing.

**Acceptance Scenarios**:

1. **Given** no initiatives exist yet, **When** a strategy lead creates one with a name, description, owner, and status, **Then** it appears in the initiative list with those details.
2. **Given** an existing initiative and an existing objective, **When** the lead links them, **Then** the initiative shows that objective among the ones it serves, and the objective shows that initiative among the ones delivering it.
3. **Given** an initiative already linked to an objective, **When** the lead links a second objective to the same initiative, **Then** both links coexist — one initiative can serve multiple objectives.
4. **Given** an initiative, **When** the lead updates its status (e.g. from planned to in progress), **Then** the new status is saved and requires no other field to change alongside it.
5. **Given** a linked initiative, **When** the lead unlinks it from an objective, **Then** that specific link is removed without affecting the initiative's other links or the objective itself.
6. **Given** an initiative with no links at all, **When** the lead deletes it, **Then** it's removed entirely.

---

### User Story 2 - Express and see what one objective depends on or blocks (Priority: P2)

A strategy lead records that one objective can't move forward until another one does — a real-world sequencing constraint — and anyone viewing either objective can see both directions of that relationship: what it's waiting on, and what's waiting on it.

**Why this priority**: A real, distinct capability from Story 1 (sequencing between objectives, not program-of-work tracking) — valuable on its own, and doesn't block Story 1 from delivering value independently.

**Independent Test**: Create two objectives, record that one depends on the other, view the dependency from both objectives (one shows "depends on", the other shows "blocks"), attempt to create a cycle and confirm it's rejected, then remove the dependency — fully testable independent of any initiative work.

**Acceptance Scenarios**:

1. **Given** two existing objectives, **When** a lead records that one depends on the other, **Then** the dependent objective's view shows what it depends on, and the other objective's view shows what it blocks.
2. **Given** objective A depends on objective B, **When** a lead attempts to also record that B depends on A, **Then** the system rejects it — that would be a two-step cycle.
3. **Given** a chain where A depends on B and B depends on C, **When** a lead attempts to record that C depends on A, **Then** the system rejects it — that would close a longer cycle.
4. **Given** any objective, **When** a lead attempts to record that it depends on itself, **Then** the system rejects it.
5. **Given** an existing dependency between two objectives, **When** a lead removes it, **Then** neither objective shows the relationship anymore, and the objectives themselves are unaffected.

### Edge Cases

- What happens to an initiative's objective links, or an objective's dependency links, when one of the linked objectives is deleted? The links involving the deleted objective are removed along with it — no dangling references, consistent with how objective progress history already cascades on objective deletion.
- What happens when an initiative is deleted while still linked to one or more objectives? Deletion is unconditional here (unlike a theme, an initiative isn't a shared taxonomy value another record points to by identity — it's more like a tag on the objectives it serves) — deleting it removes its links along with it, without requiring the links to be removed first.
- What happens if a cycle-creating request is attempted through a longer chain (more than 3 objectives)? Rejected the same way as a direct 2-cycle — the check considers the whole reachable chain, not just the immediate pair.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to create a strategy initiative with a name (required), and optionally a description, owner, and status.
- **FR-002**: Users MUST be able to view, edit, and delete an existing initiative.
- **FR-003**: An initiative's status MUST accept any of a fixed set of values (planned, in progress, blocked, complete, cancelled) and MUST NOT be constrained to a required sequence — any value is settable from any other at any time (per Clarifications).
- **FR-004**: Users MUST be able to link an initiative to one or more objectives, and unlink any specific link without affecting the initiative's other links.
- **FR-005**: Viewing an initiative MUST show every objective it's linked to; viewing an objective MUST show every initiative linked to it.
- **FR-006**: Users MUST be able to record that one objective depends on another.
- **FR-007**: The system MUST reject a dependency that would create a cycle — directly (A depends on B, B depends on A), through a longer chain, or degenerately (an objective depending on itself) — and MUST explain why.
- **FR-008**: Viewing an objective MUST show both directions of its dependency relationships: what it depends on, and what depends on it (what it blocks).
- **FR-009**: Users MUST be able to remove a recorded dependency between two objectives.
- **FR-010**: Deleting an objective MUST also remove any initiative-objective links and any dependency links involving it (no dangling references left behind).
- **FR-011**: Deleting an initiative MUST remove its objective links along with it; deleting an initiative MUST NOT be blocked by the existence of those links.

### Key Entities

- **Strategy Initiative**: A named program of work delivering one or more strategic objectives — distinct from the existing, unrelated application-level transformation-initiative concept elsewhere in the platform. Carries a name, an optional description, an optional owner, and a status (a plain tracking label, not derived from anything and not sequence-constrained). Can serve more than one objective at once.
- **Objective Dependency**: A directional relationship between two strategic objectives — one depends on the other. The platform never allows these relationships to form a cycle, including a one-step self-dependency.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Anyone viewing a strategic objective can see, without leaving the page, what program(s) of work are actually delivering it.
- **SC-002**: Anyone viewing a strategic objective can see, without leaving the page, both what it's waiting on and what's waiting on it.
- **SC-003**: Zero dependency cycles ever exist in the recorded data — every attempt to create one is rejected with a clear explanation, verified across direct, chained, and self-referential cases.
- **SC-004**: Deleting an objective or an initiative never leaves an orphaned link behind for a user to stumble on later.

## Assumptions

- Initiative status is a free-form label in this version (per Clarifications) — no configurable or enforced transition rules, unlike the platform's Design lifecycle precedent.
- No new user-facing permission is introduced — creating/editing initiatives and recording/removing dependencies reuse the same write permission every other `adp.strategy` mutation already requires.
- Linking an initiative to an objective, or one objective depending on another, has no prerequisite on the objectives involved (e.g. no requirement that a linked objective already have a target, or not already be abandoned) — an independent, unconstrained link is intentional, matching how objective↔capability and objective↔value-stream links already work with no such prerequisite.
- Cross-objective rollups that would surface this data at a portfolio level (e.g. "which objectives have unresolved dependencies") are out of scope here — a separate, later feature already tracked for that purpose.
- Merging or migrating the existing, unrelated `adp.application` transformation-initiative concept into this one is explicitly out of scope — the two remain distinct records for distinct layers.
