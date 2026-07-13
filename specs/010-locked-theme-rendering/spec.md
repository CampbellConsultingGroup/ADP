# Feature Specification: Locked Visual Theme & Diagram Rendering

**Feature Branch**: `010-locked-theme-rendering`
**Created**: 2026-07-01
**Status**: Draft
**Input**: `/home/jmuir/projects/ADP/docs/010-locked-theme-rendering.md`

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this feature is fully spec-driven
- **ART-II** — Canonical Model as Single Source of Truth: rendering reads the canonical model and applies the locked theme at render time; styling is never stored in the model
- **ART-III** — Typed, Schema-Validated Records: the theme artifact validates against `c4-theme.schema.json`; the renderer rejects malformed themes
- **ART-IV** — Test-Driven Development: always applies
- **ART-XII** — Fixed Visual Language: the central article; no per-element or per-diagram style overrides are permitted; the locked theme is the sole source of visual style
- **ART-XIV** — Artifact Lineage: the theme artifact carries a version; every change is reviewable as an artifact diff

**ART-V (security)**: Low risk — rendering is read-only over the canonical model; the primary attack surface is malformed input. See Threat Model below.

**ART-VII (AI grounding)**: Not engaged — this feature has no LLM component.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Diagram images and Structurizr DSL produced from organizational architecture designs; the locked theme artifact.

**Trust boundaries crossed**: Internal service call (canonical model in → diagram source + images out); the theme artifact is loaded from the repository; no external user input reaches the theme.

**Abuse cases**:
- Malformed model submitted to renderer (elements with null names, invalid relationships): could cause renderer crash or hang → Mitigated by schema validation of the canonical model before rendering begins.
- Author supplies per-element style override in render request: could undermine visual consistency → Mitigated by FR-002 (renderer silently ignores any per-element or per-diagram style input).
- Unauthorized modification of the theme artifact: could introduce non-compliant styles → Mitigated by artifact versioning and review process (FR-005); the schema validator rejects a theme not marked `locked: true`.

**Residual risk**: Acceptable. This feature produces images from already-validated internal data; it introduces no new authentication surfaces, stores no credentials, and makes no external API calls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Render a Design to Diagram (Priority: P1)

An Architect has a saved design and needs to share or review it as a visual diagram. They request rendering for a specific design at a specific C4 level (context, container, or component). The system produces three outputs: a Structurizr DSL source file, an SVG image, and a PNG image. The resulting images apply the locked theme consistently — every Container element has the same fill color; every Person element has the same shape — regardless of who authored the design.

**Why this priority**: This is the core deliverable. Without rendering, the canonical model has no visual representation for review or sharing.

**Independent Test**: Provide a minimal valid design with one element of each type; request rendering at the container level; verify that Structurizr DSL source, SVG, and PNG are all emitted and that the element colors match the locked theme values exactly.

**Acceptance Scenarios**:

1. **Given** a valid design with at least one element of each type (Person, System, Container, Component), **When** a render is requested at the container level, **Then** the renderer emits Structurizr DSL source, an SVG, and a PNG — all three outputs successfully.
2. **Given** a render request, **When** output is produced, **Then** every Container element in the diagram has the identical fill, stroke, and text color defined in the locked theme entry for `container`.
3. **Given** two separate designs each containing a Container-kind element, **When** both are rendered, **Then** the Container elements are visually identical in both outputs.

---

### User Story 2 — Style Override Rejection (Priority: P1)

An author or automated tool passes per-element or per-diagram styling alongside a render request — for example, requesting that one element be highlighted in red. The renderer produces the diagram using only the locked theme; the attempted override has zero visible effect on the output.

**Why this priority**: Equal to US1 because without this guarantee the locked visual language (ART-XII) is not enforced, and organizational diagram consistency breaks down immediately.

**Independent Test**: Submit a render request carrying a per-element color override; verify the output diagram shows the theme-specified color, not the overridden color.

**Acceptance Scenarios**:

1. **Given** a render request carrying a per-element style override (e.g., fill `#FF0000` on one element), **When** rendered, **Then** the element appears with the theme-specified fill for its element type, not `#FF0000`.
2. **Given** a render request carrying a per-diagram color scheme override, **When** rendered, **Then** the output is identical to the same render request with no overrides.

---

### User Story 3 — Theme Validation and Schema Compliance (Priority: P2)

An Enterprise Architect needs confidence that the theme artifact in use is well-formed and explicitly marked as locked. When the theme is loaded, the system validates it against the theme schema. A theme that fails validation (missing a required field, not marked `locked: true`, or containing an unknown element type) is rejected before any rendering proceeds.

**Why this priority**: Schema validation prevents silent rendering errors from a corrupt or incomplete theme, but the feature can be demonstrated against a valid theme before the rejection paths are hardened.

**Independent Test**: Provide a theme file missing the `locked: true` field; request rendering; verify a validation error is returned and no diagram is produced.

**Acceptance Scenarios**:

1. **Given** the current locked theme artifact, **When** the schema validator is run, **Then** it reports valid with zero errors.
2. **Given** a theme artifact where `locked` is `false` or absent, **When** a render is requested, **Then** the renderer rejects the request with a clear validation error before producing any output.
3. **Given** a theme artifact missing a required element type entry (e.g., no `container` entry), **When** a render is requested, **Then** the renderer rejects with a schema validation error naming the missing entry.

---

### User Story 4 — Versioned Theme Change (Priority: P2)

The visual language requires a deliberate update (e.g., the brand color for Container elements changes). An Enterprise Architect updates the theme artifact, bumps its version number, and commits the change. The change is reviewable as a diff; the previous version is not overwritten in-place without a version increment.

**Why this priority**: Theme history and auditability are important organizational controls but do not block diagram rendering for the initial MVP.

**Independent Test**: Make a change to one element type's fill color in the theme artifact; verify the version field increments; verify the diff shows only the intended color change; verify the updated theme passes schema validation.

**Acceptance Scenarios**:

1. **Given** the current theme at version `1.0.0`, **When** a fill color for one element type is changed, **Then** the theme version field is incremented (e.g., to `1.1.0`).
2. **Given** a theme change is committed, **When** reviewed as an artifact diff, **Then** the diff shows only the intended modification and no other changes.
3. **Given** the updated theme, **When** schema validation is run, **Then** it passes with zero errors.

---

### Edge Cases

- What happens when the model has elements but no relationships? Renderer must still produce valid output (a diagram with isolated nodes, no edges).
- What happens when the model is empty (no elements)? Renderer must return a validation error rather than an empty diagram file.
- What happens when the theme is missing an entry for an element type present in the model? Renderer must reject with a clear error identifying the missing type rather than silently using a default.
- What happens when two elements have identical names in the same design? Renderer must disambiguate in the DSL output; output must remain valid Structurizr DSL.
- What happens when the Structurizr tooling is unavailable? Renderer must return a clear infrastructure error; no partial output is emitted (all-or-nothing).
- What happens when a render is requested for a design that no longer exists? Renderer must return a clear "not found" error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The locked theme MUST map every `ElementType` (`person`, `system`, `container`, `component`) to fill color, stroke color, text color, and shape; the theme MUST be marked `locked: true`.
- **FR-002**: The renderer MUST apply only the locked theme; it MUST NOT apply per-diagram or per-element style overrides even if supplied in the render request; any supplied overrides MUST be silently ignored.
- **FR-003**: The renderer MUST emit Structurizr DSL source as a machine-readable artifact AND produce an SVG file AND a PNG file from that source.
- **FR-004**: The theme MUST carry a version field and MUST validate against `c4-theme.schema.json`; a theme that fails validation MUST be rejected before rendering begins, with an error identifying the failing constraint.
- **FR-005**: A change to the theme MUST increment the version field; the version history MUST be reviewable as artifact diffs in version control.
- **FR-006**: Datastores (when rendered as a distinct shape) MUST be distinguishable from other element types by shape alone so that greyscale or color-blind viewing remains unambiguous.

### Key Entities

- **Locked Theme** (`c4-theme.json`): Versioned mapping from `ElementType` to visual properties (fill, stroke, text color, shape). Marked `locked: true`. The single source of visual truth for all rendered diagrams.
- **Theme Schema** (`c4-theme.schema.json`): Formal schema defining required fields, permitted element types, and the `locked` flag constraint. Used to validate the theme before any rendering.
- **Diagram Source** (Structurizr DSL): Machine-readable, version-controllable text artifact produced by the renderer from the canonical model. Serves as the intermediate representation before image generation.
- **Rendered Diagram**: Visual output produced from the Structurizr DSL in two formats: SVG (web embedding, scalable) and PNG (document export).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given any two designs containing the same element type, when both are rendered, the elements of that type are visually identical — same fill, stroke, and text color — in 100% of cases.
- **SC-002**: A render request for a design with up to 50 elements produces all three outputs (DSL, SVG, PNG) within 30 seconds end-to-end.
- **SC-003**: Theme schema validation completes and returns a pass/fail result within 2 seconds for any theme artifact.
- **SC-004**: Per-element style overrides supplied in a render request have zero visible effect on the rendered output — 0% of supplied overrides alter the diagram appearance.
- **SC-005**: All body text in rendered diagrams meets a minimum contrast ratio of 4.5:1 (WCAG AA normal text) between text color and element background color for every element type defined in the locked theme.
- **SC-006**: The Structurizr DSL output for the same model and theme version is byte-identical across repeated render calls on the same platform (deterministic rendering).

## Assumptions

- **Accessibility theme variant**: A high-contrast or accessibility theme variant is out of scope for v1. When a second locked theme is needed (e.g., for accessibility compliance mandates), it will be introduced as a new versioned theme artifact in a separate spec. The single baseline locked theme is the only theme for this spec.
- **Structurizr DSL tooling**: The Structurizr DSL command-line tooling must be available in the deployment environment to produce SVG/PNG from DSL source. The renderer depends on this external tool.
- **Rendering trigger**: Rendering is on-demand (synchronous request/response). Background pre-rendering and watch-mode are out of scope.
- **C4 level as render parameter**: The C4 level (context, container, component) is a required parameter to the render call. Level projection is handled by ADP-SPEC-009's filter logic; the renderer applies it before generating DSL.
- **Output formats**: SVG and PNG are the two required image formats. PDF export is out of scope for this spec (deferred to ADP-SPEC-011 document export bundling).
- **Model source**: The renderer reads from the ADP canonical model store (ADP-SPEC-002); the model is fully persisted before rendering is requested.
- **Theme artifact location**: The theme artifact lives in the repository; its version history is tracked via git. No database storage of the theme is required for v1.
- **WCAG level**: The locked theme targets WCAG AA contrast compliance (4.5:1 for normal text). WCAG AAA is aspirational and not a blocking requirement for v1.
