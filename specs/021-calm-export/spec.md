# Feature Specification: CALM Export

**Feature Branch**: `021-calm-export`
**Created**: 2026-07-03
**Status**: Draft

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Model is Source of Truth: the ADP canonical model is the input; CALM JSON is a derived projection, not the primary record
- **ART-IV** — Test-Driven Development: always applies
- **ART-V** — Security & Threat Model: exported JSON may contain sensitive design data; export is gated by design existence check
- **ART-VIII** — Human in the Loop: export is an explicit user-initiated action; no automatic export
- **ART-IX** — Audit Trail: export action must be recorded in the design's audit log
- **ART-XI** — Provenance: exported CALM document must carry `source: "adp"` metadata and the ADP design ID

## Threat Model

**Assets at risk**: Architecture designs that may contain sensitive system names, data classifications, or security topology.

**Trust boundaries crossed**: FastAPI → file download to browser.

**Abuse cases**:
- Exfiltration of design data via repeated export calls: mitigated by requiring a valid design ID (404 if not found); no auth bypass is introduced.
- Malformed CALM output consumed by downstream tools: mitigated by CALM schema validation in the exporter before returning the document.

**Residual risk**: No per-user export permissions in v1 (single-tenant); accepted.

## User Scenarios & Testing

### User Story 1 — Export a Design as CALM JSON (Priority: P1)

An architect has completed a C4 design in ADP and wants to share it with teams using CALM-aware tooling (the FINOS CALM Hub, CALM CLI validator, or a custom pipeline). They click "Export as CALM" on the canvas and receive a valid CALM JSON file they can save, commit to a repository, or upload to CALM Hub.

**Why this priority**: The primary value — making ADP designs interoperable with the FINOS CALM ecosystem. Everything else (UI polish, audit) supports this.

**Independent Test**: `POST /api/v1/designs/{id}/export/calm` for a seeded design returns a 200 with a JSON body that is a valid CALM document (has `nodes`, `relationships` arrays; every node has `unique-id`, `node-type`, `name`, `description`).

**Acceptance Scenarios**:

1. **Given** a design with 3 elements and 2 relationships, **When** the export endpoint is called, **Then** the response is a JSON object with `nodes` (3 entries) and `relationships` (2 entries), each correctly mapped from ADP element kinds and relationship types.
2. **Given** a design with requirements, **When** exported, **Then** each requirement appears as a control in the CALM document's top-level `controls` array with a `description` matching the requirement statement.
3. **Given** a design with a `person` element, **When** exported, **Then** the CALM node has `node-type: "actor"`.
4. **Given** a design with a `container` or `component` element, **When** exported, **Then** the CALM node has `node-type: "service"`.
5. **Given** a design with a `system` element, **When** exported, **Then** the CALM node has `node-type: "system"`.
6. **Given** a non-existent design ID, **When** the export endpoint is called, **Then** the response is 404.

---

### User Story 2 — Download CALM Export from the Canvas UI (Priority: P2)

An architect triggers the export from the ADP canvas toolbar and the browser immediately downloads the CALM JSON file named `{design-id}-calm.json`.

**Why this priority**: Makes the export accessible without requiring API knowledge. Follows the existing "Export" pattern on the canvas.

**Independent Test**: Clicking "Export as CALM" in the canvas toolbar triggers a browser download of a `.json` file.

**Acceptance Scenarios**:

1. **Given** the canvas is open for a design, **When** the user clicks "Export as CALM" in the toolbar, **Then** the browser downloads a file named `{design-id}-calm.json`.
2. **Given** the download is triggered, **Then** the downloaded file is valid JSON containing `nodes` and `relationships` keys.

---

### Edge Cases

- Design with no elements: export produces `{"nodes": [], "relationships": [], ...}` — still a valid CALM document.
- Design with relationships referencing elements by ID: all relationship source/destination IDs must reference valid `unique-id` values in the nodes array.
- ADP relationship kinds not directly mappable to CALM types: default to `connects` with an annotation in metadata.
- CALM `unique-id` format: use the ADP element ID directly (already slug-style, e.g. `EL-001`).

## Requirements

### Functional Requirements

- **FR-001**: The system MUST expose `GET /api/v1/designs/{id}/export/calm` that returns a CALM-compliant JSON document for the given design.
- **FR-002**: The exporter MUST map ADP `ElementKind.PERSON` → CALM `node-type: "actor"`.
- **FR-003**: The exporter MUST map ADP `ElementKind.SYSTEM` → CALM `node-type: "system"`.
- **FR-004**: The exporter MUST map ADP `ElementKind.CONTAINER` and `ElementKind.COMPONENT` → CALM `node-type: "service"`.
- **FR-005**: Each exported CALM node MUST include `unique-id` (ADP element ID), `name`, `description`, `node-type`, and a `metadata` object carrying `adp-kind` (the original ADP element kind) and `adp-design-id`.
- **FR-006**: The exporter MUST map ADP relationships to CALM `connects` relationships, setting `source-node` and `destination-node` from the ADP relationship's source and target element IDs.
- **FR-007**: Where the ADP relationship carries a `protocol` or `technology` label, the CALM relationship MUST include a `protocol` field using the closest CALM-defined protocol value (HTTP, HTTPS, AMQP, etc.); default to `HTTPS` when unknown.
- **FR-008**: The system MUST map each ADP `Requirement` to a CALM control entry with `description` (the requirement statement) and `control-requirement-url` set to a stable ADP-generated URN (`urn:adp:requirement:{requirement-id}`).
- **FR-009**: The exported CALM document MUST include a top-level `metadata` array with an entry recording `source: "adp"`, `adp-version: "1.0.0"`, `design-id`, and `exported-at` (ISO 8601 timestamp).
- **FR-010**: The endpoint MUST write an ART-IX audit entry to the design recording `action: "calm-export"` and the exporting actor.
- **FR-011**: The endpoint MUST return `Content-Disposition: attachment; filename="{design-id}-calm.json"` so browsers trigger a download.
- **FR-012**: The React canvas toolbar MUST include an "Export as CALM" button that calls the export endpoint and triggers a browser download.

### Key Entities

- **CALMDocument**: top-level object with `nodes` (array), `relationships` (array), `controls` (array, optional), `metadata` (array, optional)
- **CALMNode**: `unique-id`, `node-type`, `name`, `description`, `metadata` (optional), `interfaces` (optional)
- **CALMRelationship**: `unique-id`, `relationship-type: "connects"`, `connects` object with `source-node`, `destination-node`, `protocol` (optional)
- **CALMControl**: `control-requirement-url`, `description`

## Success Criteria

- **SC-001**: The exported CALM document passes the CALM CLI schema validator (`calm validate`) without errors for any valid ADP design.
- **SC-002**: A design round-trip (ADP → CALM export → visual inspection in CALM Hub) preserves all element names, types, and relationships.
- **SC-003**: The export endpoint responds within 2 seconds for designs with up to 50 elements.
- **SC-004**: Every export action is traceable via the design's audit log.

## Assumptions

- The CALM schema version targeted is draft 2025-03 (latest at time of writing).
- ADP does not need to import CALM back to ADP canonical model (that is a separate spec — 022).
- C4 `level` (context/container/component) is preserved in CALM node metadata but does not change the node-type mapping.
- CALM `interfaces` (port bindings) are out of scope for v1 — relationships carry protocol at the relationship level.
- The CALM CLI validator is not invoked at runtime; validation is done against the schema inline.
