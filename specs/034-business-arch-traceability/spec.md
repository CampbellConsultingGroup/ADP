# Feature Specification: Business Architecture Traceability

**Feature Branch**: `034-business-arch-traceability`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "Link capabilities and value streams to solution architecture designs, completing the chain from business intent to technical implementation"
**Depends on**: ADP-SPEC-033 (capability model and value streams must exist)

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: applies always
- **ART-IV** — Test-Driven Development: applies always
- **ART-V** — Security by Design: link creation/deletion gated by authenticated user; same trust boundary as existing design mutations
- **ART-IX** — Provenance and Auditability: traceability link mutations SHOULD be audit-logged so there is a record of when a design was associated with a business capability
- **ART-XI** — Traceability End to End: this feature is the direct realisation of ART-XI — it creates the navigable chain from business capability → value stream → solution design → architecture elements
- **ART-XIII** — Typed Contracts Everywhere: link endpoints must have Pydantic request/response models and OpenAPI schemas
- **ART-XV** — Schema Evolution is Governed: two new join tables (`capability_design_links`, `value_stream_design_links`) require governed Alembic migrations

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Traceability links between business architecture and solution designs; integrity of the architecture record.

**Trust boundaries crossed**: Browser → API (link creation/deletion); API → PostgreSQL (persistence).

**Abuse cases**:
- Unauthorised link creation: attacker associates a sensitive design with a misleading capability to distort governance reports → Mitigation: authenticated actor required; same auth gate as design mutations
- Orphan reference injection: link created to a non-existent design or capability ID → Mitigation: foreign-key constraint at DB level; 404 returned at API level if either entity is not found

**Residual risk**: Low. No LLM involvement; no external integrations; risk profile is the same as existing relationship CRUD.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Link Designs to Capabilities (Priority: P1)

An Enterprise Architect, while viewing a business capability (e.g. "Order Processing"), searches for and selects one or more existing solution designs that realise that capability. The links are immediately visible on the capability detail page. The architect can also remove a link if a design no longer realises that capability.

**Why this priority**: Capability-to-design is the most direct traceability link and the one most likely to be populated first. It is the anchor for all downstream reporting on coverage and gaps.

**Independent Test**: Can be fully tested by linking two designs to a capability, verifying both appear on the capability detail page, removing one, and confirming only the remaining design shows — requires ADP-SPEC-033 capabilities to exist.

**Acceptance Scenarios**:

1. **Given** a capability "Order Processing" and designs exist in the system, **When** the user selects "Order Management System" to link, **Then** it appears under "Realised by" on the capability detail page
2. **Given** a capability with a linked design, **When** the user removes the link, **Then** the design no longer appears under "Realised by"
3. **Given** a design is linked to a capability, **When** the user views the design, **Then** "Order Processing" is listed in a "Business Context — Capabilities" section
4. **Given** a linked design is deleted from ADP, **When** the user views the capability, **Then** the deleted design is no longer listed (no orphan reference)

---

### User Story 2 — Link Designs to Value Streams (Priority: P2)

An Enterprise Architect, while viewing a value stream (e.g. "Order to Cash"), selects existing solution designs that support that value stream. The links appear on the value stream detail page. The design detail view also shows which value streams it contributes to.

**Why this priority**: Value-stream-to-design links are the second tier of business-to-solution traceability. Depends on US1 patterns being established; follows the same interaction model.

**Independent Test**: Can be fully tested by linking a design to a value stream, verifying the link from both the value stream detail and the design detail views.

**Acceptance Scenarios**:

1. **Given** a value stream "Order to Cash" and a design "Order Management System", **When** the user links the design, **Then** it appears under "Supporting designs" on the value stream detail page
2. **Given** a design linked to a value stream, **When** the user views the design, **Then** "Order to Cash" appears in a "Business Context — Value Streams" section
3. **Given** a linked design is deleted from ADP, **When** the user views the value stream, **Then** no orphan reference to the deleted design appears

---

### User Story 3 — Traceability Explorer (Priority: P3)

An architect can navigate the full traceability chain in both directions: starting from a capability, they can reach the designs that realise it; starting from a design, they can reach the capabilities and value streams it supports. A simple "Business Context" panel on the design detail screen and a "Coverage" section on capability/value-stream pages make this chain visible without requiring a dedicated graph view.

**Why this priority**: This is a read-only navigation enhancement. US1 and US2 already create the data; this story makes it ergonomically useful and is the right capstone before the data starts being consumed by portfolio/governance screens.

**Independent Test**: Can be fully tested by starting from a design detail page, clicking through to a linked capability, and confirming the original design appears in the capability's "Realised by" list — round-trip navigation works.

**Acceptance Scenarios**:

1. **Given** a design linked to both a capability and a value stream, **When** the user views the design detail, **Then** both the capability and value stream are listed in a "Business Context" panel with links to their detail pages
2. **Given** a capability linked to three designs, **When** the user views the capability detail, **Then** all three designs are listed with links to their design detail pages
3. **Given** no links have been created, **When** the user views any capability or design detail, **Then** a clear empty state explains how to add links

---

### Edge Cases

- What if the same design is linked to the same capability twice? (Prevented — the join is unique on `(capability_id, design_id)`; API returns 409 Conflict on duplicate)
- What if a capability is deleted while designs are linked to it? (Cascade: links are removed; design detail's "Business Context" panel no longer lists the deleted capability)
- What if there are hundreds of designs linked to one capability? (List is paginated or truncated at 50 with a "show all" option in v1)

## Requirements *(mandatory)*

### Functional Requirements

**Capability–Design Links**

- **FR-001**: System MUST allow users to link one or more designs to a business capability
- **FR-002**: System MUST prevent duplicate links between the same design and capability (unique constraint)
- **FR-003**: System MUST allow users to remove a capability–design link
- **FR-004**: System MUST display all designs linked to a capability on the capability detail page
- **FR-005**: System MUST remove capability–design links when the referenced design is deleted
- **FR-006**: System MUST remove capability–design links when the referenced capability is deleted

**Value Stream–Design Links**

- **FR-007**: System MUST allow users to link one or more designs to a value stream
- **FR-008**: System MUST prevent duplicate links between the same design and value stream
- **FR-009**: System MUST allow users to remove a value-stream–design link
- **FR-010**: System MUST display all designs linked to a value stream on the value stream detail page
- **FR-011**: System MUST remove value-stream–design links when the referenced design is deleted
- **FR-012**: System MUST remove value-stream–design links when the referenced value stream is deleted

**Reverse Navigation (Design Detail)**

- **FR-013**: System MUST display all capabilities linked to a design in a "Business Context" panel on the design detail view
- **FR-014**: System MUST display all value streams linked to a design in the same "Business Context" panel
- **FR-015**: Each item in the Business Context panel MUST be a navigable link to the capability or value stream detail page

### Key Entities

- **CapabilityDesignLink**: Join entity. Has `capability_id` (FK → business_capabilities), `design_id` (FK → designs). Unique on `(capability_id, design_id)`.
- **ValueStreamDesignLink**: Join entity. Has `value_stream_id` (FK → value_streams), `design_id` (FK → designs). Unique on `(value_stream_id, design_id)`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can link a design to a capability in under 30 seconds from the capability detail page
- **SC-002**: Traceability links are visible from both directions (capability→design and design→capability) without navigating away from the current page
- **SC-003**: Deleting a design removes all its traceability links within the same transaction — no orphan references visible on capability or value stream pages after deletion
- **SC-004**: Duplicate link attempts return a clear error; the existing link is preserved unchanged

## Assumptions

- ADP-SPEC-033 (capability model and value streams) is fully delivered before this feature is built; this spec makes no sense without it
- Element-level traceability (linking a design element, not just the whole design, to a capability) is out of scope for v1
- Stage-level traceability (linking a value stream stage to a specific capability) is out of scope for v1
- Portfolio and governance screens (ADP-SPEC-031, ADP-SPEC-032) will consume the link data in a future iteration — this feature only creates and exposes the links
- The "Business Context" panel on the design detail view is additive — it does not replace any existing design metadata panels
