# Phase 0 Research: Diagram Types Beyond C4

The spec's Input named a sibling project's diagramming library as reusable but did not give its exact location; the location was resolved this session as `/home/jmuir/projects/canvas` (a real, git-tracked monorepo: `packages/diagram-core` + `apps/web` + `apps/api`). Every decision below is grounded in directly reading that repo's source, not the spec's general description alone.

## Decision 1: Vendor (copy) the reusable source into ADP, not a live cross-repo dependency

**Decision**: Copy `packages/diagram-core`'s TypeScript source and the confirmed-portable pieces of `apps/web/src/canvas` into a new `web/src/diagrams/` module inside ADP's own repo, becoming ADP-owned code from that point forward — not an npm dependency pointing at the sibling repo's path, and not a git submodule.

**Rationale**:
- `packages/diagram-core`'s own `package.json` has `"private": true` and no publish config — there is no registry to depend on cleanly (`npm install @canvas/diagram-core` resolves nowhere outside that monorepo's own workspace).
- A `file:../../../canvas/packages/diagram-core` path dependency would make ADP's build depend on a sibling repository existing at an identical relative path on every machine/CI runner — directly violating ART-XIV ("builds MUST be reproducible from a clean checkout"). ADP's CI (`drift-check.yml`) checks out only the ADP repository.
- The library is small (one `src/` tree, two runtime dependencies) and its own test suite (55 test files) is the confirmation it's mature and stable — the standard downside of vendoring (losing automatic upstream sync) is low-cost here, and the standard upside (a self-contained, CI-reproducible ADP repo) is exactly what this project's own constitution already requires elsewhere.

**Alternatives considered**:
- **Git submodule**: rejected — same reproducibility problem as a `file:` dependency (a submodule still requires network/path access to the sibling repo at checkout time in CI), plus submodules are a known source of contributor friction in this kind of solo/small-team project.
- **Publish `@canvas/diagram-core` to a private npm registry ADP could depend on normally**: rejected as out of scope for this feature — stands up new registry infrastructure (and its own auth/billing/maintenance surface) to solve a one-time integration, when a straightforward vendor-copy solves it today with strictly less new infrastructure.

## Decision 2: Parsing, validation, and SVG rendering happen entirely client-side; the backend treats DSL source as opaque stored text

**Decision**: The vendored `dslFamilies` registry (`parse`/`serialize` per family), `escapeXml`-hardened `svg-renderer.ts`, and `auto-layout.ts` (dagre-based) all run in the browser, exactly as they already do in the sibling project's own `apps/web`. ADP's Python backend never parses, validates, or renders diagram DSL — it stores the DSL source string as-is (with a size cap, not a syntax check) and returns it as-is on read.

**Rationale**: The sibling library is TypeScript with zero server-side coupling by design (confirmed directly: `packages/diagram-core`'s only runtime dependencies are `@dagrejs/dagre` and `yaml`, both pure JS). ADP's backend is Python. Porting parser/serializer/renderer logic for five DSL families into Python would mean re-implementing and re-testing everything the sibling project's 55 test files already prove, for zero product benefit and real, ongoing double-maintenance risk. Confirmed directly in the sibling repo's own architecture: its Fastify backend (`apps/api`) does not parse DSL either — it persists it and (separately, see Decision 4) converts already-rendered SVG to PNG server-side. ADP already has an identical precedent for "complex interactive editing lives entirely client-side, backend just stores the result": the existing C4 canvas (`web/src/canvas/C4Canvas.tsx` + React Flow) edits interactively in the browser; the backend stores the resulting `ArchitectureDescription`, it doesn't re-derive or validate the diagram's visual layout server-side.

**Alternatives considered**:
- **Port the parsers to Python for server-side validation**: rejected — the exact "redundant, error-prone, works against the whole point of reuse" outcome Decision 1 already argues against, now applied to logic instead of packaging.
- **Run the TypeScript library server-side via a Node subprocess/sidecar from the Python backend**: rejected — a new runtime dependency (Node available in the Python container) and process-management surface for a capability the browser already provides directly and more simply; no other part of ADP's backend does this.

## Decision 3: Server-side PNG export reuses ADP's existing `cairosvg` dependency, not the sibling project's `resvg-js`

**Decision**: A single new backend endpoint accepts a browser-rendered SVG string and returns PNG bytes via `cairosvg` — the same library ADP's own C4 pipeline (`adp.renderer`) already uses for SVG→PNG conversion (ADP-SPEC-010).

**Rationale**: The sibling project's PNG export (`ExportMenu.tsx`'s only backend-coupled call, confirmed via direct source read) uses `@resvg/resvg-js`, a Node native/WASM binding — unusable from Python. Rather than leaving PNG export unbuilt (SVG-only, which the spec's own Success Criteria already treat as the sufficient v1 bar) or introducing a second, different SVG→PNG toolchain, reusing `cairosvg` costs almost nothing: it's already a project dependency, already proven on this exact conversion direction, and keeps ADP's PNG-generation story singular rather than split across two different libraries doing the same job for two different diagram families.

**Alternatives considered**:
- **Skip PNG entirely for v1**: genuinely viable (SC-002 only requires SVG) but rejected once the near-zero marginal cost of reusing an already-present dependency was clear — no reason to leave value on the table this cheaply.
- **Port `@resvg/resvg-js`'s usage pattern via a Node sidecar**: rejected for the same reasons as Decision 2's rejected Node-subprocess alternative.

## Decision 4: New standalone `diagrams` table and `adp.diagrams` backend package, mirroring the established per-domain module convention

**Decision**: One new table (`diagrams`: `id`, `title`, `diagram_type`, `dsl_source`, `created_by`, `created_at`, `updated_at`) via a new Alembic migration, plus a new `adp.diagrams` package (`models.py`, `store.py`, `router.py`) following the exact shape of every other ADP domain module (`adp.business`, `adp.application`, etc.). No `design_id` column or foreign key (FR-011 — standalone in v1).

**Rationale**: Matches this codebase's own established pattern precisely rather than introducing a new one; the "standalone, no Design coupling" decision from the spec's Clarifications directly determines the table has no FK to `designs` at all — the simplest possible schema for what v1 actually needs.

**Alternatives considered**: None seriously — this is a direct application of an already-proven pattern, not a new design question.

## Decision 5: RBAC reuses the existing `ActionType`/`PersonaRole` mechanism with one new action, no new mechanism

**Decision**: Add `WRITE_DIAGRAM` to `adp.authz.roles.ActionType`. Grant it explicitly to `SOLUTION_ARCHITECT` and `TECHNICAL_ARCHITECT` (mirroring exactly how `WRITE_APPLICATION` is granted to those two roles today); `ENTERPRISE_ARCHITECT` receives it automatically via its existing `frozenset(ActionType) - {MANAGE_AGENT_PROMPTS}` wildcard grant, requiring no code change there. `REVIEWER` does not receive it — read access to `GET /diagrams` endpoints stays ungated (matching how general reads work elsewhere in ADP; only sensitive categories like `READ_APPLICATION_RISK` get a dedicated read gate, and nothing about a diagram's content is sensitive in that sense). `PERMISSIONS_VERSION` bumps from `1.7.0` to `1.8.0`.

**Rationale**: Directly satisfies FR-008 ("reuse ADP's existing role-based access control... no new permission model") by construction — confirmed against the actual `permissions.py` grant table and its documented precedent (the `WRITE_BUSINESS_ARCH`/`WRITE_APPLICATION` additions at version `1.1.0` used the identical shape).

**Alternatives considered**: None — FR-008 already rules out inventing a new mechanism; this is the direct, minimal application of the existing one.

## Decision 6: Vendor `diagram-core`'s icon libraries and its C4 DSL family too, but never expose the C4 family in ADP's UI

**Decision**: Copy `packages/diagram-core/src/libraries/*` (icon libraries + the ingestion-time `svg-sanitizer.ts`) and `src/dsl/c4.ts` in full, unmodified, alongside the five families ADP actually needs (flowchart, sequence, erd, uml, architecture). ADP's diagram-type picker (FR-001) offers only the five non-C4 types; the vendored `c4` DSL family and `c4-notation.ts` library exist in the copied source but are never registered in any ADP-facing type picker or route.

**Rationale**: `packages/diagram-core`'s own `dslFamilies` registry and `index.ts` export surface treat all six families as one cohesive package with no natural seam to cleanly exclude just the C4 family — vendoring the whole `src/` tree unmodified keeps the copy a faithful, low-diff mirror of the upstream source (easier to compare against or re-sync from later) rather than a divergent fork. This is a purely inert inclusion: ADP's own `ArchitectureDescription`/C4 canvas/`adp.renderer` remain completely untouched per the spec's Assumptions, and no ADP code path ever calls the vendored `parseC4`/`serializeC4` functions.

**Alternatives considered**: **Strip the C4 family and icon-library C4-notation code out during vendoring.** Rejected — the effort of surgically removing one family from a registry-keyed module (and keeping that removal in sync on any future re-vendor) outweighs the cost of a few genuinely inert, unregistered exports.

## Verified security property (informs Threat Model, not a new decision)

Directly confirmed by reading `render/svg-renderer.ts`: every piece of user-supplied text that reaches the rendered SVG (node labels, container labels, element IDs) passes through a local `escapeXml()` function before being written into `<text>`/`<tspan>` elements or `data-*` attributes. This is the concrete basis for the spec's Threat Model claim that content-injection risk is mitigated by "the reused library's own SVG renderer" — verified directly, not assumed from the spec author's description.
