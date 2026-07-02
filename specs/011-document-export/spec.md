# Feature Specification: Document, View & Export Generation

**Feature Branch**: `011-document-export`
**Created**: 2026-07-02
**Status**: Draft
**Input**: `/home/jmuir/projects/ADP/docs/011-document-view-export.md`

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Canonical Model as Single Source of Truth: the central article for this feature; every document, view, matrix, and report is a generated projection of the canonical model — nothing is hand-authored
- **ART-III** — Everything is Machine-Readable: all generated documents carry typed metadata mirroring their structured form; all exported artifacts validate against published schemas
- **ART-IV** — Test-Driven Development: always applies
- **ART-VIII** — Human-in-the-Loop for Consequence: export to version control is a consequential action requiring explicit, attributable human confirmation before writing
- **ART-IX** — Provenance and Auditability: every export writes an audit entry recording who exported, which design version, and when
- **ART-XIV** — Reproducible, Drift-Free Builds: all generated artifacts are reproducible from a given model version (same model → same output)
- **ART-XV** — Schema Evolution is Governed: exported artifacts carry their schema version; re-import validates against the published schema
- **ART-XVI** — Documentation as Code: this feature is the direct implementation of ART-XVI — documents are projections of the model, not primary records

**ART-V (security)**: Moderate risk — export crosses a trust boundary from the ADP platform to an external version control system and involves organizational IP. See Threat Model below.

**ART-VII (AI grounding)**: Not engaged — this feature has no LLM component.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Architecture designs (organizational IP), requirements, recommendations, and validation reports; the target version control repository.

**Trust boundaries crossed**: ADP platform → external version control system (file write); ADP API → calling actor (human confirmation gate).

**Abuse cases**:
- Unauthorized export of a sensitive design to version control: could expose organizational architecture to unintended parties → Mitigated by role-based authorization (only authorized architects can initiate export) and explicit confirmation gate (ART-VIII)
- Export of an invalid or stale model to version control: could introduce corrupt data into the durable record → Mitigated by schema validation before any export begins (FR-006); export is aborted if validation fails
- Replay or accidental re-export of a superseded model version: could overwrite a more recent export → Mitigated by including the design version in the export directory path; older directories are never overwritten by newer exports of different versions
- Bulk export of many designs without authorization: could exfiltrate a complete architecture library → Mitigated by per-export confirmation requirement (ART-VIII); each export is a distinct human-approved action

**Residual risk**: Low-moderate. Export is one-directional (ADP → VCS); no external system writes back to the canonical model through this feature. The primary risk is IP disclosure, mitigated by authorization controls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate a Stakeholder Document (Priority: P1)

An Architect has completed a design and needs to share it with business stakeholders who cannot read raw model data. They request document generation for a design; the system produces a structured Markdown document that includes the design title, element descriptions, requirement summaries, and a traceability summary — all derived from the canonical model. The document carries typed metadata (design ID, model version, generation timestamp) in its frontmatter. No content is hand-authored; if the model changes, regenerating produces an updated document.

**Why this priority**: This is the most immediate deliverable value — turning a canonical model into a readable artifact that stakeholders can review. It also validates the core "model → projection" pipeline that all other stories depend on.

**Independent Test**: Provide a design with 3 elements, 2 requirements, and 1 verdict; request document generation; verify the output Markdown contains the element names, requirement summaries, design ID, and model version in the typed metadata frontmatter.

**Acceptance Scenarios**:

1. **Given** a valid design with elements and requirements, **When** document generation is requested, **Then** the system produces a Markdown document containing all element names and requirement summaries derived from the model.
2. **Given** the generated document, **When** its frontmatter is inspected, **Then** it carries the design ID, model schema version, and generation timestamp as typed metadata.
3. **Given** the same design at two different model versions, **When** documents are generated for each, **Then** the two documents differ only where the model differs — no hand-authored content diverges.
4. **Given** a design with a missing required field (e.g., no title), **When** document generation is requested, **Then** the system returns a clear error rather than producing a document with empty sections.

---

### User Story 2 — Project Per-Persona C4 Views (Priority: P1)

An Enterprise Architect needs to share the same architecture design with two different audiences: business stakeholders who need the context-level picture and technical engineers who need the container-level detail. Rather than maintaining two separate diagrams, the system projects the appropriate C4 level from the same canonical model for each persona. Each view renders only the elements appropriate to that level and applies the locked visual theme consistently.

**Why this priority**: Equal to P1 with document generation — multi-persona projection is a core platform promise and demonstrates that one model serves all audiences without duplication.

**Independent Test**: Provide a design with person, system, container, and component elements; request context and container views; verify the context view contains only person + system elements and the container view contains only system + container elements, both derived from the same model.

**Acceptance Scenarios**:

1. **Given** a design with elements of all C4 kinds, **When** a context-level view is requested, **Then** the view includes only person and system elements.
2. **Given** the same design, **When** a container-level view is requested, **Then** the view includes only system and container elements.
3. **Given** the same design, **When** a component-level view is requested, **Then** the view includes only container and component elements.
4. **Given** views generated at two different C4 levels from the same design, **When** inspected, **Then** both apply identical styling for shared element types (same fill color for system elements in both context and container views).

---

### User Story 3 — Generate Requirements Traceability Matrix (Priority: P2)

A reviewer or Enterprise Architect needs to verify that every element in the design satisfies at least one stated requirement, and that every requirement has been addressed by at least one element. The system generates a traceability matrix that threads every element to its requirements, the recommendation that produced it, and the validation verdicts that evaluated it. The matrix is a machine-readable artifact (not just a rendered table) so it can be queried, diffed, and validated.

**Why this priority**: Traceability is a governance deliverable. It depends on US1/US2 existing (elements and views in the model) but delivers distinct and important audit value.

**Independent Test**: Provide a design where ELM-001 satisfies REQ-001 and was produced by OPT-001; request the traceability matrix; verify the output contains an entry linking ELM-001 → REQ-001 → OPT-001; also verify that any element with no satisfied requirements appears in a "orphans" section.

**Acceptance Scenarios**:

1. **Given** a design where all elements satisfy at least one requirement, **When** the traceability matrix is generated, **Then** every element appears in the matrix with its satisfied requirement IDs.
2. **Given** a design with an element that satisfies no requirements, **When** the matrix is generated, **Then** that element appears in an explicit "orphan elements" section — it is not silently omitted.
3. **Given** a design where elements have AI-recommendation provenance, **When** the matrix is generated, **Then** each such element lists its provenance (recommendation ID and accepted option ID).
4. **Given** the matrix is generated twice from the same model version, **When** the outputs are compared, **Then** they are byte-identical (deterministic generation).

---

### User Story 4 — Export to Version Control (Priority: P2)

An Enterprise Architect has approved a design and wants to write the durable record to version control. They request an export; the system asks for explicit confirmation (naming the design ID and version being exported). After confirmation, the system writes the canonical model as JSON and YAML, the Structurizr DSL source for each C4 level, the rendered diagram images (SVG and PNG for each level), and the generated stakeholder Markdown document — all to a structured directory in version control. The export is recorded as an audit entry.

**Why this priority**: Export is the durable record — the thing that survives outside ADP. It depends on US1 (document generation) and US2 (views) but is its own distinct action requiring human approval.

**Independent Test**: Initiate an export for a design; provide explicit confirmation; verify the export directory contains at minimum a `model.json`, `model.yaml`, `context.svg`, `container.svg`, `component.svg`, `README.md` (stakeholder document), and an audit entry is written.

**Acceptance Scenarios**:

1. **Given** an approved design, **When** an export is initiated, **Then** the system presents a confirmation request naming the exact design ID and version before writing any files.
2. **Given** the confirmation is given, **When** export completes, **Then** the export directory contains: `model.json`, `model.yaml`, DSL source and SVG+PNG for each C4 level, and a stakeholder Markdown document.
3. **Given** the export completes, **When** the audit log is queried, **Then** an entry exists recording the actor, design ID, exported version, and timestamp.
4. **Given** the confirmation is declined, **When** the export is cancelled, **Then** no files are written and no audit entry is created.
5. **Given** any exported artifact fails schema validation, **When** export is attempted, **Then** the entire export is aborted before any files are written; no partial export appears in version control.

---

### User Story 5 — Round-Trip Import and Validation (Priority: P3)

A delivery team has an exported `model.json` from a previous ADP export. They want to bring it back into ADP to use as a baseline for a new design. The system re-imports the canonical JSON, validates it against the current schema, and reconstructs an equivalent in-memory model. If the imported model's schema version is older than the current version and a migration is available, the system applies it.

**Why this priority**: Round-trip integrity is a correctness guarantee, not a primary workflow. It is important for resilience (exports must be usable) but does not block the core generation and export workflows.

**Independent Test**: Export a design to `model.json`; re-import the exported file; verify the re-imported design has the same element count, relationship count, and element IDs as the original; verify no validation errors are reported.

**Acceptance Scenarios**:

1. **Given** an exported `model.json` at the current schema version, **When** it is re-imported, **Then** it validates with zero errors and the reconstructed model has element-for-element equivalence with the original.
2. **Given** an exported `model.json` at an older schema version with a known migration, **When** it is re-imported, **Then** the migration is applied and the resulting model validates against the current schema.
3. **Given** a corrupted or schema-invalid `model.json`, **When** re-import is attempted, **Then** the system rejects it with a clear validation error identifying the failing constraint, and no partial model is created.

---

### Edge Cases

- What happens when the design has no elements? Document and traceability matrix must still be generated (as empty-section documents) rather than erroring.
- What happens when the export target directory already exists at that version? The system must return an error rather than overwriting; re-export requires an explicit version bump in the design.
- What happens when version control is unavailable during export? Export must fail cleanly with a clear infrastructure error; no partial files must be written; the confirmation step must record that export did not complete.
- What happens when a generated document exceeds a rendering limit (e.g., 500 elements)? The system must still generate the document but may paginate or truncate the traceability matrix with a note.
- What happens when the model schema version in an imported file is newer than the current ADP version? Re-import must reject with a clear "schema version not supported" error.
- What happens if re-import of a round-tripped model introduces orphan element references? The referential integrity validator must catch and report them before the model is accepted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every generated stakeholder document MUST be produced from the canonical model and MUST carry typed metadata (design ID, schema version, generation timestamp) as structured frontmatter — no hand-authored primary content.
- **FR-002**: The system MUST project per-persona C4 views (context, container, component) from a single design model without requiring separate diagram sources.
- **FR-003**: The system MUST generate a requirements traceability matrix that links every design element to its satisfied requirements, recommendation provenance, and validation verdicts; orphan elements (no satisfied requirements) MUST appear explicitly in the output.
- **FR-004**: An export operation MUST write the following artifacts to version control: canonical model as JSON and YAML, Structurizr DSL source for each generated C4 level, rendered diagram images (SVG and PNG for each level), and the stakeholder Markdown document.
- **FR-005**: Export to version control MUST require explicit, attributable human confirmation naming the design ID and version; confirmation MUST be recorded as an audit entry with actor, timestamp, and export target.
- **FR-006**: All exported artifacts MUST validate against their published schemas before any files are written; a validation failure MUST abort the entire export — no partial exports are permitted.
- **FR-007**: An exported canonical artifact MUST be re-importable; the re-imported model MUST validate against the current schema and reconstruct with element-for-element equivalence to the original.

### Key Entities

- **Generated Document**: A Markdown document produced from a design; carries typed frontmatter metadata; content is fully derived from the canonical model; has no independent primary content.
- **C4 View**: A filtered projection of the canonical model at one C4 level (context, container, or component) for a specific persona; references the same model, not a copy.
- **Traceability Matrix**: A structured artifact (machine-readable) mapping every element to its requirements, provenance, and verdicts; generated deterministically from the canonical model.
- **Export Bundle**: The complete set of artifacts written to version control for one design at one version: JSON model, YAML model, DSL sources, diagram images (SVG + PNG per level), and stakeholder document.
- **Export Audit Entry**: An immutable record of an export action: actor, design ID, model version, export target path, and timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A complete stakeholder document for a design with up to 50 elements is generated and returned within 60 seconds of the request.
- **SC-002**: Per-persona views for all three C4 levels are produced from a single design model request without requiring any model duplication.
- **SC-003**: The traceability matrix accounts for 100% of design elements — every element appears either with its satisfied requirements or in the orphan section; no element is silently omitted.
- **SC-004**: A full export bundle (model JSON/YAML, 3 DSL files, 6 diagram images, 1 Markdown document) is written to version control within 120 seconds of confirmed export initiation.
- **SC-005**: An exported `model.json`, when re-imported, reconstructs a model that is element-for-element equivalent to the original with zero validation errors, verified in ≥ 99% of test cases.
- **SC-006**: Generated documents and traceability matrices are byte-identical for the same model version across repeated generation calls (deterministic output).

## Assumptions

- **Export trigger**: Export is on-demand — an Architect explicitly requests it and confirms. Export does NOT happen automatically when a design is approved. The approval action and the export action are separate, each requiring distinct human intent.
- **Version control system**: The target is git. Export writes files to a configured repository path on the local filesystem (or a mounted path). Remote push is out of scope for v1; the operator pushes after confirming the export locally.
- **Export directory structure**: `exports/{design_id}/v{model_version}/` within the configured repository root. One directory per (design, version) pair; existing directories at the same path are not overwritten.
- **Document format**: Markdown is the only human-readable output format for v1. Word (.docx) and PDF rendering are out of scope and deferred to v2 (requires additional rendering tooling and licensing considerations).
- **Diagram images**: SVG and PNG for each C4 level; produced by the rendering engine from ADP-SPEC-010. This feature consumes ADP-SPEC-010's output; it does not reimplement rendering.
- **Schema migration**: Basic "current version only" import is the v1 scope; a migration framework for older schema versions is v2. Re-import of artifacts at the current schema version must work; older versions that fail current schema validation return a clear error.
- **Traceability matrix format**: Machine-readable JSON (validated artifact) is the primary output; a human-readable Markdown rendering of the matrix is included in the stakeholder document as a section.
- **Access control**: Only users with the `architect` or `enterprise_architect` role can initiate an export. Document and view generation are available to all authenticated roles.
