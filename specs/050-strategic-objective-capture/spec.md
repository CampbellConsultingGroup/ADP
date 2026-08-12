# Feature Specification: Capture Strategic Objectives

**Feature Branch**: `050-strategic-objective-capture`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "ADP-d8u.1: Capture StrategicObjective as a structured entity (entry form + registry-validated links). Concretely specified by docs/strategic_objective_entry_screen.html and docs/business_strategy.md's design notes."

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: applies — `StrategicObjective` becomes a new canonical entity in ADP's own data model (like `BusinessCapability`/`ValueStream` before it), not a document or side-channel note.
- **ART-III** — Everything is Machine-Readable: applies directly — this is the feature's entire point per `docs/business_strategy.md`'s own framing: a structured `StrategicObjective` (not a text blob) is what lets a future heat map or strategy-map view become a *renderable output* of the model instead of a separately hand-maintained artifact.
- **ART-V** — Security by Design: low-risk — see Threat Model. Ordinary CRUD over already-authorized business data, no new trust boundary.
- **ART-VI** — Observability: applies at the ordinary level — create/update/delete of an objective (and its theme/links) are normal structured-logged mutations, matching every other ADP domain router; no AI step is involved.
- **ART-VII, ART-VIII, ART-IX, ART-X, ART-XI**: do not apply — no AI-generated content, no AI proposal to confirm, no new audit-trail obligation beyond ordinary `created_at`/`updated_at` (matching `BusinessCapability`'s own precedent), no validation gating, no traceability-thread change (linking a *design* to a strategic objective is out of scope for v1).
- **ART-XII** — Fixed Visual Language: does not apply — governs the locked C4 theme specifically.
- **ART-XIII** — Typed Contracts Everywhere: applies — new Pydantic v2 models with `extra="forbid"`, matching every other ADP boundary; the metric/target and horizon fields are explicitly typed values (not free text), per this feature's own core requirement.
- **ART-XIV, ART-XV** — Reproducible builds / Schema evolution: apply at the ordinary migration level — new tables need a normal, reversible Alembic migration (next available: 025).
- **ART-XVI** — Documentation as Code: applies (SHOULD).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: strategic objective content (business problem statements, targets, ownership — may be commercially sensitive) and its links to capabilities/value streams.

**Trust boundaries crossed**: browser → API → Postgres — the same shape as every other ADP content-creation feature (capabilities, value streams, domains); no new external system.

**Abuse cases**:
- A user links an objective to a capability or value stream they can't actually see/manage → mitigated by validating both ends of every link against ADP's existing capability/value-stream registries at write time (the same registry-validation requirement that motivates this feature's whole "structured, not free text" design) — a link can never reference an id that doesn't exist in those registries.
- A user enters a free-text "theme drift" duplicate of an existing theme → mitigated by FR-002 (theme is a selected reference to an existing `StrategicTheme` row, never free text at the point an objective is saved).

**Residual risk**: the same class already accepted for every other ADP business-registry entity (capabilities, value streams, domains) — reused RBAC, no new authorization mechanism introduced.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture a new strategic objective (Priority: P1)

An enterprise architect creates a new strategic objective: selects a strategic theme, names an owner, writes the objective statement (what and why now), sets a measurable metric/target, and picks a horizon. The objective is saved as a structured record the platform can query and aggregate — not a text blob.

**Why this priority**: The foundational capability every other part of this feature depends on, and the direct payoff of the source doc's central insight — a structured objective, not free text.

**Independent Test**: Create an objective with all required fields filled in, reload the page, and confirm every field (theme, owner, statement, metric, target, horizon) reads back exactly as entered, as discrete, separately-queryable fields — not concatenated into a single string.

**Acceptance Scenarios**:

1. **Given** an architect fills in theme, owner, objective statement, metric, target value, target unit, direction, and horizon, **When** they save, **Then** a new strategic objective is created with all of those fields stored as discrete, typed values.
2. **Given** the objective statement or owner is left blank, **When** the architect tries to save, **Then** the save is rejected with a clear indication of which required field is missing.
3. **Given** an architect wants to record a specific numeric target (e.g., "reduce claims cycle time by 40%"), **When** they enter the metric, **Then** they set a target value, a unit, and a direction (increase, decrease, or reach a value) as separate fields — not a single free-text sentence.

---

### User Story 2 - Link an objective to the capabilities and value streams it affects (Priority: P2)

While viewing a strategic objective, an architect links it to one or more existing business capabilities and one or more existing value streams — the architecture elements that operationalize this objective. Both link targets are chosen from ADP's own existing registries, never typed freely.

**Why this priority**: The second half of the source doc's core insight — this is what eventually lets a capability heat map or similar view be *derived* from objectives instead of maintained by hand. Lower priority than User Story 1 because an objective is already meaningful and query-able on its own; the links add traceability on top.

**Independent Test**: Open a saved objective, link it to an existing capability and an existing value stream, reload, and confirm both links persist and reference the real underlying records (not copied names).

**Acceptance Scenarios**:

1. **Given** a saved objective and an existing business capability, **When** the architect links them, **Then** the objective shows that capability in its linked-capabilities list, chosen from the real capability registry (never a freely-typed name).
2. **Given** a saved objective and an existing value stream, **When** the architect links them, **Then** the objective shows that value stream in its linked-value-streams list, chosen from the real value-stream registry.
3. **Given** an objective already linked to a capability, **When** the architect removes that link, **Then** the capability no longer appears in the objective's linked list, and the underlying capability record itself is unaffected.
4. **Given** two different objectives both refer to "risk assessment," **When** an architect links each to a capability, **Then** both necessarily reference the exact same underlying `Risk Assessment` capability record — there is no way for the same real-world concept to be entered as two different, drifting strings across objectives (the "theme drift" problem the source material explicitly calls out).

---

### User Story 3 - Browse, edit, and remove strategic objectives (Priority: P3)

An architect views a list of all captured strategic objectives, opens one to review or edit its fields, and can remove an objective that's no longer relevant.

**Why this priority**: Necessary for the feature to be genuinely usable over time (create-only, with no way to browse or fix a mistake, is not a complete capability), but lower priority than the create/link capabilities that deliver this feature's core value.

**Independent Test**: Create two objectives, confirm both appear in a list view; edit one's owner field and confirm the change persists; delete the other and confirm it no longer appears.

**Acceptance Scenarios**:

1. **Given** multiple saved objectives exist, **When** an architect views the objectives list, **Then** all of them appear with enough summary information (theme, owner, statement snippet, horizon) to identify each at a glance.
2. **Given** a saved objective, **When** an architect edits one of its fields and saves, **Then** the updated value persists and is reflected the next time the objective is viewed.
3. **Given** a saved objective with no other records depending on it, **When** an architect deletes it, **Then** it no longer appears in the list, and its capability/value-stream links are removed along with it (not left as orphaned references).

---

### Edge Cases

- What happens when an architect tries to link a capability or value stream that has since been deleted from its own registry? → Not reachable in practice: links are always created by selecting from the live registry at link-creation time, and a link to a since-deleted record is automatically removed along with it (cascading delete, mirroring the existing `capability_design_links`/`value_stream_design_links` precedent).
- What happens if no strategic themes exist yet when an architect tries to create the very first objective? → The theme selector is empty; the architect is directed to create at least one theme first (a minimal, separate capability — see Assumptions) rather than being blocked with no path forward or allowed to silently bypass the taxonomy with free text.
- What happens when an architect wants to record a purely qualitative objective with no meaningful numeric target? → Metric/target/direction remain optional fields (only the theme, owner, and objective statement are required, per FR-001) — a qualitative objective can be captured without inventing a fake number.
- What happens when the same capability is linked to many different objectives? → Fully supported — a capability or value stream can be linked from any number of objectives (a genuine many-to-many relationship, not one-to-one).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to create a strategic objective with a strategic theme, an owner, and an objective statement as required fields.
- **FR-002**: A strategic objective's theme MUST be selected from a maintained set of existing strategic themes — never entered as free text at the point an objective is saved (preventing the "theme drift" problem described in the source material).
- **FR-003**: Users MUST be able to record a metric, a target value, a target unit, and a direction (increase, decrease, or reach) as an optional, typed part of an objective — never required, and never collapsed into a single free-text string when provided.
- **FR-004**: Users MUST be able to record a horizon (a fiscal year and period) for an objective.
- **FR-005**: Users MUST be able to link a strategic objective to any number of existing business capabilities, chosen from ADP's real capability registry — never entered as free text.
- **FR-006**: Users MUST be able to link a strategic objective to any number of existing value streams, chosen from ADP's real value-stream registry — never entered as free text.
- **FR-007**: Users MUST be able to remove a capability or value-stream link from an objective without affecting the underlying capability/value-stream record itself.
- **FR-008**: Users MUST be able to view a list of all strategic objectives, with enough summary information to identify each one.
- **FR-009**: Users MUST be able to edit any field of a previously-saved strategic objective.
- **FR-010**: Users MUST be able to delete a strategic objective; doing so MUST also remove its capability/value-stream links (no orphaned link records).
- **FR-011**: Users MUST be able to create a new strategic theme (name required) — a strategic objective can never be created before at least one theme exists.
- **FR-012**: This feature MUST NOT alter the existing `BusinessCapability`, `ValueStream`, or `BusinessDomain` models or their existing APIs — it only adds new join relationships pointing at them.

### Key Entities

- **StrategicObjective**: A structured strategic goal. Attributes: theme (reference to a `StrategicTheme`), owner, objective statement, an optional typed metric/target/direction, a horizon (fiscal year + period), timestamps. Relationships: many-to-many with `BusinessCapability`, many-to-many with `ValueStream`.
- **StrategicTheme**: A short, reusable taxonomy label (e.g., "Usage-based pricing," "Operational excellence") that objectives are classified under — exists specifically to prevent the same idea being entered as different strings across objectives.
- **(join) Objective↔Capability link**: Which business capabilities a given objective affects.
- **(join) Objective↔ValueStream link**: Which value streams a given objective affects.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can capture a complete strategic objective (theme, owner, statement, optional metric/target, horizon) in a single sitting, with every field stored as a separately queryable value — never as one unstructured paragraph.
- **SC-002**: 100% of an objective's capability and value-stream links reference a real, currently-existing registry record — zero free-text or orphaned link values are ever possible to create.
- **SC-003**: The same real-world capability or value-stream concept is guaranteed to be referenced identically across every objective that links to it — zero "theme drift" (the same idea entered as two different strings) is structurally possible for links, matching the same guarantee already true of theme selection.
- **SC-004**: An architect can find, review, and correct a previously-captured objective without needing to recreate it from scratch.

## Assumptions

- **`StrategicTheme` gets its own minimal management capability (FR-011), included in this feature's scope.** Directly grounded in this codebase's own precedent: `BusinessDomain` (ADP-SPEC-035) is the closest existing analog — a small, reusable taxonomy entity — and it has its own dedicated create/list surface rather than being entered inline elsewhere. A theme needs the same treatment; without it, the very first objective could never be created (no theme would exist to select). Full theme *editing*/*deletion* is intentionally left out of this iteration's explicit requirements (not needed to unblock objective creation); create + list is sufficient for v1.
- **The capability/value-stream "search and add" UI reuses this codebase's own established `DesignLinkEditor.tsx` pattern** (ADP-SPEC-034): a filtered dropdown of not-yet-linked records plus Link/Remove actions, not a new live-search/typeahead component — confirmed by direct inspection that this is already how ADP links capabilities and value streams to other entities (designs) today, at a comparable registry scale.
- **Metric/target/direction is a typed value, not a free-text string**, mirroring this codebase's own precedent for measurable data (`ADP-9x6`'s TCO feature: `NUMERIC`, never float, for anything meant to be computed against later) generalized beyond money to any measurable metric.
- **Horizon is a structured fiscal-year + period value** (e.g., "Q3 2026," "FY2027" — matching the entry-form mockup's own implied granularity), not a free-text string or a full date-range picker — simpler than a date range while still being a real, sortable/filterable value rather than prose.
- **The many-to-many join tables mirror the existing `capability_design_links`/`value_stream_design_links` pattern exactly** (ADP-SPEC-034, migration 008): composite primary key, `ON DELETE CASCADE` on both legs, one index, `created_at`.
- **Out of scope** (per the parent epic, ADP-d8u): the capability heat map or any other visualization consuming this data (ADP-3up/ADP-3up.1 — a separate, future feature); the narrative/strategy-map/Business-Model-Canvas/Wardley-map/roadmap artifact types described in `docs/business_strategy.md` (scope/sequencing intentionally not decided here); any AI-assisted generation of objectives; linking an objective to a *design* or into ADP's traceability/audit trail (unlike capabilities/value streams, objectives don't gain a `DesignLinkEditor`-style design link in this iteration); any change to the existing `BusinessCapability`/`ValueStream`/`BusinessDomain` models or their existing APIs beyond the new join tables.
