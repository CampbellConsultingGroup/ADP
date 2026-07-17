# Feature Specification: Application Portfolio Management

**Feature Branch**: `038-application-portfolio-management`
**Created**: 2026-07-16
**Status**: Draft
**Input**: User description: "Application Portfolio Management (APM): expand the application registry (ADP-SPEC-036) so applications can be inventoried, scored, and rationalized across eight APM data categories, to enable business-value vs technical-health (TIME) rationalization."

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies) — this spec precedes implementation.
- **ART-II** — The Model is the Single Source of Truth: APM attributes extend the canonical application registry; no parallel data store. Where an attribute already exists on a linked design/element (e.g. technology stack via `element_technology_tags`), APM references it rather than duplicating.
- **ART-III** — Everything is Machine-Readable: all new entities/enums emit to JSON Schema via the generator.
- **ART-IV** — Test-Driven Development: (always applies) — contract + unit tests precede handlers; migrations verified up/down.
- **ART-V** — Security by Design: APM introduces the platform's most sensitive data (costs, vendor contracts, security posture, data classification, regulatory tags). Read/write is gated by action-based authz (ADP-SPEC-004). See Threat Model.
- **ART-IX** — Provenance and Auditability: every create/update/delete of an APM attribute writes an `AuditEntry`.
- **ART-XIII** — Typed Contracts Everywhere: all boundary payloads are Pydantic v2 models with `extra="forbid"`; money is `Decimal`, never `float`.
- **ART-XV** — Schema Evolution is Governed: all schema changes ship as reviewed Alembic migrations with verified down-revisions; migration numbering is coordinated with the other open capability migrations (ADP-4ga, ADP-33v, ADP-9x6).
- **ART-XVI** — Documentation as Code: the APM data dictionary (attribute → category → definition) is versioned alongside the spec.

*Not engaged*: ART-VII (Grounded AI) — APM is structured data capture, not AI generation. ART-XII (Fixed Visual Language) — no C4 rendering change.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Application cost figures and vendor contract terms (commercially sensitive); security posture, vulnerability status, and data-classification/regulatory tags (disclosing these is itself a security risk — it maps the organization's soft targets); business-value/criticality scores (reveal what matters most). Collectively, the APM dataset is a rationalization dossier of the entire estate.

**Trust boundaries crossed**: browser → API (all APM data flows over the existing FastAPI surface). No new external integration in scope for v1 (quality/performance ingestion from ops tooling is deferred — see Assumptions).

**Abuse cases**:
- *Unauthorized disclosure*: a low-privilege user reads cost/contract/security-posture fields → **Mitigation**: APM read and write are gated by action-based permissions (ADP-SPEC-004); sensitive categories (cost, risk, governance) require a dedicated permission distinct from general application read.
- *Tampering to skew rationalization*: an actor lowers a rival system's business-value score or hides an EOL date to force/avoid a decommission → **Mitigation**: every write produces an `AuditEntry` (ART-IX) with actor + before/after; rationalization views are read-only projections.
- *Data-classification leakage via export/report*: sensitive APM fields leak through governance reporting or CSV export → **Mitigation**: exports honor the same permission gate; the no-sensitive-data test (QG) is extended to cover APM fields.

**Residual risk**: APM data is only as trustworthy as manual entry; stale risk/EOL data can mislead decisions. Accepted at this threat level because the audit trail makes staleness attributable and the review-due mechanism (mirroring design lifecycle) surfaces aging records. Quantitative quality/performance metrics remain manual/absent in v1 (ingestion deferred), so those signals are advisory.

## User Scenarios & Testing *(mandatory)*

> Each story is an independently shippable slice: it adds its category's attributes, typed contracts, migration, audit, authz, and a read surface, and delivers standalone value. Stories are ordered by **rationalization value**, not by the taxonomy's listing order.

### User Story 1 - Plot the estate on the business-value × technical-health quadrant (Priority: P1)

A portfolio analyst wants to see every application placed on the classic TIME rationalization plot (Tolerate / Invest / Migrate / Eliminate) so they can drive rationalization decisions. The technical-health axis already exists (`applications.health_score`); the missing half is a **business-value / criticality** score *on the application*. This story adds that score and delivers the quadrant view.

**Why this priority**: This is the single highest-leverage addition — one new scored axis turns data ADP *already* holds (health_score, time_classification, dependency graph) into a working rationalization view. It is the MVP: shippable alone, and it de-risks the whole epic by proving the scoring + view pattern.

**Independent Test**: Score a set of applications for business value/criticality, then retrieve the rationalization projection and confirm each application lands in the correct TIME quadrant from (business_value × health_score); verify an unscored application is reported as "unplaced" rather than defaulting.

**Acceptance Scenarios**:

1. **Given** an application with a health_score and a business_value score, **When** the analyst opens the rationalization view, **Then** the application appears in the quadrant computed from both axes.
2. **Given** an application with no business_value score, **When** the view is rendered, **Then** it is listed as "not yet assessed" and excluded from quadrant placement (never silently defaulted to a quadrant).
3. **Given** a business_value score is changed, **When** the update is saved, **Then** an audit entry records actor + old/new value and the quadrant placement updates.

### User Story 2 - Complete application identity & ownership basics (Priority: P2)

An APM administrator needs each application to carry its owning **business unit**, a distinct **business owner** and **technical owner** (today only a single `primary_owner` exists), and an explicit **lifecycle status** (planned / active / sunset / retired — designs have this via ADP-SPEC-030, applications do not).

**Why this priority**: Identity completeness is the backbone every other category filters and rolls up by (cost-by-BU, risk-by-owner, roadmap-by-lifecycle). Cheap to add, unblocks aggregation elsewhere.

**Independent Test**: Set BU, both owners, and lifecycle status on an application; filter the registry by business unit and by lifecycle status and confirm correct membership.

**Acceptance Scenarios**:

1. **Given** an application, **When** an admin sets owning business unit, business owner, technical owner, and lifecycle status, **Then** all persist and round-trip through the API with an audit entry.
2. **Given** applications across several business units, **When** the registry is filtered by business unit, **Then** only that unit's applications are returned.
3. **Given** a lifecycle status transition (e.g. active → sunset), **When** saved, **Then** the transition is audited and surfaces in the roadmap view.

### User Story 3 - Risk & compliance register (Priority: P3)

A risk/compliance owner records, per application: security posture, vulnerability status, **data classification/sensitivity**, applicable **regulatory requirements** (SOX / GDPR / HIPAA / …), DR/BC status, and **end-of-life / end-of-support dates**.

**Why this priority**: The largest current gap and table-stakes for any APM program; EOL/EOS dates and data classification drive the most urgent rationalization and compliance actions. Highest sensitivity — validates the sensitive-field authz path.

**Independent Test**: Record risk attributes on an application including an EOS date in the past; query "applications past end-of-support" and confirm it appears; confirm a user without the risk permission cannot read the fields.

**Acceptance Scenarios**:

1. **Given** an application, **When** the risk owner sets data classification, regulatory tags, and EOL/EOS dates, **Then** they persist with an audit entry.
2. **Given** an application with an EOS date in the past, **When** the compliance view is queried, **Then** it is flagged as out-of-support.
3. **Given** a user lacking the risk-read permission, **When** they fetch the application, **Then** risk/compliance fields are withheld (or the request denied) per the authz policy.

### User Story 4 - Total Cost of Ownership & spend rollups (Priority: P4)

A portfolio owner captures TCO across the eight cost buckets (per **ADP-9x6**), plus **cost allocation by business unit** and a **run-vs-change** spend ratio, to see where money goes and support cost-vs-value decisions.

**Why this priority**: Cost completes the value story once identity (BU) exists to allocate against. Depends on US2 for BU allocation. TCO is already partly scoped (ADP-9x6).

**Independent Test**: Enter per-bucket costs (as Decimal, with ISO-4217 currency) on applications in two business units; retrieve the per-BU cost rollup and the run-vs-change ratio and confirm the arithmetic.

**Acceptance Scenarios**:

1. **Given** an application, **When** costs are entered across the eight buckets with a currency and horizon, **Then** TCO = the sum of the buckets and round-trips as `Decimal` (never float).
2. **Given** applications allocated to business units, **When** the cost-by-BU rollup is requested, **Then** totals aggregate correctly per unit.
3. **Given** bucket costs, **When** the run-vs-change ratio is computed, **Then** run (operational + maintenance + support) vs change (acquisition + implementation + upgrades) is reported.

### User Story 5 - Technical fit depth (Priority: P5)

An architect records **hosting model** (on-prem / cloud / SaaS), **architecture pattern**, and explicit **technical-debt flags** (e.g. unsupported versions, deprecated tech) on an application, complementing the existing technology-tag and dependency data.

**Why this priority**: Sharpens the technical-health axis and rationalization rationale; builds on existing tech-capability links, `application_integrations` (dependency graph), and `element_technology_tags`.

**Independent Test**: Set hosting model and a tech-debt flag; filter the registry for cloud-hosted apps and for apps carrying tech-debt flags and confirm membership.

**Acceptance Scenarios**:

1. **Given** an application, **When** hosting model, architecture pattern, and tech-debt flags are set, **Then** they persist with an audit entry.
2. **Given** applications with mixed hosting models, **When** filtered by hosting model, **Then** correct membership is returned.
3. **Given** an application flagged for unsupported technology, **When** the technical-health view is rendered, **Then** the flag is surfaced against that application.

### User Story 6 - Lifecycle & roadmap (Priority: P6)

A planner links applications to **transformation initiatives** and records planned changes (retire / replace / modernize / invest) and EOL milestones, building on the existing `time_classification` (TIME) and `r_strategy` (the Rs).

**Why this priority**: Turns point-in-time classification into a forward roadmap; depends on US2 lifecycle status and US3 EOL dates being present.

**Independent Test**: Create a transformation initiative, link two applications, and retrieve the initiative with its member applications and their planned dispositions.

**Acceptance Scenarios**:

1. **Given** a transformation initiative, **When** applications are linked to it, **Then** the initiative lists its members and each member surfaces the initiative on its record.
2. **Given** an application with `time_classification` = Eliminate and a retirement date, **When** the roadmap is viewed, **Then** it appears on the decommission track.

### User Story 7 - Ownership & governance (Priority: P7)

A governance lead records vendor **contract details and renewal dates**, **SLAs**, internal stakeholder roles (business sponsor, IT owner), and decision rights, so contract renewals and accountability are visible.

**Why this priority**: Important for governance and renewal planning but not on the critical path to the rationalization plot; depends on identity (US2) for stakeholder roles.

**Independent Test**: Record a contract with a renewal date within 90 days; query "contracts renewing soon" and confirm it appears.

**Acceptance Scenarios**:

1. **Given** an application with a vendor, **When** contract terms, renewal date, and SLA are recorded, **Then** they persist with an audit entry.
2. **Given** a contract renewing within a configurable window, **When** the renewals view is queried, **Then** the application is flagged.

### User Story 8 - Quality & performance signals (Priority: P8)

A service owner records or reviews reliability/uptime, incident history, user satisfaction, performance metrics, and support-ticket volume as advisory quality signals.

**Why this priority**: Valuable context but typically fed from ops tooling; lowest priority because v1 captures manual/point-in-time values only (automated ingestion is deferred).

**Independent Test**: Record a set of quality metrics on an application and confirm they surface on the application's quality panel and feed the health narrative (without overriding the technical-health score in v1).

**Acceptance Scenarios**:

1. **Given** an application, **When** quality metrics are recorded, **Then** they persist with an audit entry and surface on the quality panel.
2. **Given** recorded metrics, **When** the technical-health context is viewed, **Then** the metrics are shown as advisory signals alongside `health_score`.

### Edge Cases

- **Unassessed vs. worst score**: an unscored business_value/criticality or maturity must read as "not assessed" (NULL), never silently as the lowest active rating — placement/rollups must exclude, not default.
- **Money edge cases**: mixed currencies across applications when rolling up per BU (v1 assumes a single reporting currency — see Assumptions); negative or zero costs; extremely large figures (NUMERIC precision).
- **Sensitive-field authz on aggregates**: a cost/risk rollup must not leak per-application sensitive values to a user who lacks the field-level permission.
- **Lifecycle/roadmap conflicts**: `time_classification` = Eliminate while lifecycle_status = active with no retirement date — surfaced as a data-quality warning, not blocked.
- **Deletion**: deleting an application must cascade its APM child records (cost, risk, governance, quality) and links, and audit the cascade.
- **Stale risk data**: EOL/EOS dates in the past with no recorded action — surfaced via a review-due mechanism.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add a business-value/criticality score to the application entity, distinct from the existing hierarchy/classification fields, with an explicit "not assessed" state (NULL) separate from the lowest active value.
- **FR-002**: System MUST provide a read-only rationalization projection that places each *assessed* application in a TIME quadrant computed from (business_value × health_score), and MUST list unassessed applications separately.
- **FR-003**: System MUST extend application identity with owning business unit, distinct business owner and technical owner, and an explicit lifecycle status (planned / active / sunset / retired).
- **FR-004**: System MUST allow recording, per application, of risk & compliance attributes: security posture, vulnerability status, data classification/sensitivity, regulatory tags (multi-valued), DR/BC status, and end-of-life / end-of-support dates.
- **FR-005**: System MUST flag applications whose end-of-support date is in the past (out-of-support) and MUST support a "renewing/expiring soon" query window.
- **FR-006**: System MUST capture Total Cost of Ownership across the eight cost buckets per ADP-9x6, storing all monetary values as decimal (NUMERIC), never floating point, with an ISO-4217 currency and an analysis horizon; TCO MUST be derivable as the sum of the buckets.
- **FR-007**: System MUST support cost allocation by business unit and a run-vs-change spend ratio derived from the cost buckets.
- **FR-008**: System MUST capture technical-fit attributes: hosting model, architecture pattern, and technical-debt flags.
- **FR-009**: System MUST support transformation initiatives as first-class records and many-to-many links between applications and initiatives, with each application surfacing its planned disposition.
- **FR-010**: System MUST capture ownership & governance attributes: vendor contract details, renewal dates, SLAs, stakeholder roles (business sponsor, IT owner), and decision rights.
- **FR-011**: System MUST capture quality & performance signals (reliability/uptime, incident history, user satisfaction, performance metrics, support-ticket volume) as advisory values that do not override `health_score` in v1.
- **FR-012**: System MUST write an `AuditEntry` (actor, action, affected entity, before/after summary) for every create/update/delete of any APM attribute (ART-IX).
- **FR-013**: System MUST gate APM reads and writes by action-based permissions (ADP-SPEC-004); sensitive categories (cost, risk & compliance, governance) MUST require a permission distinct from general application read, and aggregates MUST NOT leak sensitive per-application values to unauthorized users.
- **FR-014**: All APM boundary payloads MUST be typed (Pydantic v2, `extra="forbid"`), and all new entities/enums MUST emit to JSON Schema via the generator (ART-III/ART-XIII).
- **FR-015**: All schema changes MUST ship as reviewed Alembic migrations with verified down-revisions, coordinated with the open capability migrations (ADP-4ga maturity, ADP-33v strategic relevance, ADP-9x6 TCO) so numbering does not collide.
- **FR-016**: Deleting an application MUST cascade and audit removal of its APM child records and links.
- **FR-017**: System MUST publish a versioned APM data dictionary mapping each attribute to its APM category and definition (ART-XVI).
- **FR-018**: System MUST reconcile with existing feeders rather than duplicate them: strategic relevance (ADP-33v) and maturity (ADP-4ga) on capabilities, and the capability gap analysis (ADP-zg3.4), feed Business fit; technology stack/version continues to come from `element_technology_tags`; app-to-app dependencies from `application_integrations`.
- **FR-019**: System MUST express the business-value/criticality dimension as a bounded, ordinal, labelled scale [NEEDS CLARIFICATION: single composite score, or separate "business value" and "business criticality" dimensions? and what scale — 1–5, or High/Medium/Low?].
- **FR-020**: TCO bucket structure MUST support the given example (a recurring annual cost projected over a horizon) [NEEDS CLARIFICATION: store one lump amount per bucket over the horizon, or split one-time vs. annual components and compute over the horizon? — carried from ADP-9x6].
- **FR-021**: Quality & performance metrics MUST be captured [NEEDS CLARIFICATION: manual entry only in v1, or is ingestion from an external ops/monitoring source in scope?].

### Key Entities *(include if feature involves data)*

- **Application (extended)**: the APM unit. Gains business_value/criticality, owning business unit, business owner, technical owner, lifecycle status, hosting model, architecture pattern, tech-debt flags. Retains existing vendor, primary_owner, time_classification (TIME), r_strategy, pace_layer, health_score.
- **ApplicationCost (TCO)**: per-application cost across the eight buckets; currency (ISO-4217), analysis horizon; amounts as decimal. Enables per-BU allocation and run-vs-change. (Scoped by ADP-9x6.)
- **ApplicationRisk**: security posture, vulnerability status, data classification, regulatory tags (multi-valued), DR/BC status, EOL/EOS dates.
- **ApplicationGovernance / Contract**: vendor contract terms, renewal date, SLA, stakeholder roles, decision rights.
- **ApplicationQualityMetric**: advisory reliability/uptime, incidents, satisfaction, performance, ticket volume.
- **TransformationInitiative**: a named change program; many-to-many with applications, each link carrying a planned disposition.
- **RationalizationProjection**: a derived, read-only view placing assessed applications on the business-value × technical-health (TIME) quadrant. Not stored — computed.
- **AuditEntry (existing)**: reused for all APM writes (ART-IX).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An analyst can retrieve a rationalization projection that places 100% of *assessed* applications into a TIME quadrant, with unassessed applications reported separately (never mis-placed).
- **SC-002**: Adding the business-value/criticality score requires exactly one new scored dimension on the application — no other data entry — to make the quadrant usable, demonstrating the "one field completes TIME" goal.
- **SC-003**: For any application, an authorized user can view its complete APM record spanning all eight categories, and each populated attribute is attributable to an actor and time via the audit trail.
- **SC-004**: A user lacking sensitive-category permission can never read cost, risk/compliance, or contract values — verified for both direct reads and aggregate/rollup endpoints.
- **SC-005**: The system surfaces every application that is out-of-support (EOS date in the past) and every contract renewing within the configured window.
- **SC-006**: Per-business-unit cost rollups and the run-vs-change ratio reconcile exactly to the sum of the underlying application cost buckets.
- **SC-007**: 100% of monetary values persist and round-trip as decimal with no floating-point representation error.
- **SC-008**: Every APM schema change has a verified reversible migration and zero schema-drift-check failures in CI.

## Assumptions

- **Single reporting currency (v1)**: cost rollups assume one organization reporting currency; multi-currency conversion is out of scope for v1 (per-application currency is still stored for fidelity).
- **Manual quality/performance capture (v1)**: quality & performance metrics are entered/reviewed manually; automated ingestion from monitoring/ITSM tooling is a future feature.
- **Application is the APM unit**: APM attributes attach to the existing `applications` registry (ADP-SPEC-036), not to C4 designs; design linkage remains via `application_design_links`.
- **Authz model reused**: sensitive-category gating uses the existing action-based permission system (ADP-SPEC-004); this feature adds new permission actions but no new authz mechanism.
- **Feeders are reparented, not duplicated**: ADP-9x6 (TCO), ADP-33v (strategic relevance), ADP-4ga (maturity), and ADP-zg3.4 (gap analysis) become work items under this epic; their schema lands under this feature's migration sequence.
- **Migration coordination**: because ADP-4ga, ADP-33v, and ADP-9x6 each reserve an unimplemented migration after the on-disk head (`011_searchable_items`), the plan phase assigns contiguous migration numbers to avoid collision.
- **Zero new runtime packages expected** beyond what the stack already provides (SQLAlchemy NUMERIC + Python `Decimal` cover money).
