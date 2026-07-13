# Feature Specification: Element Technology Tagging

**Feature Branch**: `029-element-technology-tags`
**Created**: 2026-07-05
**Status**: Draft
**Prerequisite for**: ADP-SPEC-031 (Portfolio Analysis Screen)

## Context

Every element in an ADP design — an API Gateway, a Payment Service, a Message Broker — currently has only a name, a C4 kind, and a description. There is no structured way to record what technology it runs on, who owns it, or what platform it sits in.

This matters at portfolio scale. An Enterprise Architect needs to answer questions like "which of our designs depend on our self-hosted RabbitMQ cluster?" or "how many production systems are still running Java 8?" Without structured technology metadata on elements, every answer requires manually opening each design and reading descriptions — which defeats the purpose of a machine-readable architecture platform.

This spec adds a structured technology tagging system to ADP elements. Tags are stored as queryable metadata alongside the canonical model, enabling the cross-portfolio analysis that ADP-SPEC-031 will surface.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Model is Source of Truth: technology tags extend the canonical element record; they are part of the machine-readable model, not annotations outside it
- **ART-IV** — Test-Driven Development: always applies
- **ART-VIII** — Human in the Loop: tags are set by architects, not inferred by AI — explicit human ownership of metadata
- **ART-IX** — Audit Trail: every tag change must be recorded in the design audit log with the actor who made it

## Threat Model

**Assets at risk**: Technology metadata could reveal sensitive infrastructure details (internal platform names, vendor relationships, technology debt).

**Trust boundaries crossed**: Browser → ADP API (tag writes). No new external trust boundaries.

**Abuse cases**:
- Bulk export of technology landscape: mitigated by requiring authentication (ADP-SPEC-026) on all read endpoints.
- Incorrect tags misleading portfolio decisions: mitigated by the audit trail — every tag change is traceable to a specific architect.

**Residual risk**: Tags are only as accurate as architects keep them. Stale tags are a data quality risk, not a security risk. Accepted for v1.

## User Scenarios & Testing

### User Story 1 — Tag a Design Element with Technology Metadata (Priority: P1)

An architect opens an existing design on the Canvas, selects the "Payment API Gateway" element, and fills in its technology metadata: technology = "Kong", platform = "AWS EKS", vendor = "Kong Inc.", version = "3.4", owner_team = "Platform Engineering". After saving, the metadata is visible in the element inspection panel and stored in the design.

**Why this priority**: Without the ability to add tags, the entire portfolio query capability in ADP-SPEC-031 has no data to work with. This is the write path that enables everything else.

**Independent Test**: Open a design; select an element; add technology tags; save; reload the design; assert tags are displayed correctly in the inspection panel.

**Acceptance Scenarios**:

1. **Given** a design with one or more elements, **When** an architect selects an element and opens its detail view, **Then** a "Technology" section is visible where metadata fields can be filled in.
2. **Given** an architect fills in technology, platform, vendor, version, and owner team, **When** they save, **Then** all values are persisted and visible on next page load.
3. **Given** a tag has been saved, **When** the design's audit log is viewed, **Then** an entry shows which architect added or changed the tag and when.
4. **Given** an element with no tags, **When** the element is displayed, **Then** the technology section shows an empty/unfilled state without error.
5. **Given** an element with existing tags, **When** an architect updates one field and saves, **Then** only the changed field is updated; unchanged fields retain their values.

---

### User Story 2 — Add Free-Form Tags for Ad-Hoc Categorisation (Priority: P2)

An architect wants to mark certain elements with cross-cutting labels that don't fit the structured fields — for example tagging elements with "needs-migration", "gdpr-scope", or "legacy". They add these as free-form tags (a list of short strings) alongside the structured metadata.

**Why this priority**: Structured fields cover the most common metadata, but ad-hoc tagging handles the long tail of categorisation needs without requiring a schema change for every new concept.

**Independent Test**: Add three free-form tags to an element; save; reload; assert all three appear as distinct tags in the display.

**Acceptance Scenarios**:

1. **Given** an element's technology section, **When** an architect types a tag label and presses Enter (or equivalent), **Then** the tag appears as a removable chip in the UI.
2. **Given** one or more free-form tags on an element, **When** an architect clicks the remove icon on a tag, **Then** that tag is deleted on save.
3. **Given** a free-form tag, **Then** tag labels are limited to 50 characters and must not be blank; invalid input shows a validation message before save.

---

### User Story 3 — View Technology Metadata in the Element Inspection Panel (Priority: P3)

Any architect viewing a design can see the technology metadata for any element directly in the inspection panel on the Canvas. They do not need to be editing the design to see what technology an element uses.

**Acceptance Scenarios**:

1. **Given** an element with tags, **When** any architect (including read-only viewers) clicks the element on the Canvas, **Then** the inspection panel shows all technology metadata in a clear, readable layout.
2. **Given** an element with no tags, **When** the inspection panel is shown, **Then** the technology section is visible but shows "No technology metadata added yet".

---

### Edge Cases

- Element with only some fields filled (e.g. technology but no vendor): save succeeds; only filled fields displayed; empty fields do not show as errors.
- Very long technology names or vendor names: capped at 200 characters with a character counter shown when approaching the limit.
- Two architects saving tags for the same element simultaneously: last write wins (consistent with existing design save behaviour); both writes recorded in the audit log.
- Deleting an element that has tags: tags are deleted with the element; no orphaned metadata.
- Copying or exporting a design (ADP-SPEC-011 / ADP-SPEC-021): technology tags are included in the exported artefact.

## Requirements

### Functional Requirements

**Tag Structure (FR-001 to FR-003)**

- **FR-001**: Each design element MUST support the following optional structured metadata fields: `technology` (the primary technology name, e.g. "Apache Kafka"), `vendor` (the technology vendor or maintainer, e.g. "Confluent"), `platform` (the hosting platform, e.g. "AWS EKS"), `version` (the technology version, e.g. "3.4.1"), `owner_team` (the team responsible for this element, e.g. "Platform Engineering").
- **FR-002**: Each design element MUST support a list of free-form `tags` (short string labels, maximum 50 characters each, no maximum count in v1) for ad-hoc categorisation.
- **FR-003**: All metadata fields are optional. An element with no technology metadata is valid and behaves identically to the current element model.

**Write Path (FR-004 to FR-006)**

- **FR-004**: The system MUST provide an interface for architects to view and edit technology metadata for any element within a design they have write access to.
- **FR-005**: Saving technology metadata MUST write an audit entry to the design's audit log recording the actor, the element affected, and the fields changed (ART-IX).
- **FR-006**: Technology metadata MUST be persisted alongside the canonical design model and included in all design export formats (document export, CALM export) so the information travels with the design.

**Read Path (FR-007 to FR-008)**

- **FR-007**: Technology metadata MUST be visible to all users who can view a design, in the element inspection panel, without requiring edit access.
- **FR-008**: The system MUST expose technology metadata via the design read API so that external tools and the portfolio analysis feature (ADP-SPEC-031) can query it without parsing unstructured description text.

**Portfolio Query Enablement (FR-009)**

- **FR-009**: The system MUST store technology tags in a form that allows efficient cross-design queries (e.g. "find all designs containing elements tagged with technology='Kafka'") without requiring a full scan of each design's content. This storage form is the foundation for ADP-SPEC-031.

### Key Entities

- **ElementTechnologyMetadata**: Structured metadata attached to one element within one design. Fields: `element_id`, `design_id`, `technology` (string, optional), `vendor` (string, optional), `platform` (string, optional), `version` (string, optional), `owner_team` (string, optional), `tags` (list of strings, optional). The `element_id` + `design_id` combination is unique.

## Success Criteria

- **SC-001**: An architect can add, edit, and remove technology metadata for any element in under 30 seconds of interaction.
- **SC-002**: All technology metadata added to elements is included in the design's CALM export and document export without data loss.
- **SC-003**: Every tag change is traceable in the audit log to a named architect with a timestamp, with no gaps in the trail.
- **SC-004**: A cross-portfolio query filtering by technology name (e.g. "show all designs with an element tagged technology='Kafka'") returns correct results within 2 seconds across a portfolio of 100 designs.
- **SC-005**: Technology metadata fields are consistently visible in the element inspection panel across all three C4 canvas levels (context, container, component).

## Assumptions

- Technology metadata is manually entered by architects; no AI inference of technology in v1.
- There is no controlled vocabulary (taxonomy) for technology names in v1 — architects type free text. Autocomplete from existing values in the portfolio is desirable but out of scope for this spec.
- Tags are per-element, not per-design. A design's technology landscape is derived by aggregating across its elements.
- The existing C4 element kinds (person, system, container, component) are not changed. Technology tagging is additive metadata on top of the existing model.
- Free-form tag count is unlimited in v1; abuse prevention (e.g. thousands of tags) is a future concern.
- Technology metadata is shared with all authenticated users who can view a design; no element-level access control.
