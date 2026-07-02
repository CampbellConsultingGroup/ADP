# Research: Document, View & Export Generation

**Branch**: `011-document-export` | **Date**: 2026-07-02

---

## Decision 1: YAML Serialization for `model.yaml` Export

**Decision**: Use `pyyaml>=6.0` (new dependency) for writing `model.yaml`. Specifically `yaml.dump(data, default_flow_style=False, sort_keys=True, allow_unicode=True)` applied to the Pydantic model's `model_dump()` output.

**Rationale**: `python-frontmatter` (already in project) depends on PyYAML, so adding `pyyaml` as an explicit pin costs nothing. `ruamel.yaml` preserves comments and ordering better but is significantly heavier. For machine-readable export artifacts that will be consumed by scripts or diffed in git, PyYAML's clean, sorted-key output is preferable. Stable-sorted keys produce deterministic diffs.

**Alternatives considered**:
- `ruamel.yaml` — better comment preservation but heavier; not needed for generated (non-hand-authored) artifacts
- `python-frontmatter` for YAML output — designed for reading/writing Markdown+YAML frontmatter, not raw YAML files; wrong tool for this
- No YAML (JSON only) — FR-004 explicitly requires YAML export; rejected

---

## Decision 2: Export Directory Atomicity (No Partial Exports)

**Decision**: Write the entire export bundle to a `tempfile.mkdtemp()` directory first, validate all artifacts within the temp directory, then atomically rename/move to the final `exports/{design_id}/v{version}/` path. If any step fails, the temp directory is removed and the final path is never created.

**Rationale**: FR-006 requires "no partial exports." Writing directly to the final path risks leaving a partial directory if any artifact fails. A temp-then-rename approach ensures the final path either fully exists or doesn't exist at all. `shutil.copytree(src, dst)` (Python 3.8+) or `os.rename()` on the same filesystem gives this atomicity.

**Alternatives considered**:
- Write directly to final path + rollback on failure — rollback is complex and error-prone (cannot reliably undo all writes if the process crashes); rejected
- Transaction-style write with a sentinel file — adds complexity; temp-dir approach is simpler and equally safe

---

## Decision 3: Per-Persona Views (US2) — Thin Wrapper Over ADP-SPEC-010

**Decision**: US2 "per-persona C4 views" is satisfied by calling the existing `RenderOrchestrator.render(design_id, level)` once per C4 level. No new rendering logic is needed. The new `views.py` module is a thin orchestrator that calls the renderer for `"context"`, `"container"`, and `"component"` and returns a `ViewBundle(context=RenderResult, container=RenderResult, component=RenderResult)`.

**Rationale**: ADP-SPEC-010 already implements the full render pipeline (DSL + SVG + PNG per level). US2 is about the _concept_ of persona-based projection, not new rendering logic. Re-implementing filtering or styling would duplicate ADP-SPEC-010. A thin wrapper demonstrates the "one model, many views" promise without duplication.

**Alternatives considered**:
- New rendering logic in `adp.docs` — duplicates ADP-SPEC-010; rejected
- Single endpoint returning all 3 levels — added to the API as `GET /api/v1/designs/{id}/views`; returns all three C4 level renders in one response

---

## Decision 4: Export Confirmation Gate (ART-VIII)

**Decision**: Reuse the existing `ConfirmationPayload` pattern from ADP-SPEC-003/004. The `POST /api/v1/designs/{id}/export` endpoint requires `confirmation_id` in its request body (same as other consequential actions). The confirmation_id is obtained by first calling `POST /api/v1/operations/confirm` or inline in the request. Export without a valid confirmation_id returns 409 (confirmation required).

**Rationale**: ART-VIII requires "explicit, attributable human confirmation." The existing `ConfirmationPayload` pattern is already established in `adp.api.models.confirmation.py` and used by recommendation acceptance and validation override. Using the same pattern ensures consistent UX and avoids implementing a new confirmation flow.

**Implementation note**: The `POST /api/v1/designs/{id}/export` request body includes a `confirmation_id` field. Without it (or with an invalid/expired one), the endpoint returns 400/409 with a message explaining that export is a consequential action requiring confirmation.

---

## Decision 5: Markdown Frontmatter Format

**Decision**: Use YAML frontmatter delimited by `---` blocks at the top of each generated Markdown document, per the existing `python-frontmatter` convention already used in the project (knowledge connectors). Fields: `design_id`, `schema_version`, `generated_at` (ISO 8601), `generator_version` (ADP version), `level` (for view-specific docs).

**Rationale**: `python-frontmatter` (already a project dependency) can read and write this format. YAML frontmatter is the de-facto standard for Markdown documents with structured metadata (Hugo, Jekyll, GitHub wikis, Obsidian). The existing `git.py` connector already parses this format.

---

## Decision 6: Document Generator — Template vs Builder

**Decision**: Use a Python string builder (not a template engine like Jinja2) for generating Markdown documents. The document structure is deterministic and relatively flat; a dedicated builder function is simpler and produces byte-identical output without template-caching concerns.

**Rationale**: Template engines (Jinja2, Mako) add a dependency for what is essentially a structured string concatenation. The generated documents have a predictable structure: frontmatter → title → elements section → requirements section → traceability summary. A builder guarantees byte-identical output for the same input without template reloading or whitespace surprises.

**Alternatives considered**:
- Jinja2 — adds a dep; template caching can cause non-determinism; rejected
- Python string builder — **chosen** (zero new deps, deterministic, testable)

---

## Decision 7: Import — Schema Version Check Strategy

**Decision**: v1 import only supports the **current** schema version. A `model.json` whose `schema_version` field does not match the installed `SCHEMA_VERSION` constant is rejected with a clear error identifying both versions. No migration framework in v1; this is explicitly deferred to v2 per the spec's Assumptions section.

**Rationale**: The spec's Assumptions say "basic 'current version only' import is the v1 scope." Implementing a migration framework now would be gold-plating. The current schema version is `1.0.0` and the project has been built spec-by-spec; there are no known older versions in the wild yet. A clear error message telling the user which version was found and which is expected is sufficient for v1.

---

## Summary of New Dependencies

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `pyyaml` | `>=6.0` | `model.yaml` serialization for export | `pyproject.toml` |

All other requirements use existing dependencies: `pydantic`, `fastapi`, `python-frontmatter`, `cairosvg` (via ADP-SPEC-010), `jsonschema`.
