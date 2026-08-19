---
document_type: speckit-input
title: Compliance Domain — Regulatory & Industry Framework Tracking
bundle: COMPLY-01 through COMPLY-05
status: draft
layer: cross-cutting (governance-adjacent; reads from Business, Application, Solution, Strategy)
last_updated: 2026-08-17
---

# Compliance Domain — Speckit Bundle

Five specs, extending the STRAT-01–04-style shape: registry entities first,
traceability links second, derived status third, read-side rollup last, and a
fifth spec (COMPLY-05) linking the compliance domain back to Strategy
(Themes/Objectives/Initiatives) — added once it became clear compliance work
doesn't live in isolation from strategic planning.

**Package placement (open question, not decided here):** candidate is a new
sibling package `adp.compliance`, following the precedent set when
`adp.strategy` was split out of `adp.business` once the existing package's core
files crossed ~2,800 lines. Before committing, measure `adp.knowledge` and
`adp.business` against that same threshold — if either is already large, that's
the signal to keep `adp.compliance` separate rather than folding controls into
an existing domain. Not resolved here; flag for a product-level decision.

---

## COMPLY-01 — Framework & Control Registry

### What to build

Two entities:

**`RegulatoryFramework`**
- `id`, `name` (e.g. "NIST 800-53 Rev 5", "GDPR", "SOC 2 Type II")
- `jurisdiction` (Text — e.g. "EU", "US-Federal", "Global")
- `authority` (Text — issuing body, e.g. "European Commission", "NIST")
- `version` (Text, not folded into `name` — frameworks get revised independently)
- `effective_date` (Date, nullable — some frameworks are perpetually "current")
- `source_url` (Text, nullable)
- `created_at`, `updated_at`

**`Control`**
- `id`, `framework_id` (FK → `RegulatoryFramework`, `ON DELETE CASCADE`)
- `parent_id` (self-referencing FK, nullable — mirrors the capability
  hierarchy's parent-referencing shape; supports framework → family → control,
  e.g. NIST `AC` family → `AC-2` control)
- `code` (Text — e.g. `AC-2`, `Art. 17`; unique per framework, not globally)
- `title`, `description`
- `position` (SmallInteger, for stable ordering within a parent — same
  convention as capability/value-stream-stage ordering)
- `created_at`, `updated_at`

### Why

Frameworks and controls are reference data — architects don't edit NIST's
control catalog, they import it and map their estate against it. Keeping this
as its own registry (rather than knowledge-base entries) preserves the
distinction ADP already draws between "content you look up" (`knowledge`,
free-text + vector search) and "content you formally link against with a
typed, evidenced relationship" (everything using the composite-PK join-table
shape).

### Out of scope

- No built-in importer for any specific framework's canonical control set
  (NIST, ISO 27001, etc.) — controls are entered manually or via a future
  bulk-import tool, not fetched live from an external authority.
- No versioning/diffing between framework revisions (e.g. "what changed
  between NIST 800-53 Rev 4 and Rev 5") — `version` is a flat field, not a
  linked history.
- No control-to-control relationships (e.g. "supersedes", "overlaps with")
  in this pass.

### Constraints tied to ADP conventions

- `parent_id` self-reference follows the same three-level hierarchy pattern as
  capabilities — but depth isn't hard-capped at 3 the way capabilities are;
  some frameworks nest deeper (framework → family → control → sub-control).
  Open question below.
- Migration owns the FK/PK/CHECK constraints; the store-layer `Table()` object
  is DML-only, per existing convention.
- `code` uniqueness is scoped to `framework_id`, not global — needs a composite
  unique constraint, not a simple unique column.

### Open questions

- Is control nesting depth actually unbounded in practice, or does it settle
  at a knowable max (3–4 levels) the way the business capability hierarchy
  did? Worth checking against 2–3 real framework catalogs before capping it.
- Should `RegulatoryFramework` support a `status` (active / superseded /
  draft) the way Objectives carry a lifecycle status? Left open — no evidence
  yet that frameworks need lifecycle tracking distinct from `effective_date`.
- **Granularity varies within a single framework, not just across
  frameworks.** A GDPR walkthrough surfaced this concretely: Art. 5 (broad
  principles) plausibly wants six `Control` children — Art. 5(1)(a)–(f) — while
  Art. 33 (breach notification) is narrow enough to stand alone as one leaf
  control. So depth isn't just framework-dependent, it's article-dependent
  *within* a framework. `position` and nullable `parent_id` already support
  this without a schema change, but it's worth naming explicitly so nobody
  assumes a uniform depth per framework when seeding real data.

---

## COMPLY-02 — Control Mappings (Traceability Links)

### What to build

**`ControlMapping`** — join table(s) linking a `Control` to the entity it
governs.

Shared columns across all mapping tables:
- Composite PK: `(control_id, entity_id)`
- `ON DELETE CASCADE` on both FK legs
- `compliance_status` (Text, named CHECK constraint: `compliant` / `partial` /
  `non_compliant` / `not_assessed` / `not_applicable`)
- `evidence_ref` (Text, nullable — pointer to supporting evidence: a doc URL,
  an audit finding ID, or a design annotation; format intentionally loose in
  this pass)
- `assessed_at` (Date, nullable)
- `assessed_by` (Text, nullable — actor reference, not a hard FK to a user
  table if one doesn't exist yet)
- `created_at`

### Why

A bare link without status and evidence would contradict ADP's own thesis —
"evidenced, not asserted" applies to compliance exactly the way it applies to
Business Value scoring's soft-cap mechanism. `compliance_status` is what makes
this a governance artifact rather than a glorified tag.

### Out of scope

- No workflow/approval process for changing `compliance_status` in this pass —
  it's a direct field update, not a proposal→confirm flow. (Whether it *should*
  go through the AI-proposes/human-confirms gate is an open question below,
  not assumed either way.)
- No file/attachment storage for evidence — `evidence_ref` is a pointer, not a
  blob.

### Constraints tied to ADP conventions — and the one open structural decision

Every existing many-to-many link (capability↔design, value-stream↔design,
objective↔capability, objective↔value-stream) targets exactly **one** other
entity type, which is why a clean composite-PK-with-FK join table works. A
`Control` plausibly maps to a `Capability`, an `Application`, a `Design`, or
even a `Pattern` in the knowledge base — four possible targets.

Two ways to resolve this, **neither chosen here**:

1. **Four separate join tables** (`control_capability_mapping`,
   `control_application_mapping`, `control_design_mapping`,
   `control_pattern_mapping`) — one per target type, each following the exact
   existing shape with full FK/PK enforcement at the DB level. More tables,
   but preserves the database-level integrity guarantee that's a stated
   non-functional requirement.
2. **One polymorphic table** (`entity_type` + `entity_id` in the composite
   key) — fewer tables, but Postgres cannot FK-constrain a polymorphic target,
   so referential integrity would move to the application layer for this one
   link type only, breaking the "cross-entity links are FK-enforced at the
   database level, not just application-layer checks" NFR.

Recommendation to flag for product decision: option 1 is more consistent with
existing conventions and the stated NFR, at the cost of four tables instead of
one. This should be an explicit open question in the actual spec, not resolved
silently in either direction.

### Open questions

- Four tables vs. one polymorphic table (above) — product-level call.
- Does a `Control` mapping ever need to target more than one entity
  simultaneously with *different* compliance statuses per target (e.g.
  compliant at the Capability level, not-assessed at the Application level)?
  Assumed yes, implicitly, by having independent rows per target type — worth
  confirming that's the intended semantic before implementation.
- Should sensitive-read gating apply here the same way it does for
  application risk/cost/governance data? `compliance_status` and
  `evidence_ref` both seem at least as sensitive.
- **A single control routinely needs different target types depending on what
  "evidence" even means for it.** GDPR Art. 32 (security of processing) is the
  clean example: it's not credibly evidenced at the abstract Capability level
  ("Identity & Access Management" has no `technical_fit_score`) — it's
  evidenced at the Application level (MFA enforced, encryption-at-rest
  configured, specific config flags). This is a second, independent argument
  for needing multiple target types in COMPLY-02 beyond "which tables exist" —
  it also affects which target type is the *natural* one to map a given
  control against, and that guidance (not just the schema) should probably
  live somewhere discoverable, maybe as a per-control `suggested_entity_type`
  hint or just documentation. Not resolved here.
- **Some controls don't cleanly belong to any single mapped entity at all.**
  GDPR Art. 30 (records of processing activities) and Art. 25 (privacy by
  design) read as standing, estate-wide obligations rather than something one
  Capability or Application satisfies on its own. Forcing these onto a single
  arbitrary target would misrepresent what's actually being assessed. Worth
  considering an "organization-wide" pseudo-mapping — e.g. a nullable
  `entity_id` with a `scope: organization` flag, or a dedicated
  `control_organization_mapping` table with no join key at all, just a status
  per framework. Left open; flag for product-level decision alongside the
  four-tables-vs-polymorphic question above, since it's the same underlying
  tension (rigid FK-enforced targets vs. real-world mapping shapes that don't
  fit one entity).

---

## COMPLY-03 — Derived Compliance Status

### What to build

`compute_compliance_status(entity_type, entity_id) -> ComplianceStatus`

A pure function, same family as `compute_evolution_stage()` and
`compute_business_value_score()`, following ADP's pattern of deriving status
from data rather than storing it as an independently-editable field.

Aggregation logic (proposed, mirrors the Health rubric's "lowest score wins"):
- If any mapped control for the entity is `non_compliant` → overall status is
  `non_compliant`.
- Else if any mapped control is `partial` or `not_assessed` → overall status
  is `partial`.
- Else if every mapped control is `compliant` or `not_applicable` (with at
  least one `compliant`) → overall status is `compliant`.
- No mapped controls at all → `not_assessed`.

This deliberately mirrors the Health rubric's minimum-aggregation, not the
Business Value rubric's weighted average — one non-compliant control should
flag the whole entity, not get averaged away by ten compliant ones. Same
justification as the Health rubric: this is risk-gate logic, not an
independent-signals blend.

### Why

Matches ADP's existing convention that any rollup status a screen displays
must be a computed view over typed data, never a hand-set field that can drift
from what the underlying mappings actually say.

### Out of scope

- No weighting by control severity/criticality in this pass (a `non_compliant`
  on a minor control counts the same as one on a critical control). Flagged
  as a likely v2 need, not built now.
- No time-decay on `assessed_at` (e.g. auto-downgrading to `not_assessed`
  after N months) — status reflects the last recorded assessment indefinitely
  until someone updates it.

### Constraints tied to ADP conventions

- Pure function, unit-testable in isolation before wiring into any store or
  router — per your usual validate-before-implement approach.
- Should be tested standalone against a matrix of mapping-status combinations
  the same way `compute_evolution_stage()` was validated before full
  implementation.

### Open questions

- Should `not_applicable` controls be excluded entirely from the aggregation
  (as modeled above) or actively required — i.e., does an entity need *at
  least one* mapped control to be a required aggregate rather than falling
  through to `not_assessed`? Left as written above but worth confirming
  against a real framework's expectations (e.g. does SOC 2 require full
  Trust Services Criteria coverage before an entity can be "compliant" at
  all?).
- Severity/weighting scheme for a future version — deliberately not designed
  yet.

---

## COMPLY-04 — Compliance Rollup (Read-Side)

### What to build

- A read-side rollup endpoint/view: per-`RegulatoryFramework` coverage across
  the estate — count of entities at each `compliance_status`, surfaced the
  same way the Governance & Standards screen already claims (but doesn't yet
  back with real data) a "standards compliance" rollup.
- Entity-level traceability: given a `Capability`/`Application`/`Design`, list
  its mapped controls and each one's status — the same reverse-traceability
  shape as "which designs touch this capability."
- A single-pane summary card, matching the shape of the Strategy domain's
  landing-dashboard card work already done, but for Governance — framework
  count, overall coverage %, at-risk entity count.

### Why

Rollups and dashboard tiles should be *rendered outputs of the model*, per
ADP's core thesis — not separately maintained. This spec makes that literal
for compliance the same way COMPLY-01–03 made the underlying data typed and
queryable in the first place.

### Out of scope

- No PDF/export "compliance report" generation in this pass — that's a later
  bead once the underlying reads are proven out, likely reusing whatever
  export machinery `adp.export` already has for continuous JSON export.
- No cross-framework "which controls overlap across NIST and ISO 27001"
  analysis — single-framework rollups only.

### Constraints tied to ADP conventions

- Sensitive fields (`compliance_status`, `evidence_ref`) should sit behind the
  same sensitivity-gated read permission model as application risk/cost/
  governance data, independent of general domain read access — consistent
  with the existing NFR, and flagged as an open question in COMPLY-02 that
  should resolve before this spec is finalized.
- Card design should follow the same speckit-input-file → landing-dashboard
  pattern already used for the Strategy domain card.

### Open questions

- Does this rollup live on the existing Governance & Standards screen (which
  already implies it in its caption) or get a dedicated Compliance screen?
  Given the domain now has real entities (frameworks, controls, mappings)
  rather than just an audit-trail view, a dedicated screen may be warranted —
  left for a product decision.
- Should framework coverage % be visible platform-wide on the Overview
  dashboard (alongside the other stat tiles), or only within Governance? The
  Strategy domain precedent (no Overview card yet) suggests starting scoped
  and expanding later rather than front-loading it.

---

## COMPLY-05 — Strategy Domain Linkage

### What to build

Three distinct link types, deliberately not merged into one table — Strategy
and Compliance change at different rates (fiscal-cycle vs. external regulatory
clock) and should stay separate models, same principle already applied to
keeping Strategy, Business, and Application distinct.

**1. `ObjectiveControlMapping` — why an objective exists**
- Composite PK `(objective_id, control_id)`, `ON DELETE CASCADE` on both legs
  — same shape as the existing `objective_capability` /
  `objective_value_stream` join tables.
- No `compliance_status` column here — that lives on `ControlMapping`
  (COMPLY-02). This link answers "is this objective regulatory-driven,"
  not "is the control satisfied."
- Supports queries like "which objectives exist because of a regulatory
  requirement" — audit narrative and portfolio-level "how much strategic work
  this year is compliance-driven" reporting.

**2. `InitiativeControlMapping` — the remediation loop**
- Links an `Initiative` to a specific `ControlMapping` row (not the abstract
  `Control`) — the target is the control *in context of a specific entity*,
  since that's what actually carries a `compliance_status` to move.
- Composite PK `(initiative_id, control_mapping_id)`, `ON DELETE CASCADE`.
- This is the highest-value link in the bundle: once an Initiative closes and
  `compute_compliance_status()` (COMPLY-03) re-runs, the status change is
  directly attributable to remediation work, giving a live view instead of a
  manually maintained tracker.
- **Does not require an Objective to exist.** An assessment can flip a
  `ControlMapping` to `non_compliant` and spawn an Initiative directly — see
  open question below on whether Initiative→Objective is currently mandatory.

**3. `ThemeFrameworkMapping` — coarse grouping (lower priority)**
- Optional, lighter-weight than the other two. A reusable Theme (e.g.
  "Regulatory & Compliance") tagged against one or more Frameworks, the same
  reuse pattern Themes already support across Objectives.
- Useful for portfolio rollups, not load-bearing for remediation tracking —
  build only if COMPLY-05's other two links prove insufficient for the
  reporting need.

### Why

Compliance findings need to be actionable, not just visible. Without
`InitiativeControlMapping`, a `non_compliant` status is a dashboard fact with
no connection to the work meant to fix it — exactly the kind of drift-prone,
hand-maintained tracking ADP's core thesis exists to eliminate. And without
`ObjectiveControlMapping`, there's no way to answer "why does this objective
exist" when the answer is regulatory rather than purely business-driven.

### Out of scope

- No automatic Initiative creation on a `ControlMapping` status change — a
  human still creates the Initiative and links it; this spec provides the
  link, not an automation trigger. (Whether that automation should exist
  later, and whether it would need to go through the AI-proposes/human-
  confirms gate, is a follow-on question, not decided here.)
- No cascading status logic where an Initiative's own lifecycle state
  automatically flips `compliance_status` — `compute_compliance_status()`
  still derives purely from `ControlMapping` rows per COMPLY-03; an Initiative
  closing doesn't itself change anything until someone updates the mapping's
  status with evidence.

### Constraints tied to ADP conventions

- Both new join tables follow the existing composite-PK / `ON DELETE CASCADE`
  / migration-owns-constraints shape.
- `InitiativeControlMapping` targeting `ControlMapping` rather than `Control`
  directly is a deliberate deviation worth calling out explicitly in the real
  spec — every other join table in the system targets a primary entity, not
  another join table's row. This is closer in spirit to an annotation on a
  relationship than a relationship between two entities, and may need its own
  justification pass during review.

### Open questions

- **Is Initiative→Objective currently mandatory in the schema?** This is the
  load-bearing question for the whole spec. If it's mandatory, bottom-up
  compliance remediation (assessment finds a gap → Initiative directly, no
  Objective) gets forced through strategic-planning ceremony it doesn't need.
  If it's already optional, COMPLY-05 needs no schema change here — just
  confirm before assuming either way.
- Should `ObjectiveControlMapping` carry its own lightweight status (e.g. "in
  progress toward compliance" vs. "compliance is incidental to this
  objective"), or is presence-of-link sufficient signal? Left as a bare link
  for now — no evidence yet that a status field earns its complexity here.
- Is `ThemeFrameworkMapping` (#3) worth building in this pass at all, or
  should it wait until there's a concrete portfolio-reporting need that the
  other two links can't answer? Leaning toward deferring it, not resolved.

---

## Implementation order (per bundle, following existing convention)

For each spec: migration → Pydantic models (`extra="forbid"`) → async
SQLAlchemy Core store → FastAPI router (with route-prefix→`ActionType`
mapping registered) → unit tests. `compute_compliance_status()` (COMPLY-03)
should be built and tested as a standalone pure function before it's wired
into any store or router, matching how `compute_evolution_stage()` was
validated. COMPLY-05 depends on COMPLY-02 (`ControlMapping` must exist before
`InitiativeControlMapping` can target it) and on Strategy's existing
Objective/Initiative models — sequence it after COMPLY-02, not in parallel.
