# Feature Specification: Generate Diagrams from Business Data

**Feature Branch**: `048-generate-diagrams-from-data`
**Created**: 2026-08-11
**Status**: Draft
**Input**: User description: "ADP-914.7: Generate a pre-filled diagram from ADP's own business-capability/value-stream data. Today the 5 standalone diagram types (ADP-SPEC-046) are entirely hand-authored DSL -- nothing connects them to business_capabilities or value_streams/value_stream_stages. This is a one-way generator (ADP data -> pre-filled DSL a user can then hand-edit), not a live two-way sync."

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: does **not** apply in the sense of introducing a *new* canonical model — `business_capabilities`/`value_streams` remain ADP's existing sources of truth for that data; a generated diagram's own DSL source becomes *that diagram's* authoritative representation the moment it's saved (per ADP-SPEC-046's existing ART-II framing), exactly like any hand-authored diagram. Generation reads from the canonical source once, at generation time — it never becomes a second copy that claims ongoing authority (see FR-008, the one-way/no-sync boundary).
- **ART-III** — Everything is Machine-Readable: applies — closes a real, related gap: today a user visualizing a value stream or capability tree as a diagram must reconstruct it from memory into hand-typed DSL; generation makes that structured data directly expressible as a diagram instead.
- **ART-V** — Security by Design: low-risk — see Threat Model. No new data exposure (reuses existing, already-authorized read endpoints); no new write path (the generated diagram isn't saved until the user explicitly saves, per ADP-SPEC-046's existing create flow).
- **ART-VI** — Observability is Not Optional: does not apply — generation is a client-side read + transform, not a new mutation type; no AI orchestration span needed (ART-VII does not apply).
- **ART-VII, ART-VIII, ART-IX, ART-X, ART-XI** — do not apply: no AI-generated content (deterministic, rule-based generation from structured data, not an LLM), no AI proposal to confirm, nothing new in the audit trail, no validation gating, no traceability thread beyond what ADP-SPEC-046 already established for any diagram.
- **ART-XII** — Fixed Visual Language: does not apply — governs the locked C4 theme specifically; generated flowchart diagrams render via the same non-C4 styling system ADP-SPEC-046 already established as out of C4's scope.
- **ART-XIII** — Typed Contracts Everywhere: applies incidentally — generation is built entirely on the vendored diagram-core's already-typed `DiagramModel`/`addNode`/`addEdge` builders, not ad-hoc string construction; no new API boundary is introduced (reuses existing, already-typed `business.ts` read hooks).
- **ART-XIV, ART-XV** — Reproducible builds / Schema evolution: do not apply — no migration, no schema change, no new dependency.
- **ART-XVI** — Documentation as Code: applies (SHOULD) — a short note in `web/src/diagrams/README.md` on the generator convention, mirroring ADP-SPEC-046's and ADP-914.6's existing documentation pattern.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none beyond what ADP-SPEC-046 and the existing Business Architecture feature (ADP-SPEC-033/034/035) already accept — generation reads data a user is already authorized to view (via existing, unchanged read endpoints) and writes it into a diagram that isn't persisted until the user's own explicit save, gated by the existing `WRITE_DIAGRAM` action exactly like any hand-authored diagram.

**Trust boundaries crossed**: none new — browser → existing `/api/v1/business/*` read endpoints (already-established boundary) → in-browser transform into a `DiagramModel` → existing `POST /api/v1/diagrams` save path (already-established boundary, unchanged). No new backend endpoint, no new server-side code path at all.

**Abuse cases**:
- A user attempts to generate a diagram from a capability or value stream they aren't authorized to read → mitigated entirely by the existing, unchanged authorization on the underlying `/api/v1/business/*` read endpoints; generation has no read path of its own to get wrong.
- A capability or value-stream-stage name containing script-like or malicious markup ends up as a node label in generated DSL, later rendered back to a viewer → mitigated by the same, already-verified `escapeXml()` property in the vendored SVG renderer that ADP-SPEC-046's own threat model already confirmed handles all user-supplied text content, regardless of that text's origin (hand-typed or generated).

**Residual risk**: none beyond what ADP-SPEC-046 and the existing Business Architecture read endpoints already accept. This feature adds no new trust boundary, no new persisted data, and no new attack surface — it recombines two already-authorized read paths into a third, already-authorized write path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a flowchart from a value stream's stages (Priority: P1)

An architect viewing a value stream's detail page (its ordered list of stages) clicks a "Generate Diagram" action. A new, unsaved flowchart diagram opens in the diagram editor, pre-filled with one node per stage (in stage order) connected by sequential edges, titled after the value stream. The architect can immediately review, hand-edit, and save it — or discard it by navigating away, exactly as with any other new, unsaved diagram.

**Why this priority**: This is the single most direct, valuable expression of ADP-914's original ask ("cover the data ADP already collects... value streams") — a value stream's stage sequence maps onto a flowchart almost exactly as a user would draw it by hand, so it's the highest-value, lowest-ambiguity starting point.

**Independent Test**: Open a value stream with at least 2 stages, click "Generate Diagram," and confirm the diagram editor opens with a flowchart containing one node per stage (correctly labeled, in stage order) and sequential edges between consecutive stages — with nothing yet saved to the diagrams list.

**Acceptance Scenarios**:

1. **Given** a value stream with 3 ordered stages ("Intake," "Review," "Approve"), **When** the architect clicks "Generate Diagram" on that value stream's detail page, **Then** a new, unsaved flowchart diagram opens with 3 nodes labeled "Intake," "Review," "Approve" and 2 edges connecting them in that order.
2. **Given** the generated diagram is open and unsaved, **When** the architect edits a node's label or adds a new node, **Then** the edit behaves exactly as it would in any hand-authored diagram — generation only pre-fills the starting content, it does not restrict subsequent editing.
3. **Given** the generated diagram is open and unsaved, **When** the architect clicks "Save," **Then** the diagram is persisted exactly like any other new diagram (via the existing save path), with no ongoing link back to the source value stream.
4. **Given** a value stream with zero stages, **When** the architect clicks "Generate Diagram," **Then** a new, unsaved flowchart diagram opens with zero nodes (an empty flowchart, titled after the value stream) rather than an error — matching ADP-SPEC-046's own precedent that a diagram is creatable before any content exists.

---

### User Story 2 - Generate a flowchart from a capability's subtree (Priority: P2)

An architect viewing a business capability in the capability tree clicks a "Generate Diagram" action on that capability. A new, unsaved flowchart diagram opens, pre-filled with one node for the selected capability and one node for each of its descendant capabilities (its full subtree, following the existing level 1→2→3 hierarchy), connected by parent→child edges, titled after the selected capability.

**Why this priority**: The second half of ADP-914's original ask ("capability models"). Lower priority than User Story 1 because a capability tree is already visually represented today (`CapabilityTree.tsx`) — this generator adds a genuinely new, exportable/editable artifact on top of an already-visible structure, whereas User Story 1's value stream stages have no existing diagram-like visualization at all.

**Independent Test**: Select a level-1 capability with at least one level-2 child (which itself has at least one level-3 child), click "Generate Diagram," and confirm the resulting flowchart contains a node for the selected capability, its child, and its grandchild, connected by parent→child edges — with nothing yet saved.

**Acceptance Scenarios**:

1. **Given** a level-1 capability "Underwriting" with a level-2 child "Risk Assessment" which itself has a level-3 child "Rating Engine," **When** the architect clicks "Generate Diagram" on "Underwriting," **Then** a new, unsaved flowchart diagram opens with 3 nodes ("Underwriting," "Risk Assessment," "Rating Engine") and edges from "Underwriting" → "Risk Assessment" → "Rating Engine".
2. **Given** a leaf capability (level 3, no children), **When** the architect clicks "Generate Diagram" on it, **Then** a new, unsaved flowchart diagram opens with a single node (that capability alone) and zero edges — not an error.
3. **Given** the generated diagram is open, **When** the architect saves it, **Then** it behaves identically to User Story 1's Scenario 3 — persisted as an ordinary new diagram, no ongoing link to the source capability.

---

### Edge Cases

- What happens when the source value stream or capability is deleted *after* a diagram was generated from it but *before* the diagram is saved? → No special handling needed — the generated diagram already exists as in-editor content independent of its source (FR-008); an unsaved editor session is unaffected by changes to data it already read.
- What happens when "Generate Diagram" is clicked by a user without `WRITE_DIAGRAM` (e.g., a Reviewer)? → The action is not available at all, consistent with how "+ New Diagram" is already gated today (ADP-SPEC-046) — no new permission check needed, since saving the generated diagram goes through the exact same, already-gated save path.
- What happens if a capability's subtree is very large (e.g., a level-1 capability with dozens of level-2/3 descendants)? → The generator includes the entire subtree with no size limit for v1 (matching the existing `dsl_source` size cap, ADP-SPEC-046, as the only backstop) — extremely large subtrees producing a visually dense diagram is an accepted usability trade-off for v1, not a blocking concern, since the architect can freely edit/prune after generation.
- What happens to a stage or capability name that would produce a syntactically awkward DSL label (e.g., containing brackets or pipe characters that collide with flowchart DSL delimiters)? → Generation builds a typed `DiagramModel` and serializes it through the existing, already-tested `serializeFlowchart()` function (not hand-written DSL text), so this is already handled by that function's existing label-escaping behavior — no new escaping logic is needed for this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to generate a new flowchart diagram from a value stream's ordered stages, from that value stream's own detail view.
- **FR-002**: The generated value-stream diagram MUST contain exactly one node per stage, labeled with that stage's name, and MUST connect consecutive stages (in their existing stage order) with a directional edge.
- **FR-003**: Users MUST be able to generate a new flowchart diagram from a business capability's subtree (the selected capability plus all of its descendants), from that capability's own view in the capability tree.
- **FR-004**: The generated capability diagram MUST contain exactly one node per capability in the subtree (the selected capability plus every descendant), labeled with that capability's name, and MUST connect each capability to its direct parent with a directional edge.
- **FR-005**: Both generated diagrams MUST be titled using the source entity's name (e.g., a value stream named "Quote to Bind" produces a diagram titled "Quote to Bind").
- **FR-006**: A generated diagram MUST open directly in the diagram editor in an unsaved state — identical in behavior to a manually-started new diagram (ADP-SPEC-046) — requiring an explicit user action to persist it.
- **FR-007**: Users MUST be able to freely edit a generated diagram (add/remove/relabel nodes and edges, change its title) before saving, with no restriction beyond what already applies to any hand-authored diagram.
- **FR-008**: Once generated, a diagram MUST NOT maintain any ongoing link back to its source value stream or capability — no automatic re-sync, no reference stored, no indication in the data model that a diagram was ever generated (a one-way, point-in-time transform only).
- **FR-009**: Generation MUST succeed (producing an empty or single-node diagram, not an error) when the source value stream has zero stages or the source capability has no descendants.
- **FR-010**: "Generate Diagram" MUST only be available to users who already have permission to create diagrams (the existing `WRITE_DIAGRAM` action) — no new permission is introduced for this feature.

### Key Entities

- No new persisted entity. A generated diagram, once saved, is an ordinary `Diagram` record (ADP-SPEC-046) — indistinguishable in storage from a hand-authored one (FR-008: no provenance marker is kept). The "generator" itself is a stateless transform from already-existing read data (`BusinessCapability`, `ValueStreamDetail`/`ValueStreamStage`) into a diagram's starting content, not a new stored concept.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can go from viewing a value stream to having an editable, correctly-sequenced flowchart of its stages in a single action (one click), with zero manual node/edge authoring required to represent the stage sequence itself.
- **SC-002**: An architect can go from viewing a business capability to having an editable flowchart of its full subtree in a single action (one click), with zero manual node/edge authoring required to represent the hierarchy itself.
- **SC-003**: 100% of generated diagrams open in a state the user can immediately save unmodified and have it correctly represent the source structure at that moment — generation never requires the user to fix incorrect content before it's usable.
- **SC-004**: Editing a generated diagram (before or after saving) is indistinguishable in capability from editing a hand-authored one — no feature of the diagram editor is disabled or degraded for generated content.

## Assumptions

- **Exactly two generators for v1, both producing `flowchart`**: value-stream-stages → flowchart, and capability-subtree → flowchart. Other diagram types (ERD, UML, sequence, architecture) or other source-entity combinations (e.g., combining a value stream and its linked capabilities into one diagram) are explicitly deferred to a later iteration — not because they're undesirable, but because these two are the clearest, most directly requested starting point (ADP-914's own wording), and keeping v1 to two independent, simple generators avoids upfront design complexity that isn't yet justified by demand.
- **The `value_stream_stage_capabilities` join data (which capabilities a stage uses) is deliberately excluded from v1's value-stream generator.** Including it (e.g., as sub-nodes under each stage) is a reasonable future enrichment, but was deferred to keep the two v1 generators simple and independent of each other's data — the capability generator already covers capability visualization on its own.
- **Generated diagrams open unsaved, matching ADP-SPEC-046's existing "+ New Diagram" flow exactly.** This was chosen specifically so "regenerate" requires no new concept — clicking "Generate Diagram" again is just starting over, with no update/versioning/conflict-resolution question to design, since nothing was ever auto-persisted in the first place.
- **The "Generate Diagram" entry point lives on the source entity's own existing page** (the value stream's detail view; the capability's node/detail view in the tree) rather than inside the generic diagrams list/creation flow, since the source page is where the user already has one specific entity selected — avoiding the need for a new entity-picker UI inside the diagrams section.
- **No provenance is recorded.** A saved, generated diagram is stored identically to a hand-authored one (FR-008) — deliberately, to keep this a strictly one-way, point-in-time transform rather than the start of a sync relationship the platform would need to maintain going forward.
- **Out of scope** (per the originating request): live two-way sync between a diagram and its source data; AI-assisted generation (tracked separately as ADP-914.8); any change to the `business_capabilities`/`value_streams` data model or their existing APIs; combining multiple source entities into a single generated diagram; generating ERD/UML/sequence/architecture diagrams from this data.
