# Feature Specification: C4 Visual Design Workspace

**Feature Branch**: `009-c4-workspace`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-009 — C4 Visual Design Workspace"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — The Model is the Single Source of Truth: the central article this spec implements; the canvas is a view over the canonical model — every element placed and every relationship drawn MUST produce a typed record in the canonical model; there is no separate diagram store
- **ART-III** — Everything is Machine-Readable: every canvas mutation produces a typed `Element` or `Relationship` in the canonical model; diagram layout (2D coordinates) is a separate, disposable UI concern and does not override the model
- **ART-IV** — Test-Driven Development: always applies; every canvas interaction that mutates the model requires a test
- **ART-V** — Security by Design: in scope; the canvas operates within ADP-SPEC-004's authorization model; architects only edit designs they have permission to write; the canvas MUST NOT allow style overrides that bypass ART-XII
- **ART-XI** — Traceability End to End: in scope; the workspace MUST surface each element's satisfied requirements and provenance when inspected (FR-005)
- **ART-XII** — Fixed Visual Language: the primary design constraint on this spec; element styling derives exclusively from element type via the locked theme (ADP-SPEC-010); the UI MUST NOT expose any per-diagram or per-element style controls (FR-004 / QG-17)
- **ART-XIII** — Typed Contracts Everywhere: every mutation the canvas sends to the Platform API must be a typed, schema-valid request

## Threat Model *(mandatory — ART-V)*

The visual workspace is a client-facing surface that mutates sensitive architectural design data. Risk is moderate.

**Assets at risk**: The canonical design model (could be corrupted by invalid mutations or unauthorized edits); the locked theme (could be bypassed to produce non-standard diagrams).

**Trust boundaries crossed**: Architect's browser → Platform API (ADP-SPEC-003) → canonical model store (ADP-SPEC-002).

**Abuse cases**:
- **Unauthorized canvas edit**: An architect without write permission submits a canvas mutation → Mitigation: all mutations go through ADP-SPEC-003, which enforces ADP-SPEC-004's persona-based authorization before writing
- **Schema-invalid canvas mutation**: An architect drags an element to create an invalid relationship → Mitigation: FR-006 (schema validation before commit); the API rejects invalid mutations with a typed error; the canvas rolls back the visual action
- **Theme override**: A user discovers a way to apply custom styles → Mitigation: FR-004 enforces that the UI exposes no styling controls; the theme is applied server-side per element type, not client-side per diagram

**Residual risk**: Browser-side rendering bugs that could display incorrect styling without corrupting the model — accepted; the model remains authoritative even if a rendering bug exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a Design on the C4 Canvas (Priority: P1)

An architect opens their design in the workspace and begins modeling it — placing elements (systems, containers, or components depending on their C4 level) and drawing relationships between them. Each action persists immediately to the canonical model through the Platform API. The architect can see the design taking shape as they work.

**Why this priority**: Canvas editing is the primary reason the workspace exists. All other stories build on a working canvas.

**Independent Test**: Place one element and draw one relationship; assert that a typed `Element` and `Relationship` record now exist in the model; assert both are schema-valid; assert neither was committed without going through the API.

**Acceptance Scenarios**:

1. **Given** an architect is editing a design, **When** they place an element on the canvas at their C4 level, **Then** a typed `Element` record (with the correct kind, name, and level) is immediately written to the canonical model via the Platform API; the canvas reflects the placed element visually
2. **Given** two elements exist on the canvas, **When** the architect draws a relationship between them, **Then** a typed `Relationship` record is written to the model with the correct `source` and `target` element ids; the relationship line appears on the canvas
3. **Given** an architect submits a canvas mutation that would violate the schema, **When** the API rejects it, **Then** the canvas visually rolls back the action and displays a clear error; no invalid record is written to the model

---

### User Story 2 - View the Same Design at Different C4 Levels (Priority: P1)

An architect who has built a context-level view wants to drill into a system and see it at the container level — without redrawing anything. The same canonical model is projected to the requested C4 level, showing the appropriate elements and relationships.

**Why this priority**: Model-backed multi-level projection is the core differentiator. Without it, architects would maintain separate diagrams per level and drift would be inevitable (violating ART-II).

**Independent Test**: Create a design with context-level and container-level elements in the same canonical model; switch the workspace to container level; assert that only container-level elements are shown; assert no separate diagram source was used.

**Acceptance Scenarios**:

1. **Given** a design contains elements at multiple C4 levels, **When** the architect switches the workspace to a different C4 level, **Then** the canvas projection immediately shows the elements and relationships appropriate to that level, derived from the same canonical model
2. **Given** an architect adds an element at one C4 level, **When** they switch to another level, **Then** the newly added element is visible at its level without the architect having to redraw it
3. **Given** the same model viewed at two different C4 levels, **When** both projections are inspected, **Then** the data underlying both derives from the same canonical model version — zero drift between the views

---

### User Story 3 - Inspect an Element's Traceability (Priority: P2)

An architect clicks on an element in the canvas and sees a panel showing which requirements the element satisfies and where it came from (its provenance — whether it was manually placed or accepted from an AI recommendation).

**Why this priority**: Traceability surfacing is the ART-XI implementation for the visual workspace. Builds on US1 (elements must exist to inspect).

**Independent Test**: Place an element with known `satisfies` links and `provenance`; click it in the canvas; assert the inspection panel shows the correct requirements and provenance data.

**Acceptance Scenarios**:

1. **Given** an element on the canvas with a non-empty `satisfies` list, **When** the architect clicks it, **Then** an inspection panel shows the requirement ids (and their titles) that this element satisfies
2. **Given** an element with a `provenance` value, **When** inspected, **Then** the panel shows where the element originated — whether it was manually placed or accepted from an AI recommendation (with the recommendation option id)
3. **Given** an element with an empty `satisfies` list, **When** inspected, **Then** the panel indicates that no requirements are currently satisfied (not an error — this is actionable information for the architect)

---

### User Story 4 - Consistent Styling via the Locked Theme (Priority: P2)

Every element on the canvas is styled according to its C4 type (person, system, container, component) using the locked organizational theme. No architect can change the visual appearance of an individual element or diagram — visual consistency is a platform guarantee, not a per-user preference.

**Why this priority**: ART-XII and QG-17 require this. Builds on US1 (elements must be rendered). The absence of style controls simplifies the UI significantly.

**Independent Test**: Create two elements of the same type in two different designs; assert their visual appearance (color, shape, border) is identical; assert the UI exposes no style controls for either element.

**Acceptance Scenarios**:

1. **Given** an element of type `container` on the canvas, **When** it is rendered, **Then** its appearance (color, shape, font, border) exactly matches the organizational theme's definition for `container` — regardless of which design or architect placed it
2. **Given** the canvas is inspected for styling controls, **When** the architect views the element's properties panel, **Then** no color picker, border selector, font control, or other visual style control is present
3. **Given** the locked theme is updated in ADP-SPEC-010, **When** the workspace renders the diagram, **Then** all elements automatically reflect the updated theme without the architect taking any action

---

### Edge Cases

- What happens when the Platform API is unreachable at the moment a canvas mutation is submitted?
- How does the workspace behave when another user edits the same design simultaneously?
- What happens when an architect tries to place an element type that is not valid at the current C4 level?
- How does the canvas handle a design with a very large number of elements (e.g., hundreds)?
- What happens when the canonical model is updated externally (e.g., by the recommendation engine) while the architect has the design open?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workspace canvas MUST support designing at three C4 levels: context (for enterprise architects), container (for solution architects), and component (for technical architects); the active level is visible to the architect and can be switched at any time
- **FR-002**: Every element placement, element update, and relationship creation on the canvas MUST produce a corresponding typed model mutation through the Platform API (ADP-SPEC-003); no diagram state may exist that is not reflected in the canonical model
- **FR-003**: The workspace MUST project the canonical model to any of the three C4 levels without requiring the architect to maintain separate diagram sources; switching levels re-derives the view from the same model
- **FR-004**: Element visual styling (color, shape, icon, border, font) MUST derive exclusively from the element's C4 type via the locked organizational theme (ADP-SPEC-010); the workspace MUST NOT expose any per-element, per-diagram, or per-architect style override controls
- **FR-005**: When an architect selects any element, the workspace MUST display an inspection panel showing: the element's satisfied requirement ids and titles, and the element's provenance (manually placed vs. accepted from a recommendation, with the source reference)
- **FR-006**: The workspace MUST validate every canvas mutation against the canonical schema before committing it to the API; schema-invalid mutations MUST result in a visual rollback and a descriptive error message to the architect

### Non-Functional Requirements

- **NFR-001**: All canvas interactions (element placement, relationship drawing, level switching) MUST complete within 1 second from user action to visible confirmation; model mutations MUST propagate to the API within 2 seconds under normal network conditions
- **NFR-002**: Concurrent edits from different sessions are handled with optimistic concurrency — the workspace detects a version conflict, notifies the architect, and requires them to reload the latest model state before retrying their edit (last-write-wins in v1)

### Key Entities

- **CanvasView**: The workspace's projection of the canonical model at a specific C4 level; derived on-demand from the model and not stored separately; carries element positions (2D layout coordinates) which are a UI concern separate from the model
- **ElementPlacement**: The 2D canvas position of a specific `Element` instance; stored separately from the canonical `Element` record so that positions can be adjusted without mutating the model; one placement per element per design
- **InspectionPanel**: The UI panel shown when an element is selected; displays `satisfies` links and `provenance` from the canonical `Element` record; read-only from the workspace perspective

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of element placements and relationship drawings result in correctly-typed, schema-valid records in the canonical model; zero canvas mutations are committed without passing schema validation; verified by integration tests
- **SC-002**: Switching between C4 levels shows the same canonical model without requiring architect action beyond the level toggle; verified by viewing the same design at two levels and asserting the same element ids appear appropriately
- **SC-003**: Canvas interactions respond within 1 second and model mutations propagate within 2 seconds under normal conditions; verified by timing tests against the API
- **SC-004**: 100% of rendered elements use styling derived from the locked theme; zero elements rendered with overridden or custom styling; the workspace exposes zero styling controls to architects; verified by UI inspection tests
- **SC-005**: Clicking any element shows its `satisfies` list and `provenance` within 1 second; verified by interaction tests on known designs

## Assumptions

- **Multi-user collaboration (resolved)**: v1 implements single-editor with optimistic concurrency control. If two architects edit the same design simultaneously, ADP-SPEC-002's version-based OCC (optimistic concurrency control) detects the conflict; the second write fails with a conflict error; the workspace notifies the architect and requires them to reload before retrying. Real-time collaborative editing (WebSockets, operational transforms, or CRDT-based sync) is deferred to v2.
- **Canvas layout persistence**: Element 2D positions (x, y coordinates on the canvas) are stored in a separate, lightweight layout record that is not part of the canonical `Element` model. Discarding or regenerating the layout does not affect the canonical model.
- The workspace is a web application (browser-based); native mobile applications are out of scope for v1.
- The workspace is the primary interface for manual design authoring; it does not replace but complements the AI recommendation flow (ADP-SPEC-007), which materializes elements that architects then review and accept in the workspace.
- The workspace consumes the locked theme (ADP-SPEC-010) as a read-only dependency; it does not author or modify the theme.
- Export, rendering to image, and PDF generation are explicitly out of scope (ADP-SPEC-010, ADP-SPEC-011).

## Out of Scope

- Server-side diagram rendering, image export, and PDF generation (ADP-SPEC-010, ADP-SPEC-011)
- Real-time multi-user collaborative editing (deferred to v2)
- Native mobile or desktop application
- The recommendation panel and AI suggestion flow (ADP-SPEC-007 — recommendations materialize elements that appear in the workspace, but the panel logic itself is not part of this spec)
- Custom element types beyond the C4 taxonomy (person, system, container, component)
- Diagram-level styling, themes, or visual customization by architects
