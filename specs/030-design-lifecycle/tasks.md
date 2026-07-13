# Tasks: Design Lifecycle Management (ADP-SPEC-030)

**Feature**: Design Lifecycle Management
**Branch**: `030-design-lifecycle`
**Prerequisites**: All complete ✅

---

## Phase 1: Setup & Foundation

*Blocking prerequisites. Must complete before any user story phases.*

- [X] T001 Add `LifecycleStatus` StrEnum to `src/adp/models.py` with five values: `DRAFT = "draft"`, `PROPOSED = "proposed"`, `CURRENT = "current"`, `DEPRECATED = "deprecated"`, `DECOMMISSIONED = "decommissioned"`
- [X] T002 Add five lifecycle fields to `ArchitectureDescription` in `src/adp/models.py`: `lifecycle_status: LifecycleStatus = LifecycleStatus.DRAFT`, `proposed_date: datetime | None = None`, `current_since: datetime | None = None`, `review_due: datetime | None = None`, `retirement_date: datetime | None = None` — all after existing fields, preserving backward compatibility
- [X] T003 Run `adp-generate` then `adp-generate --check` from project root — confirm exit 0 (schema drift gate passes for the updated `ArchitectureDescription`)
- [X] T004 Create Alembic migration `src/adp/store/migrations/versions/006_design_lifecycle.py` that executes: `ALTER TABLE designs ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'draft'`; `ALTER TABLE designs ADD COLUMN proposed_date TIMESTAMPTZ`; `ALTER TABLE designs ADD COLUMN current_since TIMESTAMPTZ`; `ALTER TABLE designs ADD COLUMN review_due TIMESTAMPTZ`; `ALTER TABLE designs ADD COLUMN retirement_date TIMESTAMPTZ`; `CREATE INDEX ix_designs_lifecycle ON designs (lifecycle_status)`; `CREATE INDEX ix_designs_review_due ON designs (review_due) WHERE review_due IS NOT NULL`; downgrade drops indexes then columns
- [X] T005 Run `alembic upgrade head` and verify: `SELECT lifecycle_status, count(*) FROM designs GROUP BY 1` returns all existing designs as `draft`; `\d designs` shows all five new columns and both indexes

**Checkpoint**: `adp-generate --check` exits 0; migration applied; all existing designs show `lifecycle_status = 'draft'`.

---

## Phase 2: US1 — Transition a Design Through Its Lifecycle

*P1. Architect can transition a design between lifecycle states via an explicit action. Every transition is recorded in the audit log. Auto-dates are set on relevant transitions.*

**Independent test criteria**: `PATCH /api/v1/designs/DSN-001/lifecycle` with `{"status": "proposed"}` returns 200; subsequent `GET /api/v1/designs/DSN-001` shows `lifecycle_status: "proposed"` and `proposed_date` set; audit log has a new entry. `PATCH` with invalid transition returns 409.

- [X] T006 [P] [US1] Write contract test `tests/contract/test_lifecycle_api.py` — `test_patch_lifecycle_draft_to_proposed_returns_200()`: mock DesignStore; PATCH `{"status": "proposed"}`; assert 200 and `lifecycle_status == "proposed"` in response; assert `proposed_date` is not null
- [X] T007 [P] [US1] Write `test_patch_lifecycle_invalid_transition_returns_409()` in `tests/contract/test_lifecycle_api.py`: PATCH `{"status": "decommissioned"}` on a draft design; assert 409 with detail containing valid next states
- [X] T008 [P] [US1] Write `test_patch_lifecycle_writes_audit_entry()` in `tests/contract/test_lifecycle_api.py`: mock DesignStore; PATCH valid transition; assert `store.save()` was called; assert saved design's `audit_log` has a new entry containing old status, new status, and actor
- [X] T009 [P] [US1] Write `test_patch_lifecycle_date_override_respected()` in `tests/contract/test_lifecycle_api.py`: PATCH `{"status": "proposed", "proposed_date": "2026-01-01T00:00:00Z"}`; assert `proposed_date` in response equals the override date (not today)
- [X] T010 [P] [US1] Write `test_patch_lifecycle_auto_date_does_not_overwrite_existing()` in `tests/contract/test_lifecycle_api.py`: seed design already having `proposed_date = "2025-06-01"`; PATCH `{"status": "current"}`; GET design; assert `proposed_date` still equals `"2025-06-01"` (auto-date only applies when field is None)
- [X] T011 [P] [US1] Write `test_patch_lifecycle_with_note_included_in_audit_entry()` in `tests/contract/test_lifecycle_api.py`: PATCH `{"status": "deprecated", "note": "Superseded by DSN-042"}`; assert audit entry summary contains the note text
- [X] T012 [US1] Create `src/adp/api/routers/lifecycle.py` with: `VALID_TRANSITIONS` dict implementing the FR-004 graph (`{"draft": {"proposed"}, "proposed": {"current", "draft"}, "current": {"deprecated"}, "deprecated": {"decommissioned", "current"}, "decommissioned": set()}`); `LifecycleTransitionRequest` Pydantic model (fields: `status: LifecycleStatus`, `note: str | None = None` max 500 chars, optional date override fields for `proposed_date`, `current_since`, `review_due`, `retirement_date`); `_apply_auto_dates()` helper that sets `proposed_date` when transitioning to proposed (if None), `current_since` when transitioning to current (if None), `retirement_date` when transitioning to decommissioned (if None), using override value from request if supplied; `PATCH /{design_id}/lifecycle` handler that: validates status is a valid `LifecycleStatus`, validates transition is permitted (409 if not, "Reset to Draft" from any status is always permitted), loads design (404 if missing), records old status, applies auto-dates, updates `design.lifecycle_status` and date fields, writes audit entry with actor (from `get_current_user(request)`), old_status, new_status, note, calls `store.save(design)`, then upserts lifecycle columns on the `designs` table row, returns 200 with updated lifecycle fields
- [X] T013 [US1] Update `DesignStore.save()` in `src/adp/store/store.py` — in the existing `designs.update()` call (or `designs.insert()` for new designs), also set the five lifecycle columns: `lifecycle_status`, `proposed_date`, `current_since`, `review_due`, `retirement_date` from the `description` object
- [X] T014 [US1] Register `lifecycle.router` in `src/adp/api/app.py` with prefix `/api/v1/designs` — import and `app.include_router(lifecycle.router)`
- [X] T015 [P] [US1] Run `pytest tests/contract/test_lifecycle_api.py -q --no-cov` and confirm all 6 tests pass

---

## Phase 3: US2 — Filter the Portfolio by Lifecycle Status

*P1. Architect can filter the Designs screen by lifecycle status. Filter uses indexed column on `designs` table — sub-500ms response. Designs show lifecycle status badge and count updates with filter.*

**Independent test criteria**: `GET /api/v1/designs?status=current` returns only designs with `lifecycle_status = "current"`; total count matches filtered set; `?status=` omitted returns all designs.

- [X] T016 [P] [US2] Write `test_list_designs_filter_by_status()` in `tests/contract/test_designs_api.py` (edit existing file): mock DesignStore returning 2 designs, one current and one draft; GET `/api/v1/designs?status=current`; assert only 1 design returned; assert returned design has `lifecycle_status == "current"`
- [X] T017 [P] [US2] Write `test_list_designs_no_filter_returns_all()` in `tests/contract/test_designs_api.py`: mock DesignStore returning 2 designs with different statuses; GET `/api/v1/designs` (no status param); assert both returned
- [X] T018 [P] [US2] Write `test_create_design_defaults_lifecycle_to_draft()` in `tests/contract/test_designs_api.py`: POST new design; assert response has `lifecycle_status == "draft"` and all date fields null
- [X] T019 [US2] Edit `DesignStore.list_all()` in `src/adp/store/store.py` to accept `status: str | None = None` parameter — when set, add `WHERE designs.lifecycle_status = :status` to the query (using the indexed column, not JSONB); ensure lifecycle columns from the `designs` table are also selected in the join and used to populate the returned `ArchitectureDescription` objects (so lifecycle data is consistent even if JSONB differs)
- [X] T020 [US2] Edit `DesignStore.count_all()` in `src/adp/store/store.py` to accept `status: str | None = None` parameter with matching WHERE clause
- [X] T021 [US2] Edit `src/adp/api/routers/designs.py`: add `status: str | None = Query(default=None)` parameter to `list_designs()`; pass it to `store.list_all(status=status)` and `store.count_all(status=status)`; extend `DesignSummary` Pydantic model to include `lifecycle_status: str`, `proposed_date: datetime | None`, `current_since: datetime | None`, `review_due: datetime | None`, `retirement_date: datetime | None`, and computed `overdue_review: bool` (true when `lifecycle_status == "current"` AND `review_due is not None` AND `review_due < datetime.now(timezone.utc)`); update `list_designs()` to populate these new fields in each `DesignSummary`
- [X] T022 [P] [US2] Run `pytest tests/contract/test_designs_api.py -q --no-cov` and confirm all tests pass (existing + 3 new)

---

## Phase 4: US2+US3 — Frontend Lifecycle Badges, Filter, and Overdue Indicator

*US2 (P1): Status badges and filter on Designs screen. US3 (P2): Lifecycle dates + overdue indicator. Grouped because both modify `DesignsPage.tsx`.*

**Independent test criteria**: Designs screen shows colour-coded status badge per row; lifecycle filter dropdown filters the list; `review_due` in the past shows amber "⚠ Review overdue" chip; TypeScript compiles clean.

- [X] T023 [P] [US2] Add lifecycle fields to the `DesignSummary` TypeScript interface in `web/src/api/designs.ts`: `lifecycle_status: string`, `proposed_date: string | null`, `current_since: string | null`, `review_due: string | null`, `retirement_date: string | null`, `overdue_review: boolean`
- [X] T024 [P] [US2] Update `useDesignList(page?)` hook in `web/src/api/designs.ts` to accept an optional `status?: string` parameter and append `&status=${status}` to the query URL when set; update the query key to include status: `["designs", page, status]`
- [X] T025 [P] [US2] Add `useTransitionLifecycle(designId: string)` mutation hook to `web/src/api/designs.ts` — `mutationFn` calls `PATCH /api/v1/designs/${designId}/lifecycle` with body `{status, note?, proposed_date?, current_since?, review_due?, retirement_date?}`; on success invalidates `["designs"]` query key
- [X] T026 [US2] Create `web/src/designs/LifecycleTransitionButton.tsx` — a dropdown button component accepting `designId: string`, `currentStatus: string` props; computes valid next transitions using the same `VALID_TRANSITIONS` graph as the backend (client-side for UX, server validates); renders as a small button with a dropdown menu showing next states; on selecting a state, shows an inline popover with: optional Note textarea (max 500 chars), optional date fields relevant to the transition (e.g. proposed_date for draft→proposed), Confirm and Cancel buttons; calls `useTransitionLifecycle()` on confirm; shows loading state during mutation; shows error message if 409 received
- [X] T027 [US2] [US3] Edit `web/src/designs/DesignsPage.tsx`: add a lifecycle filter dropdown above the design list (options: All / Draft / Proposed / Current / Deprecated / Decommissioned) that passes the selected value as `status` to `useDesignList()`; update the design list item render to show: (a) a colour-coded status badge (`lifecycle_status === "draft"` → grey chip, `"proposed"` → blue, `"current"` → green, `"deprecated"` → amber, `"decommissioned"` → red), (b) for US3: when `overdue_review === true`, an amber "⚠ Review overdue" chip next to the status badge, (c) the `<LifecycleTransitionButton>` component per design row; update the design count display to reflect filtered results
- [X] T028 [P] Run `cd web && npx tsc --noEmit` and confirm zero TypeScript errors

---

## Phase 5: Export + Polish

- [X] T029 Edit `src/adp/calm/exporter.py` to include lifecycle metadata in the CALM document — in the top-level `metadata` list (alongside the existing `source: "adp"` entry), append entries for `lifecycle_status`, and each non-null date field from the design's `ArchitectureDescription` lifecycle fields
- [X] T030 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite passes with all new tests
- [X] T031 [P] Run `ruff check src/adp/api/routers/lifecycle.py src/adp/models.py src/adp/store/store.py src/adp/api/routers/designs.py src/adp/calm/exporter.py` — zero errors
- [X] T032 [P] Run `cd web && npx tsc --noEmit` — final confirmation, zero TypeScript errors
- [X] T033 Verify SC-006: confirm `SELECT lifecycle_status, count(*) FROM designs GROUP BY 1` shows only `draft` rows (all existing designs defaulted correctly without manual action)
- [X] T034 Manual E2E: start server; navigate to Designs screen; confirm status badge shows "Draft" on all designs; select "Current" filter — confirm empty state or filtered list; open a design; use lifecycle transition button to advance to Proposed; return to Designs screen; confirm "Proposed" badge shows; advance to Current; set `review_due` to yesterday via PATCH; confirm amber "⚠ Review overdue" chip appears; verify CALM export JSON contains `lifecycle_status` in metadata

---

## Dependencies

```
T001 → T002 → T003          (LifecycleStatus must exist before ArchitectureDescription change)
T004 → T005                  (migration before alembic verification)
T001, T002, T005 → T012     (model + DB must exist before lifecycle router)
T012, T013, T014 → T015     (router must be registered before tests can pass)
T019, T020 → T021           (store filters before router uses them)
T021 → T022                  (list endpoint must support status param before tests pass)
T023, T024, T025 → T026     (TypeScript types + hooks before transition button)
T026 → T027                  (transition button before Designs page integration)
T027 → T028                  (page changes before TypeScript check)
T015, T022, T028 → T030     (all tests must pass before final suite run)
```

## Parallel Opportunities

- T006–T011 all write separate test functions — can be written simultaneously
- T016–T018 all write separate test functions — can be written simultaneously
- T023, T024, T025 all touch different parts of `designs.ts` — safe to do in parallel (or sequentially in one file)
- T030, T031, T032 all run independently

## Implementation Strategy (MVP)

**MVP = Phase 1 + US1 (T001–T015)**

Delivers: architects can transition designs through their lifecycle via the API; transitions are validated against the graph; audit trail is complete; auto-dates work. The filter UI (US2) and overdue indicator (US3) can ship as a fast second increment since Phase 3–4 builds directly on the working API.

**Second increment = US2 + US3 (T016–T028)**: filter and all frontend work.

**Third increment = Export + Polish (T029–T034)**: CALM export and manual E2E verification.
