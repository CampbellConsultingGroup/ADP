# Feature Specification: Objective ↔ Design/Application Traceability

**Feature Branch**: `917-objective-design-traceability`
**Created**: 2026-08-13
**Status**: Draft
**Input**: User description: "ADP-d8u.2 — Link designs to strategic objectives (design ↔ StrategicObjective traceability)"

## Ground-Truth Corrections

The source bead and `docs/strategy-domain-expansion-specs.md` SPEC-STRAT-02 were re-verified against
the actual codebase before writing this spec; several assumed facts turned out to be wrong or
imprecise. Corrections carried forward into this spec and its downstream plan:

1. **No `UUID` primary keys anywhere in this schema.** The source doc's data-model tables show
   `id UUID PK` for the new join tables' foreign-key columns. Direct migration reads confirm every
   relevant id is a plain string type instead: `strategic_objectives.id` is `sa.String(36)`,
   `designs.id` is `sa.Text()`/`sa.String()` (no fixed length — the `DSN-NNN` format), and
   `applications.id` is `sa.String(36)`. This spec's join tables use string FKs throughout, matching
   `capability_design_links`/`value_stream_design_links` (migration 008) exactly, not the doc's UUID
   assumption.
2. **`GET /store/designs/{id}/objectives` doesn't name a real package.** There is no `adp.store`
   *router* — `adp.store` is the `DesignStore` persistence class; the actual HTTP endpoints for
   designs live in `src/adp/api/routers/designs.py` under the existing `/api/v1/designs` prefix. The
   reverse-lookup endpoint belongs there, as `GET /api/v1/designs/{id}/objectives`.
3. **The applications router prefix is plural** (`/api/v1/applications`, confirmed directly in
   `src/adp/application/router.py`), not the doc's singular `/application/{id}/objectives`. Corrected
   to `GET /api/v1/applications/{id}/objectives`.
4. **No new package or submodule needed.** Unlike ADP-d8u.6 (which measured `adp.strategy` at
   1,434 lines and chose a new submodule for a genuinely new concept — initiatives), this feature adds
   two more join tables of the *exact same shape* two already-existing ones use
   (`strategic_objective_capabilities`/`strategic_objective_value_streams`, both already living in
   `models.py`/`store.py`/`router.py`). This is "more of the same," not a new concept — it belongs in
   the existing three files directly. Current total (`models.py`+`store.py`+`router.py`, excluding the
   `initiatives.py` submodule) is 1,596 lines, comfortably under the ~2,847-line split threshold even
   after this addition.
5. **Design existence checks use a lightweight read-only table mirror, not `DesignStore.get()`.**
   `adp.business.store` already establishes the pattern for validating a `design_id` exists without
   pulling the full `ArchitectureDescription` JSONB: it declares its own minimal
   `_designs = sa.Table("designs", ..., sa.Column("id", sa.Text(), primary_key=True), ...)` against its
   own `_metadata`, used purely for existence/JOIN queries via a raw session, not `DesignStore`'s
   heavier `.get()` (which raises `DesignNotFoundError` and fetches full content). This spec's
   `adp.strategy.store` does the same for both `designs` and `applications`.
6. **`adp.application`'s own `ApplicationDetail.tsx` already has real sectioned panels** (capabilities,
   design links, initiatives, cost, risk, etc. — confirmed via direct file listing), so an "Objectives
   realized" panel fits there directly, mirroring `CapabilityLinksEditor.tsx`. **`web/src/designs/` has
   no equivalent detail screen** — `DesignsPage.tsx` is a flat list; selecting a design still routes to
   Intake (`App.tsx`'s `onSelectDesign`, unchanged since ADP-914.9's original research). The closest
   thing to a design-scoped detail view today is `C4DesignView.tsx` (the diagram editor itself, reached
   via the nav rail once a design is selected) — not a metadata/traceability screen. Where the
   reverse "Objectives realizing this design" panel should live is a genuine open question, resolved
   in Clarifications below.

## Clarifications

### Session 2026-08-13

- Q: Where should the reverse "Objectives realizing this design" panel live, given `web/src/designs/`
  has no detail screen and `C4DesignView.tsx` is a diagram-editing surface, not a metadata screen? →
  A: Add a small collapsible "Traceability" section to `C4DesignView.tsx` (alongside the canvas), since
  it's the only design-scoped screen that exists today; it will need a next-door home once a proper
  design detail screen exists, but that's out of scope here.
- Q: Should linking an objective to a design require the design to already be linked (via
  capability/value-stream) to that objective's own capability/value-stream targets, as a soft
  consistency check? → A: No — allow independent, unconstrained links. A design can realize an
  objective through a capability path the objective doesn't directly name; enforcing the soft
  constraint would block legitimate cases and adds real validation complexity for a benefit no other
  traceability link in this codebase currently enforces (capability↔design and value-stream↔design
  links are already unconstrained the same way).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this document, plus `/speckit-plan`/`/speckit-tasks` before
  any code.
- **ART-IV** — Test-Driven Development: all store/router functions and reverse-lookup endpoints get
  failing tests before implementation, mirroring ADP-d8u.1/.5/.6's established rhythm in this package.
- **ART-VII** — AI Grounding: not applicable — this feature is pure human-driven CRUD/traceability,
  no AI-generated content or LLM calls anywhere in its scope.
- **ART-IX** — Auditability: `adp.strategy` has no `AuditEntry`-writing capability (established in
  ADP-d8u.5/.6 — `audit_entries` is tightly coupled to `design_id`/`design_version`, which strategy
  link tables don't have). Satisfied the same way as every other write in this package: structured
  `logger.info(...)` calls on link/unlink.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Traceability integrity between strategic objectives and the designs/applications
that realize them — low sensitivity (no PII, no secrets, no financial data), but incorrect or spoofed
links could mislead governance reporting about which objectives are actually being delivered.

**Trust boundaries crossed**: Browser → API only (same as every other `adp.strategy` write endpoint).
No new external integration, no new AI/LLM call.

**Abuse cases**:
- An authenticated-but-unauthorized actor links an objective to an arbitrary design/application to
  falsely inflate delivery-progress reporting → mitigated by the existing `strategy:write`
  (`ActionType.WRITE_BUSINESS_ARCH`) route-prefix gate, unchanged from every other mutating endpoint in
  this package — no new attack surface introduced.
- A malformed `design_id`/`application_id` is submitted to probe for existence of designs/applications
  the actor shouldn't be able to enumerate → both existence checks return a generic 404 with no
  additional metadata beyond "not found," matching the existing capability/value-stream link pattern.

**Residual risk**: Same as the existing capability/value-stream link endpoints this feature mirrors —
accepted, since those have been in production since ADP-d8u.1 with no incident.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Link a design to the objective(s) it realizes (Priority: P1)

A strategy lead or architect, viewing a strategic objective, links one or more designs to it to record
that "this design is how we're delivering this objective." The link is visible from both the objective
side (which designs realize it) and, since the design is opened elsewhere in the app, from the design
side too.

**Why this priority**: This is the actual top-priority open-frontier gap named in the source
requirements doc — today traceability stops at Layer 1 (capabilities/value streams); this closes the
gap to Layer 3 (designs), the most concrete artifact in the chain.

**Independent Test**: From an objective's detail view, link an existing design, confirm it appears in
the objective's linked-designs list, confirm the same link is visible as "Objectives realizing this
design" when that design is opened in the C4 Design View, then unlink and confirm it disappears from
both sides.

**Acceptance Scenarios**:

1. **Given** an existing strategic objective and an existing design, **When** the strategy lead links
   them, **Then** the design appears in the objective's linked-designs list and the objective appears
   in the design's "Objectives realizing this design" panel.
2. **Given** a design already linked to an objective, **When** the strategy lead attempts to link the
   same pair again, **Then** the system rejects the duplicate with a clear message (no silent
   no-op, no duplicate row).
3. **Given** a linked objective-design pair, **When** the strategy lead unlinks them, **Then** the
   design no longer appears on the objective and the objective no longer appears on the design.
4. **Given** an objective, **When** the strategy lead attempts to link a design id that doesn't exist,
   **Then** the system rejects the request with a clear "design not found" message.

---

### User Story 2 - Link an application to the objective(s) it realizes (Priority: P2)

The same capability as User Story 1, for applications instead of designs — an objective can name which
applications in the portfolio realize it, visible from both the objective's detail view and the
application's own detail screen.

**Why this priority**: Named in the same source spec as an efficiency pairing with the design link (one
migration, same shape) — lower priority than the design link only because the design is the more
concrete, immediately-useful artifact; applications already have richer traceability elsewhere
(capabilities, initiatives) that this extends rather than introduces from scratch.

**Independent Test**: From an objective's detail view, link an existing application, confirm it appears
in the objective's linked-applications list and in the application's own detail screen as "Objectives
realized," then unlink and confirm removal from both sides.

**Acceptance Scenarios**:

1. **Given** an existing strategic objective and an existing application, **When** the strategy lead
   links them, **Then** the application appears in the objective's linked-applications list and the
   objective appears on the application's detail screen.
2. **Given** an application already linked to an objective, **When** the strategy lead attempts to link
   the same pair again, **Then** the system rejects the duplicate.
3. **Given** a linked objective-application pair, **When** the strategy lead unlinks them, **Then** the
   link disappears from both sides.

### Edge Cases

- Deleting an objective that has design/application links: links are removed automatically
  (`ON DELETE CASCADE`, matching every other traceability link table in this codebase) — never leaves
  an orphaned row.
- Deleting a design or application that has objective links: same cascade behavior, from the other
  side's FK.
- Linking a design/application to an objective is intentionally unconstrained — no requirement that the
  design/application already be linked (via capability/value-stream) to that objective's own targets
  (resolved in Clarifications).
- An objective with zero linked designs/applications shows an empty state on both the objective and
  (where applicable) design/application side, not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a strategy lead to link a strategic objective to a design, given
  both already exist.
- **FR-002**: The system MUST allow a strategy lead to unlink a previously-linked objective-design
  pair.
- **FR-003**: The system MUST reject an attempt to create a duplicate objective-design link with a
  clear "already linked" message, not a silent no-op.
- **FR-004**: The system MUST reject a link attempt referencing an objective id or design id that does
  not exist, with a clear "not found" message identifying which id was invalid.
- **FR-005**: The system MUST show, on a strategic objective's detail view, every design currently
  linked to it.
- **FR-006**: The system MUST show, when a design is opened in the C4 Design View, every strategic
  objective currently linked to it (reverse lookup).
- **FR-007**: The system MUST allow a strategy lead to link and unlink a strategic objective to/from an
  application, mirroring FR-001–FR-004 for applications instead of designs.
- **FR-008**: The system MUST show, on a strategic objective's detail view, every application currently
  linked to it.
- **FR-009**: The system MUST show, on an application's detail screen, every strategic objective
  currently linked to it (reverse lookup).
- **FR-010**: The system MUST remove all of an objective's design/application links automatically when
  that objective is deleted (no orphaned links, no separate cleanup step required).
- **FR-011**: The system MUST remove an objective's link to a specific design/application automatically
  when that design/application is deleted.
- **FR-012**: Objective-design and objective-application linking MUST NOT require any pre-existing
  relationship between the design/application and the objective's own capability/value-stream targets
  (Clarifications).

### Key Entities *(include if feature involves data)*

- **Objective-Design Link**: A record that a strategic objective is realized by a specific design.
  Many-to-many — one objective can link many designs, one design can realize many objectives.
- **Objective-Application Link**: A record that a strategic objective is realized by a specific
  application in the portfolio. Same many-to-many shape as the design link.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A strategy lead can link an objective to a design and see it reflected on both the
  objective's and the design's own view within the same session, with no page reload needed beyond
  normal navigation.
- **SC-002**: Attempting to link an already-linked pair, or a nonexistent design/objective/application,
  always produces a specific, actionable error message — never a silent failure or a generic "something
  went wrong."
- **SC-003**: Deleting an objective, a design, or an application never leaves a dangling traceability
  link visible anywhere in the system.
- **SC-004**: A strategy lead can determine, for any given objective, exactly which designs and
  applications realize it, without needing to cross-reference capability or value-stream links
  manually.

## Assumptions

- No new `ActionType`/permission is needed — link/unlink endpoints fall under the existing
  `/api/v1/strategy/` prefix's `strategy:write` (`ActionType.WRITE_BUSINESS_ARCH`) gate; the two new
  reverse-lookup `GET` endpoints (on the designs and applications routers) are ungated reads, consistent
  with every other read-only traceability endpoint in this codebase.
- No audit entry beyond the standard structured `logger.info(...)` call is needed for link/unlink —
  `adp.strategy` has no mechanism to write a real `AuditEntry` row (established in ADP-d8u.5/.6), and
  this feature doesn't introduce one; consistent with every other write in this package.
- Objective-application links are net-new for this bead (STRAT-02 explicitly separates them from the
  existing, unrelated `adp.application.TransformationInitiative` model — no naming or scope collision).
- The reverse "Objectives realizing this design" panel lives in `C4DesignView.tsx` per the resolved
  Clarification — it is understood to be a placeholder location, not a permanent home, since no
  dedicated design detail screen exists yet.
