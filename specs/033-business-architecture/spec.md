# Feature Specification: Business Architecture — Capability Model and Value Streams

**Feature Branch**: `033-business-architecture`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "Business Architecture: value streams and 3-level business capability model with CRUD screens"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: applies always
- **ART-II** — The Model is the Single Source of Truth: value streams and capabilities become first-class model entities alongside designs and elements
- **ART-III** — Everything is Machine-Readable: capability hierarchy and value stream data exposed via typed API endpoints
- **ART-IV** — Test-Driven Development: applies always
- **ART-V** — Security by Design: write operations gated by authenticated role; same trust boundary as existing design mutations
- **ART-IX** — Provenance and Auditability: mutations to capability/value-stream data SHOULD be audit-logged
- **ART-XI** — Traceability End to End: capability and value stream data will be consumed by ADP-SPEC-034 to link to solution architecture; this feature establishes the business data layer
- **ART-XIII** — Typed Contracts Everywhere: new API endpoints must have Pydantic request/response models and OpenAPI schemas
- **ART-XV** — Schema Evolution is Governed: new DB tables require Alembic migrations; column changes go through the governed migration process

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Business capability and value stream definitions; traceability links between business and solution architecture.

**Trust boundaries crossed**: Browser → API (CRUD operations); API → PostgreSQL (persistence).

**Abuse cases**:
- Unauthorised edit: attacker modifies capability hierarchy to obscure traceability → Mitigation: same auth middleware as existing design endpoints; write operations require authenticated actor
- Data poisoning: garbage capability names degrade AI recommendation quality → Mitigation: required-field validation at API boundary; names must be non-empty strings

**Residual risk**: Low. No LLM involvement; no external integrations; risk profile matches existing CRUD endpoints for designs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Business Capability Model (Priority: P1)

An Enterprise Architect maintains a three-level business capability hierarchy for the organisation. They create top-level strategic capabilities (e.g. "Customer Engagement"), decompose each into operational capabilities (Level 2), and further into granular capabilities (Level 3). They can edit names and descriptions, reorder capabilities within a level, and delete capabilities that are no longer relevant (with a guard against deletion if child capabilities exist).

**Why this priority**: The capability model is the foundational business vocabulary that all other business architecture work (value streams, traceability) builds on. It can stand alone as a useful directory even before linking to designs.

**Independent Test**: Can be fully tested by creating a three-level hierarchy via the UI, editing a capability at each level, and verifying the tree renders correctly — delivers a complete capability register with no other stories required.

**Acceptance Scenarios**:

1. **Given** an empty capability register, **When** the user creates a Level 1 capability "Customer Engagement", **Then** it appears as a root node in the capability tree
2. **Given** a Level 1 capability exists, **When** the user adds a Level 2 capability "Sales" under it, **Then** "Sales" appears nested under "Customer Engagement"
3. **Given** a Level 2 capability "Sales", **When** the user adds a Level 3 capability "Lead Qualification" under it, **Then** a three-level hierarchy is visible in the tree
4. **Given** a capability with child capabilities, **When** the user tries to delete it, **Then** the system prevents deletion and shows a clear message
5. **Given** a capability with no children, **When** the user deletes it, **Then** it is removed from the hierarchy
6. **Given** any capability, **When** the user edits its name or description, **Then** changes are saved and reflected immediately in the tree

---

### User Story 2 — Value Streams (Priority: P2)

An Enterprise Architect defines and manages value streams — end-to-end sequences of activities that deliver value to a specific customer segment or stakeholder. Each value stream has a name, a description, a target stakeholder, and an ordered list of value-adding stages. The architect can create, edit, reorder stages, and delete value streams.

**Why this priority**: Value streams provide the "why" behind capability groupings and solution designs. They are the second key artefact of business architecture but have no dependency on capabilities being defined first.

**Independent Test**: Can be fully tested by creating a value stream with three stages, reordering a stage, and verifying the ordered list is persisted — delivers a standalone value stream register.

**Acceptance Scenarios**:

1. **Given** no value streams, **When** the user creates "Order to Cash" with stakeholder "Customer", **Then** it appears in the value stream list
2. **Given** a value stream, **When** the user adds stages "Order Capture", "Fulfilment", "Invoicing", **Then** all three stages are saved in order
3. **Given** a value stream with stages, **When** the user edits a stage name, **Then** the updated name is persisted
4. **Given** a value stream, **When** the user deletes it, **Then** it is removed and any traceability links to it are also removed
5. **Given** multiple value streams, **When** the user views the list, **Then** they are displayed in the order they were created

---

### Edge Cases

- What happens when a Level 2 capability is moved under a different Level 1 parent? (Reparenting is out of scope for v1; hierarchy is fixed on creation)
- How does the system handle duplicate capability names at the same level? (Allowed — names are not unique keys; `id` is the identity)
- What happens if a value stream has only one stage and the user tries to delete it? (Allowed — a single-stage value stream is valid)
- What happens when the hierarchy is very large? (Performance expectation: tree renders without pagination for up to 500 total capabilities)

## Requirements *(mandatory)*

### Functional Requirements

**Capability Model**

- **FR-001**: System MUST allow users to create Level 1 (strategic) business capabilities with a name (required) and description (optional)
- **FR-002**: System MUST allow users to create Level 2 capabilities as children of a Level 1 capability
- **FR-003**: System MUST allow users to create Level 3 capabilities as children of a Level 2 capability
- **FR-004**: System MUST prevent creation of capabilities more than 3 levels deep
- **FR-005**: System MUST allow users to edit the name and description of any capability at any level
- **FR-006**: System MUST allow users to delete a capability that has no child capabilities
- **FR-007**: System MUST prevent deletion of a capability that has child capabilities, with a clear explanation
- **FR-008**: System MUST display the full capability hierarchy as an expandable/collapsible tree

**Value Streams**

- **FR-009**: System MUST allow users to create a value stream with a name (required), description (optional), and target stakeholder (optional)
- **FR-010**: System MUST allow users to add ordered stages to a value stream, each with a name and optional description
- **FR-011**: System MUST allow users to edit value stream metadata (name, description, stakeholder)
- **FR-012**: System MUST allow users to add, edit, and remove stages within a value stream
- **FR-013**: System MUST allow users to delete a value stream (cascades to its stages)
- **FR-014**: System MUST display value streams in a list view and a detail view showing all stages in order

### Key Entities

- **BusinessCapability**: A named organisational ability at one of three levels. Has `id`, `name`, `description`, `level` (1–3), `parent_id` (null for Level 1), `position` (ordering within parent).
- **ValueStream**: An end-to-end activity sequence delivering value to a stakeholder. Has `id`, `name`, `description`, `stakeholder`, `position`.
- **ValueStreamStage**: An ordered step within a value stream. Has `id`, `value_stream_id`, `name`, `description`, `position`.
Note: `CapabilityDesignLink` and `ValueStreamDesignLink` join entities are deferred to ADP-SPEC-034 (traceability feature).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can create a complete three-level capability hierarchy of 10 capabilities in under 5 minutes
- **SC-002**: An architect can define a value stream with 5 stages in under 3 minutes
- **SC-003**: The capability tree with up to 500 nodes renders within 2 seconds on first load
- **SC-004**: Deleting a capability with children is blocked with a clear user-facing message; deleting a leaf capability succeeds immediately

## Assumptions

- Reparenting capabilities (moving a node to a different parent) is out of scope for v1; hierarchy is fixed on creation
- User roles from ADP's existing auth system apply; write access requires an authenticated user (same gate as design mutations)
- Traceability links between business architecture and solution designs are deferred to ADP-SPEC-034; this feature establishes the data layer only
- No import format (e.g. ArchiMate, TOGAF) is required for v1 — manual data entry only
- Business architecture will appear as a new top-level navigation item alongside Knowledge, Designs, etc.
- Value stream stages do not map to specific capabilities in v1 (stage-to-capability mapping is a future enhancement)
- Mobile/responsive layout is not a v1 requirement; desktop browser is the target
