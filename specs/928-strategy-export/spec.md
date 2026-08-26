
# Feature Specification: Continuous Strategy Domain Export to Versioned Files

**Feature Branch**: `928-strategy-export`
**Created**: 2026-08-26
**Status**: Draft
**Input**: User description: "ADP-81p.3 — Continuous export of the Strategy domain (themes, objectives with their metric fields/status/progress history, strategy execution — initiatives and objective dependencies — plus the traceability join tables spanning capabilities/value-streams/designs/applications/controls/frameworks) from Postgres to versioned, git-tracked JSON files, extending the ADP-SPEC-044/045 continuous-export pattern to a third domain"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: Postgres remains authoritative; exported files are a generated, read-only *projection*, identical in spirit to ADP-SPEC-044/045.
- **ART-III** — Everything is Machine-Readable: closes the same gap ADP-SPEC-044/045 closed for their domains, now for Strategy — themes, objectives, progress history, initiatives, and every cross-domain traceability link currently live only in Postgres rows.
- **ART-V** — Security by Design: unlike ADP-SPEC-045's domain, Strategy has no sensitive-category read gating today (confirmed directly against `src/adp/authz/permissions.py` — no `READ_STRATEGY_*`/`READ_OBJECTIVE_*` action exists), so this feature follows ADP-SPEC-044's simpler precedent: export everything, no redaction decision to make.
- **ART-VI** — Observability is Not Optional: same staleness/failure-must-be-observable requirement as ADP-SPEC-044/045.
- **ART-IX** — Provenance and Auditability: this feature exports already-committed data; it introduces no new consequential mutation of its own.

ART-VIII (Human-in-the-Loop for Consequence) does not require a new confirmation gate — this feature only creates a derived, read-only file projection of already-committed data. ART-VII (Grounded AI Only) does not apply — no AI-generated content is involved.

## Clarifications

### Session 2026-08-26

- Q: `StrategicObjective.status` is never a stored column — the platform's own `compute_status()` (ADP-d8u.5) always derives it at read time from progress history plus target (the underlying `strategic_objectives.status` column only ever holds `NULL` or `'abandoned'`). Should the exported file carry this same computed status, or only the raw stored fields? → **A: The computed status.** Every existing API consumer already sees the derived value (`StrategicObjective.status` in the live read model *is* the computed value); exporting only the raw column would make the file strictly less useful than the platform's own API for the exact same question ("is this objective on track?").
- Q: `capability_design_links`/`value_stream_design_links` (spec 034) link a Business Architecture entity (already exported by ADP-SPEC-044/ADP-81p.1) to a Design. Neither endpoint is Strategy domain data — where should this increment put them, given both prior increments explicitly deferred them? → **A: Extend ADP-SPEC-044's own exported files.** Add a `linked_designs` field to the existing capability/value-stream JSON files, since that is where the other endpoint of each link already lives and is exported; this feature does not introduce a new file location owned by neither domain.
- Q: The three Strategy↔Compliance links (`objective_control_links`, the five `initiative_control_*_mapping` tables, `theme_framework_links`) shipped this session, after this increment was originally scoped. Include them now, or leave them for a later increment? → **A: Include them now** — they are already live, already the same join-table shape as everything else in this increment, and deferring them would just mean revisiting this module again soon for a small addition.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: strategic themes and objectives (including their metric targets and progress history), which strategic work is regulatory-driven or remediation-linked (via the Compliance links), and the cross-domain traceability data connecting objectives to capabilities, value streams, designs, applications, and controls. None of this is classified as sensitive by the platform's own permission model today (confirmed: no `READ_STRATEGY_*` action exists), so this is a lower-stakes threat surface than ADP-SPEC-045's.

**Trust boundaries crossed**: a system-internal boundary (Postgres → filesystem, potentially → git history) — the same shape as ADP-SPEC-044/045, no new browser-facing surface.

**Abuse cases**:
- A theme, objective, or initiative with a maliciously or accidentally crafted name is used to construct a file path → mitigated identically to ADP-SPEC-044/045: file/directory names are derived from existing internal IDs, never from user-supplied free-text.
- The sync mechanism falls silently behind or fails, and an AI tool or human trusts stale exported files as current → mitigated identically to ADP-SPEC-044/045: sync failures are a first-class, logged/observable event.

**Residual risk**: same class of accepted risk as ADP-SPEC-044 — no sensitive-category redaction question exists for this domain, so there is no equivalent to ADP-SPEC-045's residual-risk trade-off to document.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An AI tool or teammate reads current strategy execution straight from the repo (Priority: P1)

Someone (an AI coding/analysis tool, or a teammate without direct database access) wants to understand the organization's current strategic themes, the objectives under each, how each objective is actually tracking against its target, what remediation/execution work (initiatives) is underway, and how all of that traces to capabilities, value streams, designs, applications, regulatory controls, and frameworks. Instead of needing API/database access, they open the versioned files already checked into the repository and find strategy data that reflects what's actually in the platform today.

**Why this priority**: this is the entire reason this feature exists — the same "only in Postgres, not in git" gap ADP-SPEC-044/045 closed for their domains, now for Strategy, the largest domain not yet in git (four migrations' worth of tables) and the natural closer of the traceability gap those two increments left open.

**Independent Test**: can be fully tested by creating/editing themes, objectives, progress entries, and initiatives through the existing platform, then confirming the corresponding files exist, are well-formed, and contain the current data.

**Acceptance Scenarios**:

1. **Given** a theme and an objective under it exist in the platform, **When** someone looks at the exported files, **Then** each one appears in the export with its current identity and fields.
2. **Given** an objective has a metric target and recorded progress entries, **When** someone looks at its exported file, **Then** the file shows the same computed status (per Clarification Q1) the live API would show, plus the full progress history behind that computation.
3. **Given** an objective is linked to a business capability, value stream, design, application, or regulatory control, **When** someone looks at the exported files, **Then** those relationships are visible without needing database access.
4. **Given** a strategic theme is tagged against a regulatory framework, **When** someone looks at the exported files, **Then** that tag is visible in the theme's own exported file.
5. **Given** a strategy initiative is linked to one or more objectives, and separately to one or more assessed compliance mappings, **When** someone looks at the exported files, **Then** both relationships — and, for the compliance mappings, their live compliance status — are visible.

---

### User Story 2 - A reviewer sees exactly what changed in strategy execution as a readable diff (Priority: P2)

An architect or reviewer wants to know what changed in the organization's strategy over some period (e.g., "which objectives moved to at-risk last sprint?"). They look at the version history of the exported files and see a clear, human-readable diff of exactly what changed, when.

**Why this priority**: the same second-order "reviewable history" benefit ADP-SPEC-044/045 established; only has value once Story 1's export mechanism exists and is trustworthy.

**Independent Test**: can be fully tested by making a strategy change (e.g. recording a new progress entry), letting the export sync run, and confirming the resulting file change is a small, targeted diff clearly attributable to that specific change.

**Acceptance Scenarios**:

1. **Given** a single objective's progress entry is recorded, **When** the export sync runs, **Then** the resulting file change is limited to that objective's data — unrelated themes/objectives/initiatives are untouched.
2. **Given** an objective, theme, or initiative is deleted, **When** the export sync runs, **Then** its exported file (and any relationship record whose existence depends on it) is removed rather than left behind as stale, orphaned content.

---

### Edge Cases

- What happens when a theme, objective, or initiative is deleted? Its corresponding exported file MUST be removed on the next sync, along with any relationship record whose existence depends on it (e.g., a theme–framework tag where the theme no longer exists).
- What happens when the export sync itself fails partway? Same as ADP-SPEC-044/045: the failure MUST be surfaced, and MUST NOT leave a partially-written, corrupted file in place of a previously-good one.
- What happens on the very first run, before any export has ever happened? The system MUST perform a full initial export of everything that currently exists, not require a separate "bootstrap" action.
- What happens if an objective has no metric target set at all? Its exported status computation MUST still follow the platform's own existing rule for that case (never a distinct or novel export-only rule) and its progress history MUST be exported as an empty list, not omitted.
- What happens if an objective has zero recorded progress entries? Its exported file MUST still exist, with an empty progress list, not be skipped.
- What happens if a capability or value-stream file (ADP-SPEC-044) has no design links at all? The `linked_designs` field added by Clarification Q2 MUST be present as an empty list, not omitted, matching every other "absence" convention this export tree already uses.
- What happens if the same underlying data is exported again with no actual changes since the last sync? Same as ADP-SPEC-044/045: the system SHOULD NOT rewrite files whose content is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST export every strategic theme, every strategic objective, and every strategy initiative to a versioned file representation.
- **FR-002**: System MUST keep the exported files up to date via the same debounced/scheduled background sync mechanism ADP-SPEC-044/045 already established, not a new, separately-tuned one.
- **FR-003**: System MUST write one file per individual theme, objective, and initiative (not one aggregate file per entity type) — so a change to one entity produces a diff scoped to that entity alone.
- **FR-004**: System MUST remove the exported file representation for any theme, objective, or initiative that has been deleted from the platform.
- **FR-005**: System MUST NOT modify the underlying theme, objective, initiative, or link data as a side effect of exporting it — this is a read-only export.
- **FR-006**: System MUST log an observable failure event when an export sync attempt does not complete successfully, rather than failing silently.
- **FR-007**: System MUST NOT leave a partially-written or corrupted exported file in place of a previously-valid one if an export attempt fails partway through.
- **FR-008**: System MUST perform a complete export of all existing themes, objectives, initiatives, and their in-scope relationships on first run, without requiring a separate manual bootstrap step.
- **FR-009**: System MUST NOT rewrite an exported file whose underlying data has not changed since its last successful export.
- **FR-010**: A theme's exported file representation MUST include its identity, name, description, owner, priority, and which regulatory frameworks it is tagged against.
- **FR-011**: An objective's exported file representation MUST include its identity, owning theme, owner, statement, metric fields (name, target value, target unit, direction) when set, fiscal year, period, and its computed status (per Clarification Q1) with status reason when abandoned.
- **FR-012**: An objective's exported file representation MUST include its complete, dated progress history (as-of date, actual value, note, recorded by) — not a summary or the most recent entry alone.
- **FR-013**: An objective's exported file representation MUST include which business capabilities, value streams, designs, applications, and regulatory controls it is linked to, and which other objectives it depends on / is depended on by.
- **FR-014**: An objective's exported file representation MUST include which strategy initiatives are linked to it — the reverse of an initiative's own forward link — closing the traceability loop this feature's parent epic exists to close.
- **FR-015**: A strategy initiative's exported file representation MUST include its identity, name, description, owner, status, which objectives it is linked to, and which specific, already-assessed compliance mappings it is linked to, each with its live compliance status, evidence reference, and assessment date (never a value captured at link-creation time).
- **FR-016**: System MUST add a `linked_designs` field to ADP-SPEC-044's existing exported capability and value-stream files (per Clarification Q2), reflecting `capability_design_links`/`value_stream_design_links` (spec 034) — the two design-linking join tables both prior export increments explicitly deferred.
- **FR-017**: System MUST NOT introduce a new file location, entity type, or field beyond what is listed above without a corresponding update to this specification.

### Key Entities *(include if feature involves data)*

- **Strategic Theme, Strategic Objective, Strategy Initiative** *(existing entities, not introduced by this feature)*: the platform's existing typed strategy-capture data (specs 050/915/916). This feature defines no new entity or field for any of them — it produces a file-based, versioned representation, kept in sync with live Postgres state.
- **Objective Progress Entry** *(existing entity)*: a dated, editable actual value recorded against an objective's target (spec 915), exported as a nested list within its owning objective's file, not as separate files.
- **Objective/Initiative relationship records** *(existing, not new)*: objective–capability, objective–value-stream, objective–design, objective–application, objective–control links; objective–objective dependencies; initiative–objective links; initiative–compliance-mapping links (five parallel tables, one per mapping target shape); theme–framework tags.
- **Export Sync State** *(new, minimal)*: same internal change-detection/deletion-tracking concept ADP-SPEC-044/045 introduced, extended to cover this domain's entity types — exact shape is a planning-phase decision.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Someone with no database or API access can determine the platform's complete, current set of strategic themes, objectives (including their live tracking status and full progress history), strategy initiatives, and every traceability link listed in FR-013/FR-014/FR-015/FR-016, entirely from the exported files.
- **SC-002**: A change made to a single theme, objective, initiative, or relationship is reflected in its corresponding exported file within a bounded, predictable delay (matching ADP-SPEC-044/045's established delay), with zero unrelated files changed as a side effect.
- **SC-003**: 100% of currently-existing themes, objectives, initiatives, and in-scope relationships have a corresponding, up-to-date exported file at all times (excluding the bounded sync delay in SC-002) — zero orphaned files for deleted entities, zero missing files for existing entities.
- **SC-004**: When an export sync attempt fails, that failure is discoverable in logs within the same operational visibility the platform already provides (matching ADP-SPEC-044/045's SC-004).

## Assumptions

- This feature does not itself commit the exported files to git or push them anywhere — identical assumption to ADP-SPEC-044/045.
- The export writes to the same configured filesystem location concept (`export_root`) ADP-SPEC-044/045 already established, as a sibling subdirectory under the same root rather than a second, separately-configured destination.
- The bounded sync delay referenced in SC-002 is expected to match whatever cadence ADP-SPEC-044/045 established for their own background sync, reusing the same underlying mechanism rather than introducing a second, differently-tuned one.
- No sensitive-category redaction question exists for this domain (confirmed directly against the permission model) — unlike ADP-SPEC-045, this feature makes no residual-risk trade-off of that kind.
