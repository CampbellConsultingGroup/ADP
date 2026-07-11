# Feature Specification: Application Registry

**Feature Branch**: `036-application-registry`  
**Created**: 2026-07-11  
**Status**: Draft  

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this spec drives implementation
- **ART-IV** — Test-Driven Development: always applies; integration tests precede store and router code
- **ART-V** — Security & Threat Modelling: applies; new first-class entities expose vendor, owner, and TCO data requiring access control
- **ART-VI** — Auditability: applies; create/update/delete of applications and integrations are significant architect decisions that must be auditable
- **ART-IX** — Structured Logging over Raw Audit Entries: applies; mutations logged via `logger.info()` with structured fields, consistent with ADP-SPEC-033/034/035

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Application identity records (names, vendors, owners), TCO/financial metadata, strategic classification (TIME, R-strategy, pace layer), capability fit scores (1–5), health scores (1–5), integration topology (source/target/type).

**Trust boundaries crossed**: Browser → API (all CRUD); API does not cross to any external system in this spec.

**Abuse cases**:
- **Enumeration**: Unauthenticated actor lists all applications to map the IT portfolio → Mitigation: standard ADP auth middleware (ADP-SPEC-003) required on all endpoints
- **Tampering**: Authenticated actor alters another team's application records or TIME classification → Mitigation: write operations logged; future RBAC layer (out of scope here) can gate by owner
- **Score inflation**: Actor sets inflated fit/health scores to steer investment decisions → Mitigation: scores are bounded 1–5 with validation; all mutations are audit-logged
- **Self-integration abuse**: Actor creates an integration from an application to itself → Mitigation: source ≠ target enforced at the API layer (FR-037)

**Residual risk**: No per-application ownership enforcement in v1; any authenticated user can modify any application. Accepted as consistent with the current ADP permission model; ownership enforcement deferred to a future RBAC spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Application Core CRUD (Priority: P1)

An architect registers a new application in the portfolio — giving it a name, optional description, vendor, primary owner, and strategic classification (TIME, R-strategy, pace layer, health score). They can then list, retrieve, update, and delete it.

**Why this priority**: Without a persistent Application entity there is nothing to hang capability links, integrations, or design links on. Every other story depends on this.

**Independent Test**: Create an application via POST, verify it appears in the list, retrieve it by ID, update a field, delete it, confirm 404.

**Acceptance Scenarios**:

1. **Given** an empty registry, **When** an architect POSTs a valid application, **Then** 201 is returned with a UUID `id` and all supplied fields are echoed back
2. **Given** several applications exist, **When** GET /applications is called, **Then** they are returned ordered by name ascending
3. **Given** an existing application, **When** a PATCH is sent with a changed `vendor`, **Then** 200 returns the updated record
4. **Given** an existing application, **When** DELETE is called, **Then** 204 is returned and subsequent GET returns 404
5. **Given** a POST with a blank `name`, **When** submitted, **Then** 422 is returned
6. **Given** a POST with `time_classification = "Spend"`, **When** submitted, **Then** 422 is returned (not a valid TIME value)
7. **Given** a POST with `health_score = 6`, **When** submitted, **Then** 422 is returned (out of range)

---

### User Story 2 - Business Capability Linkage with Fit Score (Priority: P2)

An architect links an application to one or more business capabilities (from ADP-SPEC-033) and records a fit score (1–5) for each link, indicating how well the application supports that capability.

**Why this priority**: Capability coverage is the primary lens for portfolio analysis (ADP-SPEC-037); without fit scores the heat-map view has nothing to colour.

**Independent Test**: Create an application and a business capability, link them with fit_score=3, retrieve the link, update the score to 4, remove the link.

**Acceptance Scenarios**:

1. **Given** an application and a business capability, **When** a link is created with `fit_score=3`, **Then** 201 is returned
2. **Given** the link exists, **When** GET /applications/{id}/capability-links is called, **Then** the capability id, name, and fit_score are returned
3. **Given** a link, **When** PATCH is sent with `fit_score=5`, **Then** 200 returns the updated score
4. **Given** a POST with `fit_score=0`, **When** submitted, **Then** 422 is returned
5. **Given** a POST with `fit_score=6`, **When** submitted, **Then** 422 is returned
6. **Given** a link, **When** DELETE is called, **Then** 204 and the link no longer appears in the list
7. **Given** a duplicate link (same app + same cap), **When** submitted, **Then** 409 is returned

---

### User Story 3 - Technical Capability Hierarchy (Priority: P3)

An architect defines a three-level hierarchy of technical capabilities (e.g., Data Management → Structured Storage → Relational Database). Each level is user-defined; there is no pre-seeded catalog.

**Why this priority**: Technical capabilities are the second dimension of the application registry; they must exist before applications can declare what they provide or consume.

**Independent Test**: Create an L1 technical capability, create an L2 under it, create an L3 under the L2, retrieve the tree, delete L3, verify L1 and L2 survive.

**Acceptance Scenarios**:

1. **Given** no parent, **When** a technical capability with `level=1` is created, **Then** 201 is returned with `parent_id=null`
2. **Given** an L1, **When** an L2 is created with `parent_id=<l1_id>`, **Then** 201 is returned
3. **Given** an L2, **When** an L3 is created with `parent_id=<l2_id>`, **Then** 201 is returned
4. **Given** L3 created under L2, **When** an attempt is made to create an L4 under L3, **Then** 422 is returned (max depth exceeded)
5. **Given** several capabilities, **When** GET /technical-capabilities is called, **Then** the response includes hierarchy information
6. **Given** a capability with children, **When** DELETE is called on it, **Then** 409 is returned (must delete children first)
7. **Given** a leaf capability, **When** DELETE is called, **Then** 204 is returned

---

### User Story 4 - Application–Technical Capability Linkage (Priority: P4)

An architect declares that an application either **provides** or **consumes** a technical capability, building an explicit map of technical dependencies and offerings across the portfolio.

**Why this priority**: Provides/consumes links are the basis for impact analysis and technology rationalisation views in ADP-SPEC-037.

**Independent Test**: Create an application and an L3 technical capability, add a "provides" link, add a "consumes" link on a different technical capability, list both, remove one link.

**Acceptance Scenarios**:

1. **Given** an application and a technical capability, **When** a "provides" link is created, **Then** 201 is returned
2. **Given** an application and a technical capability, **When** a "consumes" link is created, **Then** 201 is returned
3. **Given** links exist, **When** GET /applications/{id}/technical-capability-links is called, **Then** each link includes `usage_type` ("provides" or "consumes") and the capability name
4. **Given** a duplicate link (same app + same tech cap + same usage_type), **When** submitted, **Then** 409 is returned
5. **Given** a link with invalid `usage_type`, **When** submitted, **Then** 422 is returned
6. **Given** a "provides" link, **When** DELETE is called, **Then** 204 is returned

---

### User Story 5 - Value Stream Stage and Domain Linkage (Priority: P5)

An architect links an application to value stream stages it participates in (from ADP-SPEC-033) and to business domains it belongs to (from ADP-SPEC-035), establishing cross-domain relationships with a direction and type.

**Why this priority**: Stage and domain linkages contextualise the application within the business architecture and enable portfolio segmentation.

**Independent Test**: Link an application to a value stream stage, verify the link appears in the stage's application list; link an application to a domain integration with type="primary-support" and direction="inbound".

**Acceptance Scenarios**:

1. **Given** an application and a value stream stage, **When** a stage link is created, **Then** 201 is returned
2. **Given** a duplicate stage link, **When** submitted, **Then** 409 is returned
3. **Given** a stage link, **When** DELETE is called, **Then** 204 is returned
4. **Given** an application and a domain, **When** a domain integration link is created with `type` and `direction`, **Then** 201 is returned
5. **Given** a domain integration link, **When** the linked domain is deleted, **Then** the link is removed (CASCADE)

---

### User Story 6 - Application Integration Registry (Priority: P6)

An architect registers a point-to-point integration between two applications, specifying source, target, integration type (e.g., API, event, file, database), and an optional description. The integration is a first-class entity — not merely a property of either application.

**Why this priority**: Integration topology is a key input to migration planning, risk assessment, and portfolio rationalisation.

**Independent Test**: Create two applications, register an integration from A→B of type "API", retrieve it by ID, list integrations for application A, delete the integration, confirm 404.

**Acceptance Scenarios**:

1. **Given** two applications, **When** an integration is created with source, target, and type, **Then** 201 is returned with a UUID
2. **Given** integrations exist, **When** GET /integrations?app_id={id} is called, **Then** integrations where the app is source or target are returned
3. **Given** an integration, **When** PATCH is sent with a new `description`, **Then** 200 returns the updated record
4. **Given** an attempt to create an integration where source == target, **When** submitted, **Then** 422 is returned
5. **Given** valid type values, **When** an invalid `integration_type` is submitted, **Then** 422 is returned
6. **Given** an integration, **When** DELETE is called, **Then** 204 is returned
7. **Given** A→B and B→A integrations, **When** both are listed, **Then** both are returned (bidirectional circular is permitted)

---

### User Story 7 - Design Linkage (Priority: P7)

An architect links an application to one or more ADP Designs (ADP-SPEC-002), establishing traceability between the application registry and the C4 architecture models.

**Why this priority**: Design linkage closes the loop between the portfolio registry and the architecture authoring tool; it is optional for the core registry to be useful.

**Independent Test**: Create an application and reference a valid design ID, create the link, verify it appears in the application's design list, delete the link.

**Acceptance Scenarios**:

1. **Given** an application and a design ID, **When** a design link is created, **Then** 201 is returned
2. **Given** the link exists, **When** GET /applications/{id}/design-links is called, **Then** the design id appears in the list
3. **Given** a duplicate design link (same app + same design), **When** submitted, **Then** 409 is returned
4. **Given** a design link, **When** DELETE is called, **Then** 204 is returned
5. **Given** a non-existent design ID, **When** a link is created, **Then** 404 is returned

---

### Edge Cases

- Fit score of 0 is rejected (valid range is 1–5 inclusive)
- Fit score of 6 is rejected
- Health score of 0 is rejected; health score of 6 is rejected
- Creating an integration where `source_app_id == target_app_id` is rejected with 422
- A→B integration and B→A integration may coexist (bidirectional is permitted)
- Deleting an application with outstanding capability links, integration links, or design links cascades all child links
- An L3 technical capability cannot become a parent (depth limit enforced)
- Deleting a technical capability that has children is rejected with 409
- Deleting a value stream stage (ADP-SPEC-033) cascades and removes application-stage links
- Deleting a business domain (ADP-SPEC-035) cascades and removes application-domain integration links
- `name` field with only whitespace is rejected with 422 after stripping
- Updating `time_classification` to an invalid value returns 422

## Requirements *(mandatory)*

### Functional Requirements

#### Application Core (FR-001–FR-010)

- **FR-001**: System MUST allow an architect to create an application with: `name` (required, non-blank), `description` (optional), `vendor` (optional free text), `primary_owner` (optional free text), `time_classification` (optional; one of: Tolerate, Invest, Migrate, Eliminate), `r_strategy` (optional; one of: Rehost, Replatform, Repurchase, Refactor, Retire, Retain, Relocate), `pace_layer` (optional; one of: Record, Differentiation, Innovation), `health_score` (optional integer 1–5)
- **FR-002**: System MUST assign a UUID to each application on creation
- **FR-003**: System MUST return 422 if `name` is blank or whitespace-only
- **FR-004**: System MUST return 422 if `time_classification` is not one of the defined values
- **FR-005**: System MUST return 422 if `r_strategy` is not one of the defined values
- **FR-006**: System MUST return 422 if `pace_layer` is not one of the defined values
- **FR-007**: System MUST return 422 if `health_score` is outside the range 1–5
- **FR-008**: System MUST allow partial update (PATCH) of any application field
- **FR-009**: System MUST return applications ordered by `name` ascending when listing
- **FR-010**: System MUST log application create, update, and delete as structured audit events (ART-IX)

#### Business Capability Links (FR-011–FR-016)

- **FR-011**: System MUST allow linking an application to a business capability (ADP-SPEC-033) with a `fit_score` (integer 1–5)
- **FR-012**: System MUST return 422 if `fit_score` is outside the range 1–5
- **FR-013**: System MUST return 409 if a duplicate app–capability link already exists
- **FR-014**: System MUST allow updating `fit_score` on an existing link
- **FR-015**: System MUST allow removing an app–capability link without affecting the application or capability
- **FR-016**: System MUST return capability name alongside `capability_id` in link list responses

#### Technical Capability Hierarchy (FR-017–FR-023)

- **FR-017**: System MUST allow creating technical capabilities at levels 1, 2, and 3 (maximum depth 3)
- **FR-018**: System MUST assign a UUID to each technical capability on creation
- **FR-019**: System MUST return 422 if an attempt is made to create a child of an L3 capability (depth exceeded)
- **FR-020**: System MUST derive `level` automatically from the parent's level (level = parent_level + 1; L1 has no parent)
- **FR-021**: System MUST return 409 if a technical capability with children is deleted (must delete children first)
- **FR-022**: System MUST allow listing technical capabilities with parent–child relationships visible in the response
- **FR-023**: System MUST return technical capabilities ordered by name within each level

#### Application–Technical Capability Links (FR-024–FR-028)

- **FR-024**: System MUST allow linking an application to a technical capability with `usage_type` of "provides" or "consumes"
- **FR-025**: System MUST return 422 if `usage_type` is not "provides" or "consumes"
- **FR-026**: System MUST return 409 if a duplicate link (same app + same tech cap + same usage_type) already exists
- **FR-027**: System MUST allow removing an app–technical capability link
- **FR-028**: System MUST return technical capability name alongside id in link list responses

#### Application–Value Stream Stage Links (FR-029–FR-032)

- **FR-029**: System MUST allow linking an application to a value stream stage (ADP-SPEC-033)
- **FR-030**: System MUST return 409 if a duplicate app–stage link already exists
- **FR-031**: System MUST allow removing an app–stage link
- **FR-032**: System MUST cascade-delete app–stage links when a value stream stage is deleted

#### Application–Domain Integration Links (FR-033–FR-036)

- **FR-033**: System MUST allow linking an application to a business domain (ADP-SPEC-035) with `integration_type` (free text, e.g., "primary-support", "data-provider") and `direction` (one of: inbound, outbound, bidirectional)
- **FR-034**: System MUST return 422 if `direction` is not one of the defined values
- **FR-035**: System MUST allow removing an app–domain integration link
- **FR-036**: System MUST cascade-delete app–domain integration links when a business domain is deleted

#### Application Integrations (FR-037–FR-042)

- **FR-037**: System MUST allow creating a point-to-point integration between two applications with `source_app_id`, `target_app_id`, `integration_type` (one of: API, event, file, database, messaging, other), and optional `description`
- **FR-038**: System MUST return 422 if `source_app_id == target_app_id`
- **FR-039**: System MUST return 422 if `integration_type` is not one of the defined values
- **FR-040**: System MUST allow filtering integrations by `app_id` (returns integrations where app is source OR target)
- **FR-041**: System MUST allow updating `description` on an existing integration
- **FR-042**: System MUST cascade-delete all integrations when either the source or target application is deleted

#### Design Links (FR-043–FR-046)

- **FR-043**: System MUST allow linking an application to a Design (ADP-SPEC-002) by `design_id`
- **FR-044**: System MUST return 404 if the referenced design does not exist
- **FR-045**: System MUST return 409 if a duplicate app–design link already exists
- **FR-046**: System MUST allow removing an app–design link without affecting the application or the design

### Key Entities *(include if feature involves data)*

- **Application**: The central entity. Attributes: `id` (UUID), `name`, `description`, `vendor`, `primary_owner`, `time_classification` (Tolerate/Invest/Migrate/Eliminate), `r_strategy` (Rehost/Replatform/Repurchase/Refactor/Retire/Retain/Relocate), `pace_layer` (Record/Differentiation/Innovation), `health_score` (1–5), `created_at`, `updated_at`
- **TechnicalCapability**: Three-level hierarchy of user-defined technical capabilities. Attributes: `id` (UUID), `name`, `description`, `parent_id` (FK → TechnicalCapability, null for L1), `level` (1–3, derived), `created_at`
- **ApplicationCapabilityLink**: Join between Application and BusinessCapability (ADP-SPEC-033). Attributes: `app_id`, `capability_id`, `fit_score` (1–5). Composite PK.
- **ApplicationTechnicalCapabilityLink**: Join between Application and TechnicalCapability with usage direction. Attributes: `app_id`, `tech_cap_id`, `usage_type` ("provides"/"consumes"). Composite PK.
- **ApplicationStageLink**: Join between Application and ValueStreamStage (ADP-SPEC-033). Attributes: `app_id`, `stage_id`. Composite PK.
- **ApplicationDomainIntegration**: Link between Application and BusinessDomain (ADP-SPEC-035) with integration context. Attributes: `id` (UUID), `app_id`, `domain_id`, `integration_type` (free text), `direction` (inbound/outbound/bidirectional)
- **ApplicationIntegration**: Point-to-point integration between two applications. Attributes: `id` (UUID), `source_app_id`, `target_app_id`, `integration_type` (API/event/file/database/messaging/other), `description`
- **ApplicationDesignLink**: Join between Application and Design (ADP-SPEC-002). Attributes: `app_id`, `design_id`. Composite PK.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can register a new application, set its TIME classification and health score, and retrieve it in under 10 seconds total interaction time
- **SC-002**: An architect can link an application to a business capability with a fit score in a single operation and see the updated list immediately
- **SC-003**: The technical capability hierarchy supports at least 3 levels and correctly rejects attempts to exceed that depth
- **SC-004**: Integration topology (all integrations for an application) is retrievable in a single API call without pagination limitations for portfolios up to 500 applications
- **SC-005**: All application mutations (create, update, delete) are traceable in the audit log within the same request cycle
- **SC-006**: Deleting an application removes all associated links (capability, technical, stage, domain, integration, design) with no orphaned records
- **SC-007**: All validation errors return a structured 422 response with sufficient field-level detail for the UI to surface actionable messages

## Assumptions

- Technical capabilities are entirely user-defined; no pre-seeded catalog is provided in v1 — organisations impose their own taxonomy
- `primary_owner` is a free-text field (person or team name); no foreign key to a user/group table exists in v1
- `vendor` is a free-text field; no vendor master table exists in v1
- TCO and cost fields are deferred to ADP-SPEC-037 (Portfolio Analysis); this spec covers the structural/registry layer only
- TIME and R-strategy are explicit values set by the architect — the system does not suggest or recommend them in v1
- Wardley map positioning and heat-map views are deferred to ADP-SPEC-037
- Application integrations model point-to-point data/service flows only; no SLA, latency, or volume metadata in v1
- Existing ADP authentication middleware (ADP-SPEC-003) is used for all endpoints; no new auth work is required
- Design linkage uses `design_id` as a foreign key reference; the design must exist in the `designs` table (ADP-SPEC-002) at link creation time
- The `ApplicationDomainIntegration` `integration_type` is free text in v1 (no enum) to give architects flexibility before a controlled vocabulary is established
- All new tables use Alembic migration 010 (`down_revision = "009"` from ADP-SPEC-035)
- Frontend (React) for this spec is limited to basic CRUD views for applications, technical capabilities, and integrations; portfolio analysis views are deferred to ADP-SPEC-037
