# Feature Specification: Diagram Types Beyond C4

**Feature Branch**: `046-diagram-type-support`
**Created**: 2026-08-06
**Status**: Draft
**Input**: User description: "ADP needs diagram-type support beyond C4 (flowchart, sequence, ER, UML, cloud-architecture diagrams), additive alongside the existing C4 workspace, reusing a mature sibling-project TypeScript diagramming library"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: each new diagram's own DSL source text is that diagram's authoritative representation (parallel to how `ArchitectureDescription` is authoritative for C4) — its rendered SVG/PNG is a generated view of that source, never hand-edited as a primary record. This is a *second*, independent typed-source-of-truth relationship, not an extension of the existing one; `ArchitectureDescription` remains untouched and unaware these diagrams exist.
- **ART-III** — Everything is Machine-Readable: closes a real gap — today, anything that isn't a C4 diagram (a business-process flowchart, a cross-system sequence diagram, a data-architecture ER diagram) has no home in ADP at all and would live as an external file or image with no structured, diffable representation.
- **ART-V** — Security by Design: new user-generated content (diagram DSL source) is stored and later rendered back to other viewers — the central risk is rendered-content injection (see Threat Model), not new the auth/authz surface (RBAC is reused, not reinvented).
- **ART-VI** — Observability is Not Optional: create/edit/delete of a diagram is a normal, structured-logged mutation like any other CRUD action in this codebase; no AI orchestration span is needed since no AI step is involved (ART-VII does not apply — see below).
- **ART-VII** — Grounded AI Only: does **not** apply — explicitly out of scope for this feature (see Assumptions). No AI-generated content of any kind is involved in v1.
- **ART-VIII** — Human-in-the-Loop for Consequence: does **not** apply in its AI-proposal sense — every diagram is 100% human-authored, there is no AI proposal for a human to confirm. Deleting a diagram is a normal, reversible-enough CRUD delete, consistent with how this codebase already treats deletes of business capabilities/applications/domains (a direct `DELETE`, no `confirmation_id` gate — that gate is reserved for AI-originated actions elsewhere in ADP).
- **ART-IX** — Provenance and Auditability: does **not** apply in its append-only-audit-trail sense for v1 — these diagrams are explicitly out of scope for ADP's audit trail this iteration (see Assumptions); ordinary `created_at`/`updated_at` timestamps are sufficient.
- **ART-X, ART-XI** (Validation gating / Traceability): do **not** apply — no LLM-as-a-Judge verdict, and linking these diagrams into ADP's requirement→element→recommendation→verdict thread is an explicit stretch goal for a *later* iteration, not this one.
- **ART-XII** — Fixed Visual Language: does **not** apply — the locked C4 theme (`c4-theme.json`) governs C4 diagram styling specifically; these new diagram types render via their own reused library's styling, a deliberately separate visual system, not a violation of C4's locked theme.
- **ART-XIII** — Typed Contracts Everywhere: applies — the new API boundary for creating/reading/updating/deleting these diagrams uses Pydantic v2 models with `extra="forbid"`, exactly like every other ADP boundary.
- **ART-XIV, ART-XV** (Reproducible builds / Schema evolution): apply at the ordinary migration level (a new table needs a normal, reversible Alembic migration) — no generated-artifact/schema-drift concern the way `architecture-description.schema.json` has, since these diagrams aren't schema-json-generated.
- **ART-XVI** — Documentation as Code: applies (SHOULD).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: diagram DSL source text (may describe sensitive business processes, cross-system integrations, or data architecture) and its rendered SVG output.

**Trust boundaries crossed**: browser (the reused React editor) → API → Postgres — the same shape as every other ADP content-creation feature; no new external system is introduced.

**Abuse cases**:
- A user embeds script-like or malicious markup inside a diagram's text labels (e.g., a node/actor label), attempting stored content injection that executes when a *different* user later views the rendered diagram → mitigated by relying on the reused library's own SVG renderer to escape all user-supplied text content (a property to explicitly re-verify during planning, not assume), and by this platform's existing Content-Security-Policy (`object-src 'none'`, restrictive `frame-ancestors`/`frame-src`) already applied platform-wide, which independently constrains what an injected payload could do even if escaping had a gap.
- A user attempts to reach another user's or another organization's diagrams by guessing/enumerating IDs → mitigated by reusing ADP's existing RBAC/session model exactly as every other content type does; no new authorization mechanism is introduced for this feature to get wrong.

**Residual risk**: the same class of risk this platform already accepts for any user-generated content that gets rendered back to other viewers (e.g., knowledge item descriptions, application notes) — mitigated by relying on a well-tested reused renderer plus the platform's existing CSP, not a bespoke sanitizer built for this feature alone.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An architect creates a non-C4 diagram to document something C4 can't express (Priority: P1)

An Enterprise or Business Architect needs to document something outside C4's vocabulary — a business-process flowchart, a data-architecture ER diagram — that today has no home in ADP at all. They start a new diagram, pick its type, author it interactively, and save it so it exists as a real, retrievable ADP artifact instead of a file on their own machine.

**Why this priority**: this is the entire reason this feature exists — closing the gap where ADP's own stated scope (Enterprise/Business Architecture, not just C4 Solution Architecture) has no representation for the diagram types that scope actually requires.

**Independent Test**: can be fully tested by creating a new diagram of each of the five supported types, saving it, and confirming it persists and can be reopened with its content intact.

**Acceptance Scenarios**:

1. **Given** an architect wants to document a business process, **When** they create a new flowchart diagram and author its content, **Then** the diagram saves and is retrievable later with the same content.
2. **Given** a saved diagram, **When** the architect reopens it, **Then** they see exactly what they last saved, ready to continue editing.
3. **Given** any of the five supported diagram types (flowchart, sequence, ER, UML, cloud-architecture), **When** an architect creates one, **Then** the system supports it the same way it supports the others — no type is a second-class citizen.

---

### User Story 2 - An architect renders a diagram to share or embed (Priority: P2)

Having authored a diagram, an architect wants a static rendering of it (e.g., to paste into a document or present to stakeholders) — not just an editable, in-app view.

**Why this priority**: authoring alone has limited standalone value; the ability to produce a shareable rendering is what makes a diagram useful outside the editing session that created it.

**Independent Test**: can be fully tested by creating a diagram, requesting a render, and confirming the output is a valid, visually correct static image of that diagram's current content.

**Acceptance Scenarios**:

1. **Given** a saved diagram, **When** the architect requests a rendering, **Then** they receive a static image (at minimum SVG) that visually matches the diagram's current content.
2. **Given** a diagram is edited and saved again, **When** it's rendered afterward, **Then** the new rendering reflects the updated content, not a stale cached version.

---

### User Story 3 - An architect finds a previously created diagram (Priority: P3)

An architect (or a teammate with appropriate access) wants to locate a diagram created earlier — by themselves or someone else — without needing to remember exactly where they left it.

**Why this priority**: without a way to browse/find existing diagrams, each one is only ever useful to the person who happens to still have it open — a real but lower-priority gap than authoring/rendering themselves.

**Independent Test**: can be fully tested by creating several diagrams of different types, then confirming they all appear in a listing and can each be reopened from it.

**Acceptance Scenarios**:

1. **Given** several diagrams of different types exist, **When** an architect views the diagram listing, **Then** they see all of them with enough information (title, type, last-updated) to identify the one they want.
2. **Given** a diagram in the listing, **When** the architect selects it, **Then** it opens in the editor with its saved content.

---

### Edge Cases

- What happens when a diagram's DSL source fails to parse (a syntax error introduced during editing)? The system MUST surface a clear validation error and MUST NOT silently save invalid, unparseable content as if it were valid.
- What happens when two people edit the same diagram at the same time? Out of scope to solve with real-time collaboration in v1 (see Assumptions) — a last-write-wins save is acceptable, but the system MUST NOT corrupt or partially overwrite content on a concurrent save.
- What happens to a brand-new diagram before any content has been authored? It MUST be creatable and save-able in a valid empty/starter state, not require content to exist before it can be saved at all.
- What happens when a diagram references a name that also happens to be an ADP element/application/capability name (e.g., a sequence diagram actor named the same as a real ADP application)? No referential link is implied or enforced — these diagrams are free-text authored content, not bound to ADP's own model (see Clarifications).

## Clarifications

### Session 2026-08-06

- Q: Are these new diagrams attached to an existing ADP Design (part of an EA deliverable, with some relationship to Requirements/traceability), or fully standalone artifacts a user creates independent of any design? → **A: Standalone, top-level artifacts in v1 — no relationship to any Design.** Chosen specifically because it's the lower-risk path to a *future* optional-attachment model (Option C): v1 requires no Design-deletion cascade policy and no Design-scoped listing UX, both of which a "start attached" choice would force immediately and a later optional-attachment migration would then have to retrofit. A future `design_id` (nullable) column is a clean additive migration on top of this — existing diagrams need no reinterpretation, they simply have no Design.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support creating a new diagram of each of five types: flowchart, sequence, entity-relationship, UML, and cloud-architecture.
- **FR-002**: System MUST let a user author a diagram's content interactively (not only as raw text entry), reusing the sibling project's existing React-based canvas editor rather than building a new one.
- **FR-003**: System MUST persist a diagram's DSL source text as its authoritative content, independent of and with no coupling to `ArchitectureDescription`, the C4 React Flow canvas, or the existing `adp.renderer` (Structurizr DSL/SVG/PNG) pipeline.
- **FR-004**: System MUST render a diagram's current content to at least SVG on demand, reusing the sibling project's existing renderer rather than building a new one.
- **FR-005**: System MUST validate a diagram's DSL source and surface a clear error on invalid/unparseable content rather than saving it silently as if valid.
- **FR-006**: System MUST let a user list/browse diagrams they have access to, showing at minimum title, type, and last-updated time, and reopen any one into the editor with its saved content.
- **FR-007**: System MUST let a user delete a diagram they have access to.
- **FR-008**: System MUST reuse ADP's existing role-based access control for who can create/edit/view these diagrams — no new permission model is introduced for this feature.
- **FR-009**: System MUST NOT enforce the reused library's own admin-defined Standards system, or any other content-governance/compliance check, against these diagrams in this iteration — creation and saving MUST NOT be blocked on any such check.
- **FR-010**: System MUST NOT provide any AI/chat-assistant capability for these diagram types in this iteration.
- **FR-011**: System MUST treat each diagram as a standalone, top-level artifact with no relationship to any ADP Design in this iteration — FR-006's listing is global/organization-wide (per the user's access), not scoped per-Design, and a Design's deletion has no effect on any diagram (there is no link between them to cascade or orphan).

### Key Entities *(include if feature involves data)*

- **Non-C4 Diagram** *(new entity)*: one user-authored diagram of one of the five supported types. Carries an identity, a title, its type, its DSL source text (the authoritative content), and standard creation/update timestamps. Exists independently of `ArchitectureDescription` — this feature introduces no field, relationship, or reference on the existing canonical model. Carries no reference to any ADP Design in this iteration (FR-011) — a standalone, top-level artifact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can go from "no diagram exists" to "a saved, reopenable diagram" for any of the five supported types, entirely within ADP, with no external tool required.
- **SC-002**: 100% of the five supported diagram types produce a visually correct static rendering (at minimum SVG) from valid content.
- **SC-003**: The existing C4 workspace, `ArchitectureDescription` model, and `adp.renderer` export pipeline show zero behavioral change after this feature ships — a full run of the existing C4-related test suite passes unmodified.
- **SC-004**: A user can locate and reopen a diagram they or a teammate created earlier without needing direct database or API access.

## Assumptions

- **No AI/chat-assistant integration for these diagram types in v1.** The reused library's own AI tool-calling system is wired to its own provider configuration and tool surface, distinct from ADP's LangGraph intake/recommendation/validation pipeline — integrating the two is a separate, later decision, not part of this feature.
- **No change whatsoever to ADP's existing C4 workspace, `ArchitectureDescription` model, or `adp.renderer` pipeline.** These new diagram types have no representation in any of the three today, so there is nothing to reconcile or migrate — they are purely additive, living alongside the existing C4 pipeline.
- **No governance/Standards enforcement on these new diagram types in v1** — explicitly deferred rather than attempting to reconcile ADP's own RBAC-based governance with the reused library's separate, admin-defined Standards system, which was built for a different product's needs. This is a recorded, deliberate scope decision for this iteration, not an oversight; reconciling the two governance mechanisms (if ever needed) is a distinct future decision.
- **No linking into ADP's traceability/audit/verdict system in v1** (the requirement→element→recommendation→verdict thread, or the append-only audit trail) — a stretch goal for a later iteration, not this one. Ordinary `created_at`/`updated_at` timestamps are sufficient for now.
- **RBAC is reused as-is, not extended.** Whichever existing ADP roles can already create/edit content (Enterprise/Solution/Technical Architect) can create/edit these diagrams; Reviewer retains view-only access, consistent with its existing meaning elsewhere in ADP. No new role or permission is introduced.
- **No real-time multi-user collaborative editing in v1** — a diagram is edited by one person at a time in practice; the system only needs to avoid corrupting content on a same-diagram save race, not merge concurrent edits.
- **Export formats mirror what the reused renderer already supports.** SVG is the confirmed minimum; whether PNG or other formats come along for free is a planning-phase detail, not a v1 requirement to gate on.
- **The standalone-only model (FR-011) is a deliberate stepping stone, not a permanent architectural bet.** A future "optionally attach a diagram to a Design" capability is expected to be a clean additive migration (a nullable `design_id` column) on top of this iteration's data — existing diagrams need no reinterpretation when that ships, they simply have no Design. This shaped the choice between standalone-first and attached-first for v1 (see Clarifications).
