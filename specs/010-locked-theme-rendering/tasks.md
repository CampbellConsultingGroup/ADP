# Tasks: Locked Visual Theme & Diagram Rendering

**Input**: Design documents from `/specs/010-locked-theme-rendering/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST fail before implementation begins.

**Note**: Pure Python feature — no Docker, no Java required. `cairosvg` is the only new dependency. All modules live in `src/adp/theme/` (new) and `src/adp/renderer/` (new) with a new FastAPI router at `src/adp/api/routers/render.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no file conflicts)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in every description

---

## Phase 1: Setup

**Purpose**: Install new dependency, create package skeletons

- [X] T001 Add `cairosvg>=2.7` to `pyproject.toml` dependencies section and install with `pip install cairosvg --break-system-packages`; verify `python3 -c "import cairosvg; print('ok')"` succeeds (requires `libcairo2` system library — WSL: `sudo apt-get install -y libcairo2-dev` if missing)
- [X] T002 [P] Create `src/adp/theme/__init__.py` as an empty package marker
- [X] T003 [P] Create `src/adp/renderer/__init__.py` as an empty package marker

**Checkpoint**: `python3 -c "import cairosvg, adp.theme, adp.renderer; print('ok')"` succeeds

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic models, schema generation, theme artifact, loader, and WCAG contrast — all must exist before any renderer can be built

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create Pydantic v2 models in `src/adp/theme/models.py`: `ElementStyle` (fill, stroke, color, shape, font_size, font_weight — all required; hex colors validated with `^#[0-9A-Fa-f]{6}$` pattern; `shape: Literal["box","actor","cylinder","hexagon"]`); `RelationshipStyle` (stroke, stroke_width, arrow_end); `LockedTheme` (version, `locked: Literal[True]`, `styles: dict[str, ElementStyle]`, relationship_style — all with `model_config = ConfigDict(extra="forbid")`); `ThemeValidationError(ValueError)` custom exception class; `RenderRequest(BaseModel, extra="forbid")` with only `level: C4Level` field; `RenderResult(BaseModel, extra="forbid")` with design_id, level, dsl, svg, png_base64 str fields
- [X] T005 Extend `src/adp/generate.py` to also emit `src/adp/theme/c4-theme.schema.json` from `LockedTheme.model_json_schema()`: add `generate_theme_schema(check: bool = False)` function called from the existing `generate()` function; in `--check` mode, compare the generated schema against the committed file and exit nonzero if different (same pattern as existing `architecture-description.schema.json` generation); run `adp-generate` after this task to produce the initial `c4-theme.schema.json`
- [X] T006 [P] Author `src/adp/theme/c4-theme.json` with the baseline locked C4 theme per `contracts/theme-artifact-contract.md`: version `"1.0.0"`, `"locked": true`, styles for all four element kinds (person: `#08427B`/`#073B6F`/`#ffffff`/actor/14/normal; system: `#1168BD`/`#0E5FA3`/`#ffffff`/box/14/bold; container: `#438DD5`/`#3C7FC0`/`#ffffff`/box/13/normal; component: `#85BBE0`/`#78A8CC`/`#000000`/box/12/normal), relationship_style `stroke:#707070 stroke_width:1.5 arrow_end:open`
- [X] T007 Create `src/adp/theme/contrast.py` with `compute_contrast_ratio(fg_hex: str, bg_hex: str) -> float` implementing the WCAG 2.1 relative luminance formula: parse hex to sRGB floats (0–1), linearize each channel (`c/12.92` if `c<=0.04045` else `((c+0.055)/1.055)^2.4`), compute luminance `L = 0.2126*R + 0.7152*G + 0.0722*B`, return `(max(L1,L2)+0.05)/(min(L1,L2)+0.05)`; no external deps
- [X] T008 Create `src/adp/theme/loader.py` with `ThemeLoader` class: `THEME_PATH` constant pointing to `c4-theme.json` relative to the module; `SCHEMA_PATH` constant pointing to `c4-theme.schema.json`; `load() -> LockedTheme` reads JSON, calls `validate_raw()`, constructs and returns `LockedTheme(**data)`; `validate_raw(data: dict) -> None` calls `jsonschema.validate(data, schema)` and raises `ThemeValidationError` with the failing constraint name on `jsonschema.ValidationError`; `load_and_validate() -> LockedTheme` convenience wrapper; raises `ThemeValidationError` (NOT a 500) for any validation failure

**Checkpoint**: `adp-generate --check` exits 0 with both `architecture-description.schema.json` and `c4-theme.schema.json` up-to-date; `python3 -c "from adp.theme.loader import ThemeLoader; t = ThemeLoader().load(); print(t.version)"` prints `1.0.0`

---

## Phase 3: User Story 1 — Render a Design to Diagram (Priority: P1) 🎯 MVP

**Goal**: Given a valid design, the renderer produces Structurizr DSL source, an SVG, and a PNG — all three outputs — with element styling from the locked theme.

**Independent Test**: Provide a `ArchitectureDescription` fixture with one element of each kind; call the render endpoint; verify `dsl`, `svg`, and `png_base64` are non-empty strings; verify the SVG `fill` attribute for a container element matches `#438DD5`.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Write failing `test_design_to_dsl_contains_element_names()` in `tests/unit/test_dsl_generator.py`: construct an `ArchitectureDescription` with a system element named "Web App" and a container named "API Gateway"; call `design_to_dsl(design, mock_theme, "container")` (note: `theme` is now the second parameter per I1 fix); assert "Web App" and "API Gateway" appear in the returned DSL string; assert "workspace" appears (valid DSL root keyword); assert the container fill color `#438DD5` appears in the DSL styles block (theme-dynamic, not hardcoded)
- [X] T010 [P] [US1] Write failing `test_design_to_svg_contains_theme_fill_color()` in `tests/unit/test_svg_generator.py`: construct a design with one container element; call `design_to_svg(design, theme, "container")`; assert the string `#438DD5` appears in the SVG (container fill); assert `<svg` and `</svg>` tags are present
- [X] T011 [P] [US1] Write failing `test_two_designs_render_identical_element_colors()` in `tests/unit/test_svg_generator.py`: create two separate designs each with one container element (different names, different ids); call `design_to_svg()` on each; assert both SVGs contain exactly the same fill value for container (`#438DD5`); this verifies SC-001
- [X] T012 [P] [US1] Write failing `test_render_endpoint_returns_all_three_outputs()` in `tests/contract/test_render_api.py`: POST `{"level": "container"}` to `/api/v1/designs/{design_id}/render` via TestClient with a design pre-loaded in the mock store; assert 200; assert response JSON has `dsl` (non-empty str), `svg` (starts with `<svg`), `png_base64` (valid base64 string); this is the acceptance test for US1

### Implementation for User Story 1

- [X] T013 [US1] Create `src/adp/renderer/dsl.py` with `design_to_dsl(design: ArchitectureDescription, theme: LockedTheme, level: C4Level) -> str`: apply `filterElementsForLevel` (import from `adp.models` or inline the kind mapping); generate Structurizr DSL with a `workspace` block, `model` block with one entry per visible element (using element `id` as DSL identifier, `name` as display name), `views` block with a level-appropriate view type (context/container/component), and `styles` block writing theme colors **dynamically from `theme.styles[kind].fill/.stroke/.color`** for each element kind (NOT hardcoded — so a theme version bump is immediately reflected in DSL output and DSL stays in sync with SVG output); verify T009 passes; also update T016 (orchestrator) to pass `theme` to `design_to_dsl()`
- [X] T014 [US1] Create `src/adp/renderer/svg.py` with `design_to_svg(design: ArchitectureDescription, theme: LockedTheme, level: C4Level, positions: dict[str, dict[str, float]] | None = None) -> str`: apply level filter to get visible elements and relationships; compute positions from grid auto-layout (4 columns, 200×120px cells, 20px margin; stable sort by element id for determinism); if `positions` provided, use them as overrides per element id; generate SVG XML with `<rect>` per element (fill/stroke from theme by kind), `<text>` labels, `<line>` arrows for relationships with open arrowhead markers, `<defs>` block with arrowhead marker; return complete SVG string; verify T010 and T011 pass
- [X] T015 [US1] Create `src/adp/renderer/png.py` with `svg_to_png(svg_str: str) -> bytes`: call `cairosvg.svg2png(bytestring=svg_str.encode("utf-8"))` and return the PNG bytes; raise `RuntimeError("PNG conversion failed")` if cairosvg raises
- [X] T016 [US1] Create `src/adp/renderer/orchestrator.py` with `RenderOrchestrator`: `__init__(self, design_store, theme_loader: ThemeLoader | None = None)`; `render(self, design_id: str, level: C4Level) -> RenderResult`: loads theme via `ThemeLoader().load_and_validate()`, fetches design from store, calls `design_to_dsl(design, theme, level)`, `design_to_svg(design, theme, level)`, `svg_to_png()`, returns `RenderResult(design_id=design_id, level=level, dsl=dsl, svg=svg, png_base64=base64.b64encode(png).decode())`

### US2 Override-Rejection Tests — Write BEFORE T017 (ART-IV / C2 fix)

> **These tests must exist and FAIL before T017 creates the endpoint. They fail because the route does not yet exist (404). Once T017 adds `RenderRequest(extra="forbid")`, they pass.**

- [X] T018 [P] [US2] Write failing `test_render_rejects_extra_style_fields()` in `tests/contract/test_render_api.py`: POST `{"level": "container", "fill": "#FF0000"}` to the render endpoint; assert 422; assert response body mentions the unexpected field (Pydantic extra="forbid" error message)
- [X] T019 [P] [US2] Write failing `test_render_rejects_per_diagram_override()` in `tests/contract/test_render_api.py`: POST `{"level": "container", "color_scheme": "dark", "override_theme": true}` to render endpoint; assert 422 for each unknown field
- [X] T020 [P] [US2] Write failing `test_svg_generator_has_no_override_parameters()` in `tests/unit/test_svg_generator.py`: use `inspect.signature(design_to_svg)` to get the function parameter names; assert none of `{"style", "color", "fill", "stroke", "override", "custom_theme"}` appear as parameter names; this enforces ART-XII at the function signature level
- [X] T021 [P] [US2] Write failing `test_same_kind_same_output_regardless_of_content()` in `tests/unit/test_svg_generator.py`: create two Container elements with different names and descriptions; render both separately; extract fill attribute for each from their SVGs; assert both fills equal `#438DD5` — confirms SC-004 (0% override effect) at unit level

- [X] T017 [US1] Create `src/adp/api/routers/render.py` with FastAPI router: `POST /api/v1/designs/{design_id}/render` accepts `RenderRequest(extra="forbid")` body (only `level: C4Level` field — `# ART-XII / FR-002: no style override fields; any extra field → 422`); handles `ThemeValidationError` → 422; handles design not found → 404; calls `RenderOrchestrator`; returns `RenderResult`; **emit structured log at request entry**: `logger.info({"event": "render.start", "design_id": design_id, "level": request.level, "correlation_id": req.headers.get("X-Correlation-ID", str(uuid.uuid4()))})` using `logging.getLogger(__name__)` (satisfies ART-VI / QG-10); register router in `src/adp/api/app.py`; verify T012, T018, T019 pass

**Checkpoint**: `pytest tests/unit/test_dsl_generator.py tests/unit/test_svg_generator.py tests/contract/test_render_api.py -v --no-cov` all green; render pipeline produces DSL + SVG + PNG from a design fixture

---

## Phase 4: User Story 2 — Style Override Rejection (Priority: P1)

**Goal**: Any attempt to pass per-element or per-diagram style overrides in a render request is rejected with 422 before reaching the renderer.

**Independent Test**: POST `{"level": "container", "fill": "#FF0000"}` to the render endpoint; assert 422. Verify the SVG for any render call contains only the theme-specified fill color.

> **Tests T018–T021 were written in Phase 3 (before T017) to satisfy ART-IV red-first. This phase contains only the verification step.**

### Implementation for User Story 2

- [X] T022 [US2] Run T018–T021 and confirm all pass following T017's implementation; assert `inspect.signature(design_to_svg).parameters` contains none of `{"style","color","fill","stroke","override","custom_theme"}`; assert `inspect.signature(design_to_dsl).parameters` also has none of those names; this is the static ART-XII compliance verification at the function-signature level (zero code to write — implementation was enforced in T014, T013, T017)

**Checkpoint**: `pytest tests/contract/test_render_api.py tests/unit/test_svg_generator.py -v --no-cov` green; zero style controls accessible via API or function signatures

---

## Phase 5: User Story 3 — Theme Validation and Schema Compliance (Priority: P2)

**Goal**: A malformed theme (missing `locked: true`, missing element kind, invalid color) is rejected with a descriptive error before any rendering occurs.

**Independent Test**: Call `ThemeLoader().validate_raw({"version": "1.0.0", "locked": False, "styles": {}, "relationship_style": {}})` and assert `ThemeValidationError` is raised with the failing constraint identified.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T023 [P] [US3] Write failing `test_valid_theme_passes_validation()` in `tests/unit/test_theme_loader.py`: call `ThemeLoader().load_and_validate()` (uses production `c4-theme.json`); assert no exception raised; assert returned theme has `locked == True` and `version == "1.0.0"`
- [X] T024 [P] [US3] Write failing `test_theme_locked_false_rejected()` in `tests/unit/test_theme_loader.py`: construct a theme dict with `"locked": false`; call `ThemeLoader().validate_raw(data)` (after temporarily patching the schema or using a minimal valid dict with locked=False); assert `ThemeValidationError` is raised; assert error message mentions `"locked"`
- [X] T025 [P] [US3] Write failing `test_theme_missing_element_kind_rejected()` in `tests/unit/test_theme_loader.py`: construct a theme dict missing the `"container"` key in `styles`; call `ThemeLoader().validate_raw(data)`; assert `ThemeValidationError` is raised
- [X] T026 [P] [US3] Write failing `test_render_endpoint_returns_422_on_bad_theme()` in `tests/contract/test_render_api.py`: patch `ThemeLoader.load_and_validate` to raise `ThemeValidationError("Theme invalid: missing container")`; POST a valid render request; assert 422 response; assert response body contains `"Theme"` in the detail message

### Implementation for User Story 3

- [X] T027 [US3] Verify `ThemeLoader` in `src/adp/theme/loader.py` (built in T008): confirm `validate_raw()` uses `jsonschema.validate()` correctly and catches `jsonschema.ValidationError` to re-raise as `ThemeValidationError` with `failing_constraint=err.validator`; confirm `load()` calls `validate_raw()` before constructing the Pydantic model; add `ThemeValidationError` handler in `src/adp/api/routers/render.py` (`except ThemeValidationError as e: raise HTTPException(status_code=422, detail=str(e))`); verify T023–T026 pass

**Checkpoint**: `pytest tests/unit/test_theme_loader.py tests/contract/test_render_api.py -v --no-cov` green; bad theme inputs cause 422, not 500

---

## Phase 6: User Story 4 — Versioned Theme Change (Priority: P2)

**Goal**: Every change to `c4-theme.json` increments the version; the schema is stable; WCAG AA contrast ratios are verified automatically so a theme change that breaks contrast is caught in CI.

**Independent Test**: Load the current theme; verify version matches semver pattern; compute contrast ratio for each element kind and assert ≥ 4.5:1.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T028 [P] [US4] Write failing `test_theme_version_is_semantic_version()` in `tests/unit/test_theme_loader.py`: load theme via `ThemeLoader().load()`; assert `re.match(r'^\d+\.\d+\.\d+$', theme.version)` is truthy; also assert `theme.version == "1.0.0"` as a regression anchor
- [X] T029 [P] [US4] Write failing `test_theme_wcag_aa_contrast_sc005()` in `tests/unit/test_theme_contrast.py`: import `compute_contrast_ratio` from `src/adp/theme/contrast.py` and `ThemeLoader`; for each element kind in the loaded theme, compute `compute_contrast_ratio(style.color, style.fill)` and assert `>= 4.5` with message f"{kind}: contrast ratio {ratio:.2f}:1 is below WCAG AA minimum (4.5:1)"; this is the SC-005 CI regression guard
- [X] T030 [P] [US4] Write failing `test_adp_generate_check_includes_theme_schema()` in `tests/unit/test_generate.py`: import `generate` function from `src/adp/generate.py`; call `generate(check=True)` (or check mode); assert it does NOT raise; verify `src/adp/theme/c4-theme.schema.json` exists and is valid JSON; verify its content matches `LockedTheme.model_json_schema()` (drift test at the Python level)
- [X] T031 [P] [US4] Write failing `test_compute_contrast_ratio_known_values()` in `tests/unit/test_theme_contrast.py`: verify the formula against known values — `compute_contrast_ratio("#ffffff", "#000000")` ≈ 21.0; `compute_contrast_ratio("#ffffff", "#08427B")` is between 10.0 and 12.0; `compute_contrast_ratio("#ffffff", "#438DD5")` is between 4.4 and 5.0 (the tight container case)

### Implementation for User Story 4

- [X] T032 [US4] Confirm `src/adp/generate.py` extended in T005 correctly regenerates `src/adp/theme/c4-theme.schema.json` and verifies it in `--check` mode; confirm `src/adp/theme/contrast.py` implemented in T007 produces the correct ratios; verify T028–T031 all pass; document the theme change process in a code comment in `src/adp/theme/c4-theme.json` pointing to `contracts/theme-artifact-contract.md`

**Checkpoint**: `pytest tests/unit/test_theme_loader.py tests/unit/test_theme_contrast.py tests/unit/test_generate.py -v --no-cov` green; `adp-generate --check` exits 0; WCAG contrast ratios for all element kinds confirmed ≥ 4.5:1

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration test, coverage, lint, and final verification

- [X] T033 Write `tests/integration/test_render_e2e.py` with `test_full_render_pipeline()`: construct a `ArchitectureDescription` with all four element kinds and two relationships (no database required — in-process); call `RenderOrchestrator(design_store=MockStore()).render("D-001", "container")`; assert `result.dsl` is non-empty and contains element names; assert `result.svg` starts with `<svg` and contains `#438DD5` (container fill); assert `result.png_base64` decodes to valid PNG bytes (check first 8 bytes for PNG magic `\x89PNG`); assert DSL is deterministic (render twice, compare strings)
- [X] T034 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — assert all unit and contract tests pass; fix any regressions in the 257 existing Python tests
- [X] T035 [P] Run `ruff check src/adp/theme/ src/adp/renderer/ src/adp/api/routers/render.py` — fix all lint errors; also `ruff check src/adp/generate.py` since T005 modified it
- [X] T036 [P] Run `adp-generate --check` — verify exit 0; confirm both `architecture-description.schema.json` and `c4-theme.schema.json` are drift-free
- [X] T037 [P] Run `pytest tests/ --ignore=tests/integration --cov=adp --cov-report=term-missing -q` and assert coverage ≥ 85% for `adp.theme` and `adp.renderer` modules; add targeted tests for any uncovered branches (e.g., empty design, `cairosvg` error path, grid overflow > 4 columns)
- [X] T038 [P] Write `tests/unit/test_render_performance.py` to satisfy SC-002 and SC-003: (a) `test_sc002_render_50_elements_under_30s()` — construct an `ArchitectureDescription` fixture with 50 container elements and 10 relationships; instantiate `RenderOrchestrator` with a mock store returning this design; call `render("D-001", "container")`; assert elapsed `time.perf_counter()` ≤ 30.0 seconds (b) `test_sc003_theme_validation_under_2s()` — call `ThemeLoader().load_and_validate()` once; assert elapsed time ≤ 2.0 seconds; run with `pytest tests/unit/test_render_performance.py -v --no-cov` to ensure timing assertions are in the baseline test suite and visible in CI output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories; `LockedTheme` models and `ThemeLoader` must exist before any renderer
- **US1 (Phase 3)**: Depends on Foundational — 🎯 MVP; produces all three render outputs
- **US2 (Phase 4)**: Tests T018–T021 written in Phase 3 (before T017, per ART-IV red-first); T022 (verification) depends on T017 complete
- **US3 (Phase 5)**: Depends on Foundational (`ThemeLoader` exists); independently testable
- **US4 (Phase 6)**: Depends on Foundational (models and generate.py extension exist); independently testable
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — core render pipeline
- **US2 (P1)**: Depends on US1's `RenderRequest` model; tests (T018–T021) can start from Phase 2 since they just test rejection behavior
- **US3 (P2)**: Can start after Foundational (ThemeLoader exists); independent of US1/US2
- **US4 (P2)**: Can start after Foundational (models + generate.py); independent of US1–US3

### Parallel Opportunities

- T002, T003 (Setup): parallel — different package files
- T006, T007 (Foundational): parallel — different files
- T009, T010, T011, T012 (US1 tests): parallel — independent test functions
- T018, T019, T020, T021 (US2 tests — in Phase 3 before T017): parallel — independent test functions
- T023, T024, T025, T026 (US3 tests): parallel — independent test functions
- T028, T029, T030, T031 (US4 tests): parallel — independent test functions
- T034, T035, T036, T037 (Polish): parallel — independent tooling

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1 + 2 → Models, schema, theme artifact, loader, contrast function
2. Phase 3 (US1) → DSL generator + SVG generator + PNG converter + render endpoint
3. **STOP and VALIDATE**: `curl -X POST .../render -d '{"level":"container"}'` returns DSL + SVG + PNG

### Incremental Delivery

1. Setup + Foundational → Models + theme artifact + loader ready
2. US1 → Render pipeline working (MVP)
3. US2 → Override rejection verified (already enforced; tests confirm)
4. US3 → Theme validation hardened
5. US4 → WCAG SC-005 + version + generate --check wired up
6. Polish → Coverage + lint + E2E integration test

---

## Notes

- [P] tasks = different files, no dependencies between them
- Tests MUST fail before implementation (ART-IV); commit failing tests first
- `LockedTheme.locked: Literal[True]` means Pydantic itself rejects `locked=false` — ART-XII enforced at the type level
- `RenderRequest.extra="forbid"` means FastAPI rejects any style override field before the renderer is called — no defensive programming needed in the renderer
- The SVG generator has NO style override parameters (T020 verifies this via `inspect.signature`)
- `adp-generate --check` must remain exit 0 throughout — T005 extends it, not replaces it
- `cairosvg` requires `libcairo2` system library (standard WSL/Debian package); if missing, T001 installation step will fail with a clear error
- SC-006 (deterministic rendering) is enforced by stable-sort by element id in `design_to_svg()` and tested in T033
