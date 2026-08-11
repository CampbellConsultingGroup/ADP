# Contract: Diagrams API (ADP-SPEC-046)

Prefix: `/api/v1/diagrams`. All endpoints require `WRITE_DIAGRAM` for mutations (create/update/delete/export); reads are ungated, consistent with how non-sensitive ADP content is already read (research.md Decision 5).

## `POST /api/v1/diagrams`

Create a new diagram. Body: `DiagramCreate` (`title`, `diagram_type`, `dsl_source` — the latter defaulting to `""` so a brand-new diagram is creatable before any content exists, per the spec's Edge Cases). Returns `201` + `Diagram`.

- `422` if `title` is blank, `diagram_type` isn't one of the five supported values, or `dsl_source` exceeds the 50,000-character cap.

## `GET /api/v1/diagrams`

List all diagrams (User Story 3 — global, not Design-scoped, per FR-011). Returns `200` + `DiagramListResponse` (`DiagramSummary` items — no `dsl_source`, matching the existing summary/detail split convention).

## `GET /api/v1/diagrams/{id}`

Fetch one diagram's full content, including `dsl_source`. Returns `200` + `Diagram`, or `404` if not found.

## `PUT /api/v1/diagrams/{id}`

Update `title` and/or `dsl_source` (both optional — a partial update, matching `ApplicationUpdate`'s convention). `diagram_type` is immutable (see data-model.md §4). Returns `200` + the updated `Diagram`, or `404` if not found.

- `422` on the same validation rules as create.

## `DELETE /api/v1/diagrams/{id}`

Delete a diagram. Returns `204`, or `404` if not found. No `confirmation_id` gate (ART-VIII does not apply — see plan.md's Constitution Check).

## `POST /api/v1/diagrams/{id}/export`

Convert a client-rendered SVG string to PNG via `cairosvg` (research.md Decision 3) — the one endpoint that isn't plain CRUD. Body: `{"svg": "<svg>...</svg>"}`. Returns `200` with `Content-Type: image/png` and the PNG bytes, or `404` if the diagram doesn't exist, or `422` if the submitted string isn't valid SVG.

This endpoint is stateless with respect to `dsl_source` — it converts whatever SVG the browser already rendered (via the vendored `svg-renderer.ts`) and submits, rather than re-deriving SVG from the stored DSL server-side (which would require the very server-side parsing this feature deliberately avoids — research.md Decision 2). The `{id}` in the path exists only for the `WRITE_DIAGRAM`/existence check, not because the endpoint reads that diagram's stored content.

## Non-guarantees

- No real-time collaborative editing — a same-diagram concurrent save is last-write-wins (spec Edge Cases), not merged.
- No versioning/history beyond the single current `dsl_source` — no undo-after-save, no revision list.
- No governance/Standards enforcement — `POST`/`PUT` never reject content on stylistic or organizational-standard grounds, only on the structural validation rules above (FR-009).
