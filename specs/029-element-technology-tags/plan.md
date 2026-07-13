# Implementation Plan: Element Technology Tagging

**Branch**: `029-element-technology-tags` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/029-element-technology-tags/spec.md`

## Summary

Adds structured technology metadata (technology, vendor, platform, version, owner_team) and free-form string tags to ADP design elements. Metadata is stored in two places: as a nested `TechnologyMetadata` object within the canonical `Element` model (for exports and backward compatibility) and in a dedicated indexed `element_technology_tags` PostgreSQL table (for efficient cross-portfolio queries in ADP-SPEC-031). Every change is written to the design audit log. The element inspection panel on the Canvas gains a read/edit Technology section.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, asyncpg, Pydantic v2, React 18, TanStack Query v5 — all existing stack, zero new packages
**Storage**: PostgreSQL 16; new `element_technology_tags` table + B-tree + GIN indexes; `design_versions` JSONB extended with `technology_metadata` nested in element objects
**Testing**: pytest (backend contract + unit tests), existing FastAPI TestClient pattern
**Target Platform**: Same as existing ADP — Linux server, browser-based frontend
**Performance Goals**: SC-004 — cross-portfolio technology query completes in under 2 seconds across 100 designs
**Constraints**: Additive schema change only (ART-XV) — existing designs with no tags must continue to work unchanged
**Scale/Scope**: 100 designs, ~10 elements per design typical; tags table ~1,000 rows initially

## Constitution Check

| Article | Requirement | This Plan |
|---|---|---|
| ART-I | Spec-driven | Plan derived from spec.md ✅ |
| ART-II | Model is source of truth | Canonical `Element` model extended; tags table is a derived index ✅ |
| ART-IV | TDD | Contract tests written before implementation at each phase ✅ |
| ART-V | Security by design | Auth required on PUT; no new trust boundaries ✅ |
| ART-IX | Audit trail | Every PUT writes an audit entry with actor + field diff ✅ |
| ART-XIII | Typed contracts | `TechnologyMetadata` Pydantic model; OpenAPI spec auto-generated ✅ |
| ART-XV | Governed schema evolution | Additive field on Element with `None` default; migration versioned ✅ |

## File Changes

| File | Action |
|---|---|
| `src/adp/models.py` | EDIT — add `TechnologyMetadata` Pydantic model + optional `technology_metadata` field on `Element` |
| `src/adp/store/migrations/versions/005_element_technology_tags.py` | CREATE — new indexed table |
| `src/adp/api/routers/tags.py` | CREATE — `PUT /api/v1/designs/{id}/elements/{el_id}/tags` |
| `src/adp/api/app.py` | EDIT — register tags router |
| `src/adp/calm/exporter.py` | EDIT — include `technology_metadata` fields in CALM node metadata |
| `tests/unit/test_technology_metadata.py` | CREATE — Pydantic model validation tests |
| `tests/contract/test_tags_api.py` | CREATE — PUT and design-GET contract tests |
| `web/src/api/designs.ts` | EDIT — add `TechnologyMetadata` TypeScript interface + `useUpdateElementTags()` hook |
| `web/src/inspection/InspectionPanel.tsx` | EDIT — add Technology section with inline edit |
| `web/src/inspection/TechnologyEditor.tsx` | CREATE — inline edit form component |

## Phase 1: Canonical Model + Migration

**Goal**: Extend the data model and add the indexed table. No API or UI yet.

### Tasks

- [ ] Add `TechnologyMetadata` Pydantic model to `src/adp/models.py` — fields: `technology`, `vendor`, `platform`, `version`, `owner_team` (all `str | None = None`, max lengths enforced by Pydantic validators)
- [ ] Add `technology_metadata: TechnologyMetadata | None = None` to `Element` model — `extra="forbid"` config preserved; existing designs with no field default to `None` (backward compatible)
- [ ] Run `adp-generate --check` to verify JSON schema drift gate still passes; if needed, run `adp-generate` to regenerate schemas
- [ ] Create `src/adp/store/migrations/versions/005_element_technology_tags.py` — creates `element_technology_tags` table with primary key `(design_id, element_id)`, all tag columns, B-tree indexes on `technology`, `platform`, `owner_team`, GIN index on `free_tags`
- [ ] Run `alembic upgrade head` against the live DB; verify `\d element_technology_tags`

**Checkpoint**: `adp-generate --check` passes; table exists with correct schema.

## Phase 2: Backend — Tags API

**Goal**: `PUT /tags` endpoint with audit trail and dual-write to both JSONB and tags table.

### Tests first (TDD — ART-IV)

- [ ] Write `test_put_tags_returns_200()` in `tests/contract/test_tags_api.py` — POST valid body; assert 200; assert response contains all fields
- [ ] Write `test_put_tags_clears_on_empty_body()` — PUT `{}`; assert all fields null in response
- [ ] Write `test_put_tags_missing_element_returns_404()` — PUT to nonexistent element_id; assert 404
- [ ] Write `test_put_tags_field_too_long_returns_422()` — PUT with 201-char technology; assert 422
- [ ] Write `test_put_tags_blank_tag_returns_422()` — PUT with `tags: [""]`; assert 422
- [ ] Write `test_put_tags_writes_audit_entry()` — PUT tags; assert design audit log has entry with actor + element_id + changed fields
- [ ] Write `test_get_design_includes_technology_metadata()` — after PUT; GET design; assert element has `technology_metadata` populated

### Implementation

- [ ] Create `src/adp/api/routers/tags.py`:
  - `TagsRequest` Pydantic model matching contract spec
  - `TagsResponse` Pydantic model
  - `PUT /{design_id}/elements/{element_id}/tags` handler:
    1. Load design (404 if missing)
    2. Find element (404 if missing)
    3. Build `TechnologyMetadata` from request; validate
    4. Compute field diff (old vs new) for audit entry
    5. Update element in design; save design (increments version)
    6. Upsert `element_technology_tags` row via raw SQL
    7. Write ART-IX audit entry (actor from `get_current_user`)
    8. Return `TagsResponse`
- [ ] Register `tags.router` in `src/adp/api/app.py` under prefix `/api/v1/designs`
- [ ] Update CALM exporter to include `technology`, `vendor`, `platform` in `node_metadata` alongside existing `adp-kind` and `tags`

**Checkpoint**: All contract tests pass; `GET /api/v1/designs/{id}` response includes `technology_metadata`; CALM export contains technology fields.

## Phase 3: Frontend — Inspection Panel

**Goal**: Architects can view and edit technology metadata in the element inspection panel.

### Tasks

- [ ] Add `TechnologyMetadata` TypeScript interface to `web/src/api/designs.ts`; update `Element` interface to include optional `technology_metadata`
- [ ] Add `useUpdateElementTags(designId, elementId)` TanStack Query mutation hook to `web/src/api/designs.ts` — `PUT /api/v1/designs/{id}/elements/{el_id}/tags`; on success invalidates `["design", designId]`
- [ ] Create `web/src/inspection/TechnologyEditor.tsx` — inline form with fields for technology, vendor, platform, version, owner_team plus chip input for free-form tags; Save/Cancel buttons; calls `useUpdateElementTags`
- [ ] Edit `web/src/inspection/InspectionPanel.tsx`:
  - Add Technology section below existing Satisfies section
  - When `element.technology_metadata` is set: show values as labelled read-only fields + Edit button
  - When not set: show "No technology metadata added yet" + Add button
  - Edit/Add button toggles `<TechnologyEditor>` inline

**Checkpoint**: TypeScript clean (`npx tsc --noEmit`); can add/edit/view technology metadata on an element via the Canvas inspection panel; changes persist on reload.

## Phase 4: Polish

- [ ] Run `pytest tests/ --ignore=tests/integration -q` — full suite passes
- [ ] Run `ruff check src/adp/api/routers/tags.py src/adp/models.py` — clean
- [ ] Run `cd web && npx tsc --noEmit` — zero TypeScript errors
- [ ] Manual E2E: open a design; add technology metadata to an element; verify it appears in CALM export JSON; verify audit log entry

## Constitution Compliance Summary

- **ART-II** ✅ `Element.technology_metadata` in canonical JSONB; `element_technology_tags` is a derived index only
- **ART-IV** ✅ Contract tests written before implementation code in each phase
- **ART-IX** ✅ `PUT /tags` writes audit entry with field diff; actor from authenticated user (ADP-SPEC-026)
- **ART-XIII** ✅ `TechnologyMetadata`, `TagsRequest`, `TagsResponse` are fully typed Pydantic models
- **ART-XV** ✅ `technology_metadata: TechnologyMetadata | None = None` — additive, backward compatible; Alembic migration versioned as 005
