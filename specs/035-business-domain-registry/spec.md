# Feature Specification: Business Domain Registry and Stage-Capability Mapping

**Feature Branch**: `035-business-domain-registry`
**Created**: 2026-07-10
**Status**: Draft

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies; this spec precedes planning and implementation.
- **ART-IV** — Test-Driven Development: unit tests for Pydantic models and store functions; integration tests for all new endpoints.
- **ART-V** — Security by Design: domain classification and compliance flags (PII, GDPR, etc.) are sensitive organizational metadata — same auth posture as all other business endpoints applies.
- **ART-IX** — Provenance and Auditability: domain and link mutations emit structured `logger.info()` (same pattern as ADP-SPEC-033/034; ART-IX is SHOULD for business entities with no `design_id` FK).
- **ART-XI** — Traceability End to End: stage-to-capability links are the first explicit bridge between value streams and the capability map; this is a foundational traceability edge in the business architecture.
- **ART-XIII** — Typed Contracts Everywhere: all new request/response shapes defined as Pydantic v2 models with `extra="forbid"`; TypeScript interfaces in `web/src/api/business.ts`.
- **ART-XV** — Schema Evolution is Governed: new Alembic migration 009 with `down_revision = "008"`.

## Threat Model

**Assets at risk**: Business domain metadata — including compliance classification flags such as PII, GDPR, CIFIUS — is sensitive organizational context. The capability-to-domain assignment and stage-to-capability maps reveal which systems touch regulated data and which capabilities are load-bearing for critical value streams.

**Trust boundaries crossed**: Browser → FastAPI only. No new external integrations.

**Abuse cases**:
- Unauthorized enumeration of domain compliance flags reveals the org's regulatory exposure map → Mitigation: existing `AuthMiddleware` gates all `/api/v1/business/*` reads; no additional change required for v1.
- Mass deletion of domain assignments corrupts the capability ownership map → Mitigation: delete of a domain sets `domain_id = null` on its L1 caps (soft disassociation), not cascade delete of capabilities.

**Residual risk**: Low. This feature adds metadata and linking; it introduces no AI outputs, file uploads, or external integrations.

## User Scenarios & Testing

### User Story 1 — Domain Registry CRUD (Priority: P1)

An enterprise architect wants to define the business domains that partition the capability map — naming each domain, writing a scope boundary statement, classifying it as strategic/differentiating/commodity, assigning an org unit, and tagging compliance obligations. They need to create, view, edit, and delete domains independently of the capability hierarchy.

**Why this priority**: Domains are the prerequisite for capability-domain assignment and any future cross-domain analysis. Nothing else in this spec is meaningful without domains existing first.

**Independent Test**: Create three domains with different classifications, retrieve the list, update the scope statement on one, delete another — all verified via API and in the domain list UI.

**Acceptance Scenarios**:

1. **Given** no domains exist, **When** an architect POSTs a domain with name, classification `strategic`, org_unit `Enterprise Architecture`, and risk_flags `["PII","GDPR"]`, **Then** the API returns 201 with the domain including all fields and a generated ID.
2. **Given** a domain exists, **When** the architect PUTs an updated scope statement, **Then** the API returns 200 with the updated domain.
3. **Given** a domain has L1 capabilities assigned to it, **When** the architect deletes the domain, **Then** the domain row is removed and its L1 capabilities remain intact with `domain_id` set to null.
4. **Given** a domain exists, **When** the architect GETs the domain detail, **Then** the response includes all domain fields and a list of its currently assigned L1 capabilities.
5. **Given** two domains with different classifications exist, **When** the architect lists all domains, **Then** both appear ordered by name with their L1 capability counts.

---

### User Story 2 — Assign L1 Capabilities to a Domain (Priority: P2)

An enterprise architect wants to assign L1 business capabilities to domains, establishing ownership boundaries across the capability map. Each L1 can belong to at most one domain; reassigning it to a new domain implicitly removes it from the previous one.

**Why this priority**: The domain-capability assignment is the structural link that gives domains meaning. It enables ownership queries ("who owns Billing?") and is the data foundation for future heat-map and portfolio analysis.

**Independent Test**: Create a domain, assign two L1 capabilities to it, verify the domain detail shows both, reassign one to a second domain, verify each domain's capability list is correct, then clear the assignment on the remaining one and verify the domain has no capabilities.

**Acceptance Scenarios**:

1. **Given** a domain and an L1 capability with no domain, **When** the architect assigns the capability to the domain, **Then** `GET /api/v1/business/domains/{id}` includes that capability in its list.
2. **Given** an L1 capability assigned to Domain A, **When** the architect assigns it to Domain B, **Then** Domain A's list no longer includes it and Domain B's list does.
3. **Given** an L2 or L3 capability, **When** the architect attempts to assign it to a domain, **Then** the API returns 422 with a message that only L1 capabilities can be domain members.
4. **Given** an L1 capability with a domain assignment, **When** the architect clears the assignment, **Then** the capability appears in no domain's list and `domain_id` is null.
5. **Given** an L1 capability assigned to a domain, **When** the capability tree is rendered, **Then** the L1 node displays its domain name as a badge or label.

---

### User Story 3 — Stage-to-Capability Mapping (Priority: P3)

A business architect mapping the Order-to-Cash value stream wants to record which business capabilities enable each stage — e.g., the "Fulfil Order" stage draws on "Fulfilment" and "Inventory Management" capabilities. This many-to-many mapping is the horizontal-thread-through-vertical-blocks link that makes the value stream model analytically useful.

**Why this priority**: Highest analytical value in the feature, but depends on value streams with stages and capabilities existing. Can be fully tested independently once those exist.

**Independent Test**: Create a value stream with two stages and two capabilities; link one capability to each stage; GET each stage's capability list; remove one link; verify it is gone — all via API, no UI dependency for correctness.

**Acceptance Scenarios**:

1. **Given** a value stream stage and a business capability, **When** the architect POSTs a link, **Then** `GET /api/v1/business/value-streams/{vs_id}/stages/{stage_id}/capabilities` returns the linked capability.
2. **Given** a stage with two capabilities linked, **When** the architect removes one, **Then** the GET returns only the remaining capability.
3. **Given** a capability already linked to a stage, **When** a second POST for the same pair is made, **Then** the API returns 409 Conflict.
4. **Given** a stage with capabilities linked, **When** the stage is deleted, **Then** all stage-capability links for that stage are removed (CASCADE).
5. **Given** a capability linked to stages across two different value streams, **When** the capability is deleted, **Then** all its stage-capability links are removed (CASCADE).
6. **Given** a stage with linked capabilities, **When** the stage editor is opened in the UI, **Then** each linked capability is visible with name and level; the architect can remove any link and add new ones from a capability picker.

---

### Edge Cases

- Domain deleted with L1 capabilities assigned: capabilities remain; `domain_id` set to null (no cascade delete of capabilities).
- L1 capability deleted while assigned to a domain: capability row removed; domain's capability count decreases naturally.
- L1 capability deleted while it has stage-capability links: all stage-capability links CASCADE deleted.
- Architect assigns a capability to a non-existent domain: 404 returned.
- `risk_flags` containing empty strings: 422 validation error; blank entries rejected.
- `classification` absent or an invalid value: 422 validation error.
- Domain name collision: no uniqueness constraint in v1 (two domains can share a name); architects are responsible for disambiguation. This is consistent with the capability model.
- Stage-capability link where the stage and capability belong to entirely unrelated constructs: permitted — the mapping is intentionally unconstrained so that any capability can be linked to any stage.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST allow architects to create business domains with: name (required, non-blank), scope_statement (optional text), classification (required; one of `strategic`, `differentiating`, `commodity`), org_unit (optional text), risk_flags (optional text array; defaults to empty).
- **FR-002**: The system MUST support full CRUD for business domains (create, read list, read detail, update, delete).
- **FR-003**: The domain list endpoint MUST return all domains ordered by name, each including its L1 capability count.
- **FR-004**: The domain detail endpoint MUST return the full attribute set plus the list of its assigned L1 capabilities (id, name, level).
- **FR-005**: The system MUST allow an L1 capability to be assigned to a domain; the assignment MUST replace any prior domain assignment for that capability.
- **FR-006**: The system MUST allow an L1 capability's domain assignment to be explicitly cleared (set to none).
- **FR-007**: The system MUST reject domain assignment for L2 or L3 capabilities with a 422 error.
- **FR-008**: Deleting a domain MUST set `domain_id = null` on all its L1 capabilities; it MUST NOT delete the capabilities.
- **FR-009**: The system MUST allow architects to link a business capability to a value stream stage (many-to-many, no additional attributes on the link).
- **FR-010**: The system MUST allow architects to remove a stage-capability link.
- **FR-011**: Linking the same capability to the same stage twice MUST return 409 Conflict.
- **FR-012**: Deleting a value stream stage MUST CASCADE delete its stage-capability links.
- **FR-013**: Deleting a business capability MUST CASCADE delete its stage-capability links.
- **FR-014**: The system MUST expose a list endpoint returning all capabilities linked to a given stage.
- **FR-015**: The capability tree UI MUST display the domain name on each L1 capability that has a domain assignment.
- **FR-016**: The domain list and detail views MUST be accessible from the Business page in the existing navigation.
- **FR-017**: The value stream stage editor UI MUST show capabilities linked to each stage and allow the architect to add or remove links.

### Key Entities

- **BusinessDomain**: A named, classified grouping of L1 business capabilities. Attributes: id, name, scope_statement (text, nullable), classification (strategic|differentiating|commodity), org_unit (text, nullable), risk_flags (text array, default empty), created_at, updated_at. Cardinality: one domain → many L1 capabilities; each L1 capability → at most one domain.
- **BusinessCapability** (extended): Gains a nullable `domain_id` foreign key referencing `business_domains.id`. Setting this FK to null removes the capability from its domain. The constraint is enforced at the API layer: only `level = 1` capabilities may have a non-null `domain_id`.
- **StageCap link**: A join between `value_stream_stages.id` and `business_capabilities.id`. Composite primary key `(stage_id, capability_id)`. No additional attributes. Both FK legs use `ON DELETE CASCADE`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: An architect can register a domain, classify it, add compliance flags, and assign L1 capabilities to it without reading documentation — all operations discoverable from the Business page.
- **SC-002**: All domain CRUD and assignment operations complete under 500 ms at p99 under normal single-user load.
- **SC-003**: Stage-capability links are fully round-trippable via API alone: POST link → GET confirms presence → DELETE → GET confirms empty — no UI dependency for data-layer correctness.
- **SC-004**: Deleting a domain or a capability leaves no orphaned foreign key references; verified by integration tests that inspect DB state post-deletion.
- **SC-005**: The capability tree correctly reflects domain assignment for all L1 nodes without a full page reload after an assignment change.

## Assumptions

- Domain classification is fixed at three values: `strategic`, `differentiating`, `commodity`. Extension requires a migration and a spec amendment.
- Risk flags are stored as `TEXT[]` with no server-side enum validation in v1; documented conventions (PII, GDPR, EU_AI_Act, CIFIUS, SOX, HIPAA) are advisory, not enforced by the schema.
- Only L1 capabilities participate directly in domain membership. L2 and L3 capabilities inherit domain context through their parent L1, not through direct assignment.
- The overview / landing page that aggregates domain metrics and capability heat maps is explicitly out of scope; it will be addressed in a future spec. The backend API designed here MUST be queryable enough to support that future spec without modification to existing endpoints.
- The `adp.business` module is extended in place; no new top-level module is introduced.
- Frontend components live in `web/src/business/` and are extended or added there; the business module API is the single integration boundary so a future landing page spec can introduce a new view without modifying existing component internals.
