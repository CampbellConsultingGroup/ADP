# Feature Specification: C4 Diagram Type in the Diagram Tool

**Feature Branch**: `053-c4-diagram-type`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "ADP-914.11: Expose c4 as a selectable standalone DiagramType" — Phase A of the C4Canvas retirement roadmap decided on ADP-914.9. The diagram tool's underlying engine already fully understands standard Mermaid C4 diagram syntax; it is simply never offered to users as a choice today. This feature turns that choice on, independent of and ahead of any later work to replace ADP's separate architecture-design canvas (tracked as ADP-914.12/.13).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-V** — Security by Design: low-risk — see Threat Model. No new data, no new trust boundary; reuses the diagram tool's existing create/edit/delete permission gate for every diagram type.
- **ART-XIII** — Typed Contracts Everywhere: applies narrowly — the diagram type is a typed enumeration; this feature adds one new value to it. Purely additive, no existing value changes meaning or shape.
- **ART-II, ART-III, ART-VI–XII, ART-XIV–XVI** — do not apply beyond the ordinary level: no canonical architecture-design data touched, no AI-generated content, no schema/migration, no new observability surface.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none beyond what's already exposed — this makes an already-fully-built diagram format available as a choice within an existing, already-permission-gated creation flow. No new data is read, written, or displayed that isn't already possible with the diagram tool's other supported formats.

**Trust boundaries crossed**: none — no new API call shape beyond one additional accepted value on an existing field, no new backend endpoint, no new external dependency.

**Abuse cases**: none identified beyond those already accepted for the diagram tool's other formats — the same input-size and content-parsing safeguards already applied to every diagram type's text apply here unchanged.

**Residual risk**: none beyond the ordinary risk of any new format-parsing path (malformed input is rejected with a clear error, not silently misinterpreted) — mitigated by this format's parser already existing and already being exercised by this codebase's own test suite before this feature adds a way to reach it through the product.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and author a new C4 diagram (Priority: P1) 🎯 MVP

An architect who wants to sketch a C4 model (people, systems, containers, components, and how they relate) opens the diagram tool, chooses "C4 Diagram" as the type for a new diagram, and writes it out — either by describing elements and relationships in the diagram's text description, or by placing generic shapes on the canvas and labeling them — seeing a correctly rendered C4-style diagram appear as they go.

**Why this priority**: This is the entire point of the feature — until an architect can pick C4 as a type at all, none of the tool's already-built understanding of C4 diagrams is reachable. Independently valuable and independently testable on its own.

**Independent Test**: Start a new diagram, select the C4 type, describe a person, two systems, and a relationship between them using the diagram's text description; confirm all three elements and the relationship render correctly on the canvas.

**Acceptance Scenarios**:

1. **Given** an architect is creating a new diagram, **When** they choose a diagram type, **Then** "C4 Diagram" appears as one of the available choices, alongside the tool's other diagram types.
2. **Given** an architect has selected the C4 diagram type, **When** the new diagram opens, **Then** it starts empty and ready for authoring, at the top (Context) level of the C4 hierarchy.
3. **Given** an architect describes valid C4 elements and relationships (people, systems, containers, components, and their external/database/queue variants, including elements grouped inside a boundary) in the diagram's text description, **When** the description is applied, **Then** the diagram renders those elements and relationships correctly on the canvas.
4. **Given** an architect's C4 text description contains something the format doesn't recognize, **When** they attempt to apply it, **Then** the diagram tool reports which line and content could not be understood, consistent with how it already reports errors for every other diagram type.

---

### User Story 2 - Save, reopen, and continue a C4 diagram (Priority: P2)

An architect saves a C4 diagram they're working on, leaves the tool, and later reopens it to keep working — expecting it to look and behave exactly as any other saved diagram does: listed by name and type, reopening with its full content intact.

**Why this priority**: Authoring only has lasting value if the work persists correctly; this closes the loop on User Story 1 but is meaningfully separable (a diagram that renders correctly in-session but can't be trusted to reload correctly is not yet usable for real work).

**Independent Test**: Save a C4 diagram containing several elements, navigate away, reopen it from the diagram list, and confirm every element, relationship, and label is exactly as left.

**Acceptance Scenarios**:

1. **Given** an architect has authored a C4 diagram, **When** they save it, **Then** it appears in the diagram list correctly labeled as a C4 diagram, the same way every other diagram type already appears.
2. **Given** a previously saved C4 diagram, **When** an architect reopens it, **Then** its full content (elements, relationships, positions, labels) is restored exactly as it was saved.

---

### User Story 3 - Export a C4 diagram (Priority: P3)

An architect who has finished (or wants to share progress on) a C4 diagram exports it as an image, the same way they already can for any other diagram type in the tool.

**Why this priority**: Valuable, but the diagram is already usable and shareable in-app without it — this rounds out parity with the tool's other diagram types rather than unlocking new core value.

**Independent Test**: With a C4 diagram open, use the export action and confirm an image file is produced showing the diagram's current content.

**Acceptance Scenarios**:

1. **Given** an architect has a C4 diagram open, **When** they choose to export it, **Then** they receive an image file (in either of the formats already offered for other diagram types) depicting the diagram as currently shown.

---

### Edge Cases

- What happens to diagrams created before this feature ships? → Unaffected — this only adds a new choice for diagrams created going forward; no existing diagram's type or content changes.
- What happens if an architect places a generic shape on the canvas (rather than describing it via text) while working on a C4 diagram? → It appears using the tool's existing general-purpose shape set; dedicated one-click "add a Person"/"add a System"/etc. buttons are not part of this pass (see Assumptions) — the full C4 vocabulary remains reachable via the text description either way.
- What happens if an architect wants a Container, Component, Dynamic, or Deployment-level C4 diagram instead of the default Context level? → They describe it starting from that level's heading in the text description; a dedicated level-switching control is not part of this pass (see Assumptions).
- What happens when C4 diagram text uses a construct the format doesn't model visually (e.g. a pure layout hint with no visual equivalent)? → Accepted without error, consistent with how the format's other non-visual hints are already handled; it simply has no visible effect.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to select "C4 Diagram" as a diagram type when creating a new diagram, alongside the tool's other existing diagram types.
- **FR-002**: The system MUST correctly interpret standard C4 diagram text — people, systems, containers, components (including their external/database/queue variants), relationships, and elements nested inside a boundary — rendering it as a visual diagram.
- **FR-003**: The system MUST convert a C4 diagram's visual state back into correctly-formatted C4 text reflecting any changes made directly on the canvas.
- **FR-004**: A newly created C4 diagram MUST start empty and ready for authoring, at the Context level of the C4 hierarchy.
- **FR-005**: C4 diagrams MUST be creatable, listed, reopened, edited, and deleted the same way every other diagram type already is.
- **FR-006**: C4 diagrams MUST support the same image-export capability already available for every other diagram type.
- **FR-007**: When C4 diagram text contains something unrecognized, the system MUST report which line and content could not be interpreted, consistent with how every other diagram type's errors are already reported.
- **FR-008**: This feature MUST NOT change the type, content, or behavior of any diagram created before this feature ships.
- **FR-009**: This feature MUST NOT change how ADP's separate architecture-design records (a distinct concept from standalone diagrams, covering formal, governed system designs) are created, edited, rendered, or exported — that is explicitly out of scope for this feature.

### Key Entities *(include if feature involves data)*

- **Diagram Type**: An existing concept (the tool already supports several) gains one new recognized value, "C4 Diagram" — no new entity, no change to any other existing value's meaning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can create a new C4 diagram, describe at least two elements and one relationship via the diagram's text description, and see them rendered correctly on the canvas within the same session.
- **SC-002**: Every standard C4 diagram construct this format is documented to support (people, systems, containers, components and their external/database/queue variants, relationships, nested boundaries, styling directives) parses without error.
- **SC-003**: A saved C4 diagram reopens with its content indistinguishable from what was saved — zero data loss on save/reload.
- **SC-004**: C4 diagrams appear in the diagram list correctly labeled, with no special-casing visible to the user versus any other diagram type.
- **SC-005**: An architect can export a C4 diagram to an image file using the same action already used for every other diagram type.
- **SC-006**: Zero existing diagrams (created before this feature ships) change in type, content, or appearance as a result of this feature shipping.

## Assumptions

- **No dedicated C4 shape-picker in this pass**: the canvas's one-click "add a shape" buttons continue offering only the general-purpose shapes already available to the tool's non-flowchart diagram types. Dedicated one-click "add a Person"/"add a System"/"add a Container" buttons (with correct C4 styling) are a natural follow-on, not required for this feature to deliver value, since the text description already gives full access to every C4 element type. This trade-off is a scope choice specifically requested for this phase (kept deliberately small and low-risk) — not an oversight.
- **No dedicated C4-level switcher in this pass**: a new C4 diagram starts at the Context level (the top of the C4 hierarchy, and this tool's most common starting point); moving to a Container/Component/Dynamic/Deployment view is done by editing the text description's starting heading directly. A guided level-switching control is a reasonable future enhancement, out of scope here.
- **Export uses this tool's existing general-purpose image export**, identical in kind to what every other diagram type in the tool already uses — this is a separate, distinct capability from ADP's separate governed/fixed visual styling used specifically for formal architecture-design exports elsewhere in the product; the two are unrelated and this feature does not touch the latter.
- **No migration required**: existing diagrams (of any type) are entirely unaffected — this feature only adds a new choice available going forward.
- **This feature is scoped entirely to the standalone diagram tool** and has no relationship to, and makes no change to, ADP's separate concept of formal architecture-design records — a related but distinct part of the product, addressed separately (tracked as ADP-914.12/.13, explicitly out of scope here).
