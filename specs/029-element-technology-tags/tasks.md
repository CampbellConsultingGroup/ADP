# Tasks: Element Technology Tagging (ADP-SPEC-029)

**Feature**: Element Technology Tagging
**Branch**: `029-element-technology-tags`
**Prerequisites**: All complete ✅

---

## Phase 1: Setup & Foundational

*Blocking prerequisites that all user stories depend on.*

- [X] T001 Add `TechnologyMetadata` Pydantic model to `src/adp/models.py` — fields: `technology: str | None = None`, `vendor: str | None = None`, `platform: str | None = None`, `version: str | None = None`, `owner_team: str | None = None`; add Pydantic validators for max lengths (200 chars on technology/vendor/platform/owner_team; 50 chars on version)
- [X] T002 Add `technology_metadata: TechnologyMetadata | None = None` field to the `Element` class in `src/adp/models.py`; confirm `extra="forbid"` config is preserved and existing element instantiation without the field still works
- [X] T003 Run `adp-generate` to regenerate JSON schemas for the updated `ArchitectureDescription` model; run `adp-generate --check` and confirm exit 0
- [X] T004 Create Alembic migration `src/adp/store/migrations/versions/005_element_technology_tags.py` — creates `element_technology_tags` table with primary key `(design_id, element_id)`, columns `technology TEXT`, `vendor TEXT`, `platform TEXT`, `version TEXT`, `owner_team TEXT`, `free_tags JSONB NOT NULL DEFAULT '[]'`, `updated_at TIMESTAMPTZ NOT NULL`; B-tree indexes on `technology`, `platform`, `owner_team`; GIN index on `free_tags`
- [X] T005 Run `alembic upgrade head` and verify `\d element_technology_tags` shows correct schema with all indexes

**Checkpoint**: `adp-generate --check` exits 0; `element_technology_tags` table exists.

---

## Phase 2: US1 — Tag an Element with Structured Technology Metadata

*Architect can add/edit/remove structured technology fields on any element. Tags persist across page reloads.*

**Independent test criteria**: `PUT /api/v1/designs/DSN-001/elements/ELM-001/tags` with a body containing technology/vendor/platform/version/owner_team returns 200; subsequent `GET /api/v1/designs/DSN-001` shows `technology_metadata` populated on that element.

- [X] T006 [P] [US1] Write contract test `tests/contract/test_tags_api.py` — `test_put_tags_returns_200()`: mock DesignStore; PUT valid body with all 5 structured fields; assert 200 and all fields echoed in response
- [X] T007 [P] [US1] Write `test_put_tags_missing_element_returns_404()` in `tests/contract/test_tags_api.py`: PUT to nonexistent element_id; assert 404
- [X] T008 [P] [US1] Write `test_put_tags_field_too_long_returns_422()` in `tests/contract/test_tags_api.py`: PUT with a 201-character technology value; assert 422
- [X] T009 [P] [US1] Write `test_put_tags_clears_on_empty_body()` in `tests/contract/test_tags_api.py`: PUT `{}`; assert 200 and all structured fields are null in response
- [X] T010 [P] [US1] Write `test_put_tags_writes_audit_entry()` in `tests/contract/test_tags_api.py`: mock DesignStore; PUT tags; assert `store.save()` was called and the saved design's audit_log has one new entry containing the element_id and actor
- [X] T011 [P] [US1] Write `test_get_design_includes_technology_metadata()` in `tests/contract/test_tags_api.py`: seed design with element that has technology_metadata; GET design; assert element has `technology_metadata` with correct values
- [X] T012 [US1] Create `src/adp/api/routers/tags.py` with `TagsRequest` Pydantic model (all optional fields matching `TechnologyMetadata` plus `tags: list[str]`), `TagsResponse` Pydantic model (all fields plus `updated_at: datetime`), and `PUT /{design_id}/elements/{element_id}/tags` route handler that: (1) loads design (404 if missing), (2) finds element (404 if missing), (3) builds `TechnologyMetadata` from request, (4) computes field diff vs current metadata for audit entry, (5) updates element's `technology_metadata` on the `ArchitectureDescription`, (6) saves design via `store.save()`, (7) upserts `element_technology_tags` table row via raw SQL, (8) writes audit entry with actor from `get_current_user(request)`, (9) returns `TagsResponse`
- [X] T013 [US1] Register `tags.router` (prefix `/api/v1/designs`, tags `["tags"]`) in `src/adp/api/app.py` — import and `app.include_router(tags.router)`
- [X] T014 [P] [US1] Run `pytest tests/contract/test_tags_api.py -q --no-cov` and confirm all 6 tests pass

---

## Phase 3: US2 — Free-Form Tags for Ad-Hoc Categorisation

*Architect can add/remove short string labels alongside structured metadata. Tags are stored per-element.*

**Independent test criteria**: PUT with `tags: ["legacy", "gdpr-scope"]` returns 200 with those tags; reload and assert both chips appear; remove one tag and save; assert only one remains.

- [X] T015 [P] [US2] Write `test_put_tags_free_form_tags_persisted()` in `tests/contract/test_tags_api.py`: PUT body `{"tags": ["legacy", "needs-migration"]}`; reload design; assert element has both tags in `Element.tags`
- [X] T016 [P] [US2] Write `test_put_tags_blank_tag_returns_422()` in `tests/contract/test_tags_api.py`: PUT `{"tags": ["valid", ""]}`; assert 422
- [X] T017 [P] [US2] Write `test_put_tags_tag_too_long_returns_422()` in `tests/contract/test_tags_api.py`: PUT `{"tags": ["a" * 51]}`; assert 422
- [X] T018 [US2] Add `tags: list[str] = Field(default_factory=list)` validator to `TagsRequest` in `src/adp/api/routers/tags.py` — `@field_validator("tags")` checks each tag: max 50 chars, must not be blank; update the route handler to also write `request.tags` to `Element.tags` (the existing free-form list) and to the `free_tags` column of the `element_technology_tags` row
- [X] T019 [P] [US2] Run `pytest tests/contract/test_tags_api.py -q --no-cov` and confirm all 9 tests pass

---

## Phase 4: US3 — View Technology Metadata in the Inspection Panel

*Any architect viewing a design can see technology metadata for elements in the Canvas inspection panel.*

**Independent test criteria**: Open a design with technology-tagged elements in the Canvas; click an element; assert the inspection panel shows "Technology", "Vendor", "Platform", "Version", "Owner team" labels with their values; click an untagged element; assert the panel shows "No technology metadata added yet".

- [X] T020 [P] [US3] Add `TechnologyMetadata` TypeScript interface to `web/src/types.ts` (or `web/src/api/designs.ts`): `technology?: string; vendor?: string; platform?: string; version?: string; owner_team?: string`; update `Element` TypeScript interface to include `technology_metadata?: TechnologyMetadata | null`
- [X] T021 [P] [US3] Add `useUpdateElementTags(designId: string, elementId: string)` mutation hook to `web/src/api/designs.ts` using TanStack Query — `mutationFn` calls `PUT /api/v1/designs/${designId}/elements/${elementId}/tags`; on success invalidates `["design", designId]`
- [X] T022 [US3] Create `web/src/inspection/TechnologyEditor.tsx` — inline edit form component accepting `designId: string`, `elementId: string`, `existing: TechnologyMetadata | null`, `existingTags: string[]`, `onDone: () => void` props; renders labeled text inputs for technology/vendor/platform/version/owner_team plus a chip input for free-form tags (Enter to add, ✕ to remove); Save and Cancel buttons; calls `useUpdateElementTags` on submit; shows field-level validation messages for length violations
- [X] T023 [US3] Edit `web/src/inspection/InspectionPanel.tsx` — add a "Technology" section below the existing "Satisfies" section: when `element.technology_metadata` has at least one non-null field, render a read-only display of each set field as a `label: value` row plus free-form tag chips from `element.tags`; when nothing is set, render "No technology metadata added yet"; add an "Edit" (or "Add") button that toggles `<TechnologyEditor>` inline within the panel; the Technology section is visible across all three C4 canvas levels
- [X] T024 [US3] Update the CALM exporter `src/adp/calm/exporter.py` — in the per-element loop, after the existing `{"tags": el.tags}` append, also append `{"technology": el.technology_metadata.technology}`, `{"vendor": el.technology_metadata.vendor}`, etc. for each non-null field in `technology_metadata`; wrap in `if el.technology_metadata:` guard
- [X] T025 [P] [US3] Run `cd web && npx tsc --noEmit` and confirm zero TypeScript errors

---

## Phase 5: Polish & Cross-Cutting

- [X] T026 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite passes with all new tests
- [X] T027 [P] Run `ruff check src/adp/api/routers/tags.py src/adp/models.py src/adp/calm/exporter.py` — zero errors
- [X] T028 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors (final confirmation)
- [X] T029 Manual E2E: start server; create a design; add two elements; open Canvas; click first element; click "Add" in Technology section; fill in all fields including two free-form tags; save; verify inspection panel shows values; reload page; verify values persist; open second element; verify "No technology metadata added yet" shown; verify audit log for the design has an entry for the tag save
- [X] T030 Manual CALM export check: trigger `GET /api/v1/designs/{id}/export/calm` for the design with tags; open the JSON; verify element's `metadata` array contains `technology`, `vendor`, `platform` entries

---

## Dependencies

```
T001 → T002 → T003         (model must exist before schema check)
T004 → T005                (migration must run before any tag writes)
T001, T004, T005 → T012   (model + table must exist before router)
T012, T013 → T014          (router must be registered before tests can pass)
T014 → T018                (US1 tests must pass before adding US2 logic to router)
T018 → T019
T020, T021 → T022 → T023  (TypeScript types needed before editor, editor before panel)
T023 → T025
T026, T027, T028 → T029   (all automated checks must pass before manual E2E)
```

## Parallel Opportunities

- T006–T011 can all be written in parallel (separate test functions, no shared state)
- T015–T017 can be written in parallel
- T020 and T021 can be written in parallel (different files, both are TypeScript)
- T026, T027, T028 can all run in parallel

## Implementation Strategy (MVP)

**MVP = Phase 1 + Phase 2 (T001–T014)**

Delivers: engineers can tag elements with structured technology metadata via the API; the data is stored in both the canonical model and the indexed query table; audit trail is complete. The InspectionPanel UI (US3) and free-form tags (US2) can follow in a second increment.
