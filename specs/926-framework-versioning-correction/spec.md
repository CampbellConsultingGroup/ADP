# Feature Specification: Regulatory Framework Legal Dates & Identity (COMPLY-01a)

**Feature Branch**: `926-framework-versioning-correction`
**Created**: 2026-08-19
**Status**: Draft
**Input**: User description: "docs/compliance_update.md — keep in mind this was generated outside of the
project. take it as guidance. the specifics are probably not aligned with our reality." An addendum to
COMPLY-01 (`specs/921-compliance-framework-registry/`), proposing to correct `RegulatoryFramework`'s
single free-text `version` field into a set of dated legal-event facts plus two new supporting concepts
(staged application dates, amending instruments). Authored outside this codebase and grounded against the
real, already-shipped, already-populated implementation before this spec was written — see Clarifications.

## Clarifications

### Ground-truth corrections (resolved by direct inspection, before any question was asked)

The source document's *problem statement* — a single field can't represent a real regulatory instrument's
legal shape — holds up under review (confirmed against GDPR, EU AI Act, and DORA, the three frameworks
actually tracked in this system today). Its *specifics*, however, did not match the real implementation in
several places, each corrected here rather than carried through as written:

- **The field being replaced is already free text, not numeric.** The source document's own justification
  for this change opens with "the current scalar `version` field... (`NUMERIC`, e.g. `2.5`)" — but the
  real field is a `VARCHAR(100)` string, and the three real tracked frameworks already store citation-style
  text in it today (GDPR's current value: `"Regulation (EU) 2016/679 - OJ L 119, 4 May 2016, OJ L 127, 23
  May 2018."`). The underlying problem this spec fixes is real (that string already crams two OJ citation
  dates together); the document's stated reason for it was not.
- **`source_url` is not a new field.** It already exists on `RegulatoryFramework` (COMPLY-01), and was
  hardened against `javascript:`-scheme injection during this codebase's own security review. The source
  document's draft model would have silently reintroduced an unvalidated duplicate.
- **There is no `official_title` field.** The real display-name field is `name`, already populated for
  every tracked framework (`"GDPR"`, `"EU AI Act"`, `"DORA (Digital Operational Resilience Act)"`). This
  spec adds a regulation-identity field *alongside* `name`, not a replacement for it.
- **The existing `effective_date` field is not addressed by the source document at all** — its draft model
  silently drops it while introducing similarly-named new date fields. `effective_date` stays exactly as
  it is; the new dates are additions, not a rename.
- **The source document's own "out of scope" section defers UI work to "the Governance & Standards
  screen."** `RegulatoryFramework`/`Control` has never lived there — it's on the dedicated Compliance
  screen (`FrameworkDetail.tsx`). This exact Governance/Compliance naming mix-up has already been caught
  twice this session from other source documents making the same assumption.
- **Real, live data already exists for all three tracked frameworks**, with real `version`/`effective_date`/
  `source_url` values already relied on today. The source document's literal proposed migration (a
  required, non-nullable new identity field with no backfill step, and an unconditional drop of the
  existing field) would either fail outright against that data or silently destroy it. Resolved by the
  first clarification below.

### Session 2026-08-19

- Q: The three real, live frameworks already have real `version` text today. What should happen to that
  text when this ships? → A: **Keep the existing text visible; new structured fields are optional,
  populated over time.** Nothing is auto-parsed or deleted; an architect fills in the new dated fields at
  their own pace, per framework, as a separate follow-on task.
- Q: Does this spec include the Compliance screen's UI (create/edit/display of the new fields), or is it
  data-model-and-API only? → A: **Data model and API only this pass.** The Compliance screen's existing
  Framework form/detail view is unchanged; surfacing the new fields, application phases, and amendments in
  the UI is an explicit follow-on once the backend shape has settled.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: the entire point of this correction — an
  overloaded free-text field that silently mixed a regulation's identity, its publication citation, and
  (for at least one real framework) two separate dates into one string is replaced with typed, individually
  queryable facts.
- **ART-XIII** — Typed Contracts Everywhere: the two new supporting concepts (application phases,
  amendments) are typed Pydantic models, `extra="forbid"`, not a second free-text field playing the same
  overloaded role as the one being fixed.
- **ART-XV** — Schema Evolution is Governed: this is a correction to an already-shipped, already-populated
  entity — the migration must be additive and lossless against real existing rows (resolved above), not a
  destructive rewrite, even though `RegulatoryFramework` sits outside the `ArchitectureDescription`
  generated-schema pipeline that ART-XV's automated gates (QG-03/QG-18) formally cover.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: the same class of reference data as COMPLY-01 itself — which regulations the
organization tracks and their legal timeline. Not independently sensitive beyond what COMPLY-01 already
exposes to general platform read access.

**Trust boundaries crossed**: none new — Browser → API, through the platform's existing OIDC-authenticated
session, identical to every other Compliance write.

**Abuse cases**:
- A future field on the new application-phase or amendment concepts turns out to carry a URL (e.g., a
  citation link per amendment) and is added without the same scheme-validation `source_url` already
  carries → mitigated by treating that validator as the required pattern for any URL-bearing field this
  domain ever adds, not a one-off fix scoped only to the original field. Neither new concept in this pass
  carries a URL field, so this is a residual risk for future work, not an active gap.
- An unauthorized actor edits a framework's legal-event dates to misrepresent its regulatory timeline →
  mitigated by the existing `WRITE_COMPLIANCE` gate, unchanged by this spec.

**Residual risk**: same posture as COMPLY-01 — no independent verification that recorded legal dates are
accurate; an architect's word is trusted, consistent with the platform's existing manual-entry posture for
reference data.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a framework's legal identity and timeline without losing what's already there (Priority: P1)

An architect opens an existing framework (or creates a new one) and records its regulation number, the
dates it was adopted, published, and entered into force, a date representing its current consolidated
state, and a status. The framework's existing name, jurisdiction, authority, current version text, source
link, and effective date remain exactly as they were — nothing about this framework becomes less visible
or less complete as a result.

**Why this priority**: this is the correction itself — the reason the addendum exists. Everything else in
this spec (phases, amendments) only matters once a framework has a trustworthy legal-identity baseline.

**Independent Test**: can be fully tested by adding a regulation number and one legal-event date to an
existing tracked framework, confirming its previously-recorded fields (name, version text, source link,
effective date) are still present and unchanged, and confirming a framework with none of the new fields
set behaves exactly as it does today.

**Acceptance Scenarios**:

1. **Given** an existing framework with only its original fields set, **When** an architect records a
   regulation number and a consolidation date, **Then** both are saved and the framework's original fields
   (name, jurisdiction, authority, version text, source link, effective date) are unchanged.
2. **Given** a framework with none of the new fields ever set, **When** it is viewed or listed, **Then**
   it behaves exactly as it does today — no error, no forced value, nothing missing that was there before.
3. **Given** an architect recording a framework's status, **When** they choose "not yet applicable,"
   **Then** the value is saved as entered — the system does not silently override it based on any other
   field.

---

### User Story 2 - Record that a framework applies in stages (Priority: P2)

An architect records one or more application phases for a framework whose obligations don't all take
effect on the same date (e.g., the EU AI Act's staged rollout: prohibited practices, then GPAI
obligations, then high-risk system requirements). Each phase has a label, a date it takes effect, and an
optional description.

**Why this priority**: real, but only needed for frameworks with staged rollouts — most tracked
frameworks (like GDPR) have a single application date and need zero phases.

**Independent Test**: can be fully tested by adding two or more application phases to one framework with
different effective dates, and confirming a framework with zero phases behaves identically to one that has
never used this capability at all.

**Acceptance Scenarios**:

1. **Given** a framework with a staged rollout, **When** an architect records three application phases
   with three different effective dates, **Then** all three are saved and independently visible.
2. **Given** a framework with a single, non-staged application date, **When** it is left with zero
   application phases, **Then** nothing is required or defaulted on its behalf.
3. **Given** an existing application phase, **When** an architect removes it, **Then** it is gone and the
   framework's other phases (if any) and its own core fields are unaffected.

---

### User Story 3 - Record that a framework has been amended over time (Priority: P3)

An architect records one or more amendments to a framework — later legal instruments that supplement or
modify it — as they're issued (e.g., DORA's growing stack of Regulatory Technical Standards). Each
amendment has a title, an optional citation reference, and an optional effective date.

**Why this priority**: real for frameworks whose obligations are actively being built out post-enactment,
but the least commonly needed of the three stories — many tracked frameworks have no amendments at all.

**Independent Test**: can be fully tested by adding several amendments to one framework over time and
confirming a framework with none behaves identically to one that has never used this capability.

**Acceptance Scenarios**:

1. **Given** a framework, **When** an architect records a new amendment as it's issued, **Then** it's
   added to that framework's growing list without disturbing any amendment already recorded.
2. **Given** a framework with no amendments, **When** it is viewed, **Then** it shows no amendments, not
   an error or a placeholder.
3. **Given** an existing amendment, **When** an architect removes it, **Then** it is gone and the
   framework's other amendments and its own core fields are unaffected.

### Edge Cases

- What happens when two different frameworks are both created without a regulation number? Both are valid
  — a regulation number, once used, must be unique to one framework, but its absence is not itself a
  conflict (mirrors how the existing, already-shipped fields handle "not yet known").
- What happens when a framework is deleted? Its application phases and amendments are removed with it —
  the same cascade-with-disclosure behavior the framework's controls already have today; no orphaned phase
  or amendment record can outlive the framework it describes.
- What happens to a framework's status if it's marked "repealed" but still has controls mapped against it
  from COMPLY-02? Out of scope for this pass — status is a directly recorded fact in this spec, not
  something that blocks or warns on other domains' data; that interaction is a candidate for later work.
- What happens when an application phase's effective date is in the future relative to today? Recorded as
  entered — this spec only records the fact; reasoning about which controls are or aren't yet "in scope"
  based on phase dates is explicitly future work (COMPLY-03's `compute_compliance_status()` does not read
  any framework-level date today, confirmed directly against the code — this spec adds the data it would
  need, not the reasoning itself).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow recording, for any framework, a regulation identity (e.g., "2016/679")
  distinct from its existing display name (e.g., "GDPR") — without requiring one for a framework that
  doesn't have it recorded yet.
- **FR-002**: System MUST allow recording, independently of each other and independently of the existing
  effective-date field, up to four legal-event dates for a framework: when it was adopted, when it was
  published, when it entered into force, and a date representing its current consolidated ("as of") state.
- **FR-003**: System MUST allow recording a framework's status as one of: in force, amended, repealed, or
  not yet applicable — set directly by an architect, not computed automatically, since the facts needed to
  fully automate that determination (in particular, repeal) are not captured by this spec.
- **FR-004**: System MUST preserve every existing framework's current fields (name, jurisdiction,
  authority, its existing version text, source link, effective date) exactly as they are today — none of
  them are deleted, renamed, or hidden as a side effect of this change.
- **FR-005**: System MUST allow recording one or more "application phases" for a framework — a label, the
  date the phase takes effect, and an optional description — to represent frameworks whose obligations
  take effect in stages.
- **FR-006**: A framework MUST be usable with zero application phases recorded — phases are optional, and
  a framework with a single application date needs none.
- **FR-007**: System MUST allow recording one or more "amendments" to a framework — a title, an optional
  citation reference, and an optional effective date — to represent frameworks whose obligations are
  supplemented over time by additional legal instruments.
- **FR-008**: Application phases and amendments MUST each be addable, viewable, and removable
  independently of each other and of the framework's own core fields.
- **FR-009**: Deleting a framework MUST remove its own application phases and amendments — consistent with
  how deleting a framework already removes its controls today.
- **FR-010**: This pass MUST NOT change how the Compliance screen displays or edits a framework — the new
  fields, phases, and amendments are reachable only through the platform's data layer in this pass; the
  visible screen's current behavior is unchanged (Clarifications).
- **FR-011**: This pass MUST NOT attempt to automatically parse a framework's existing version text into
  the new structured fields — that requires per-framework human judgment and is explicit follow-on work,
  not automated here (Clarifications).

### Key Entities *(include if feature involves data)*

- **Regulatory Framework** (existing entity, extended): gains a regulation identity, up to four
  legal-event dates, and a status, alongside its unchanged existing fields (name, jurisdiction, authority,
  version text, source link, effective date).
- **Framework Application Phase** (new): one staged application date for a framework — a label, the date
  it takes effect, and an optional description. Zero, one, or many per framework.
- **Framework Amendment** (new): one later legal instrument amending a framework — a title, an optional
  citation reference, and an optional effective date. Zero, one, or many per framework.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three currently-tracked frameworks continue to display every one of their existing
  fields, unchanged, immediately after this change ships — 0 fields lost or altered.
- **SC-002**: An architect can record a framework's regulation identity and its four legal-event dates
  independently of each other, with zero of them required to save the framework.
- **SC-003**: An architect can record a framework with several application phases and a framework with
  zero application phases equally easily — no minimum enforced.
- **SC-004**: An architect can record a growing list of amendments to one framework over time (5 or more)
  with no limit imposed by the system.
- **SC-005**: Deleting a framework leaves zero of its own application phases or amendments queryable
  afterward.

## Assumptions

- **The existing `effective_date` field is unchanged and unrelated to this spec's new dates** — it is not
  renamed, merged, or replaced; the new legal-event dates are pure additions (Clarifications).
- **The existing `name` field is unchanged** — `regulation_number` is a new, additional identity field,
  not a replacement for the framework's existing display name (Clarifications).
- **`status` is directly set by an architect in this pass, not derived** from application phases or
  amendments — the two new concepts as scoped here don't cleanly cover every status value (in particular,
  nothing in this spec captures a repeal event), so a full derivation isn't attempted; a future pass may
  revisit this once more of a framework's legal history is captured.
- **Application-phase labels are free text in this pass** — no existing consumer (including COMPLY-03's
  `compute_compliance_status()`) reads phase data today, confirmed directly against the code, so a
  controlled vocabulary is deferred until a real consumer needs one.
- **No history is kept for a framework's prior consolidation dates** — the consolidation date always
  reflects the latest known value; a framework's superseded consolidation dates are not retained.
- **`source_url` stays on the framework itself, unchanged** — per-amendment source links are not modeled
  in this pass.
- **Backfilling regulation identities and legal-event dates for the three currently-tracked frameworks is
  a follow-on data-entry task**, not part of this spec (Clarifications) — nothing is lost by deferring it,
  since their existing fields remain fully visible in the meantime.
- **UI work is an explicit follow-on**, not part of this spec (Clarifications) — the Compliance screen is
  unchanged by this pass.
- **`ThemeFrameworkMapping`** (deferred separately, tracked as bead `ADP-1ox`) will inherit whatever
  status/date semantics this spec settles, whenever it is eventually picked up — noted for that future
  work, no action needed here.
