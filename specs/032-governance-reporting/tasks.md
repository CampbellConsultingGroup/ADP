# Tasks: Governance Reporting Dashboard (ADP-SPEC-032)

**Feature**: Governance Reporting Dashboard
**Branch**: `032-governance-reporting`
**Prerequisites**: ADP-SPEC-029 (element_technology_tags) ✅, ADP-SPEC-030 (lifecycle_status column) ✅, ADP-SPEC-031 (Portfolio screen — "Governance Report" button) ✅

---

## Phase 1: Foundational — Backend Governance API

*4 read-only endpoints, no new tables, no new packages. All 3 frontend tabs depend on these.*

### Tests (TDD — ART-IV)

- [X] T001 [P] Create `tests/contract/test_governance_api.py` — `test_status_returns_all_designs()`: mock DB with 2 designs and 3 audit entries; GET `/api/v1/governance/status`; assert response has both design records with correct `audit_count`, `accepted_recommendations`, and `reasoning_record_count` fields present
- [X] T002 [P] Write `test_status_handles_design_with_no_activity()` in `tests/contract/test_governance_api.py`: seed design with no audit entries; GET `/api/v1/governance/status`; assert design still appears with `audit_count=0`, `last_activity=null`
- [X] T003 [P] Write `test_exceptions_returns_only_fail_advisory()` in `tests/contract/test_governance_api.py`: seed design with `findings` array containing critical + info severity findings in design JSONB; GET `/api/v1/governance/exceptions`; assert only critical finding appears (mapped to FAIL); info finding excluded
- [X] T004 [P] Write `test_exceptions_empty_when_no_findings()`: design with empty findings; GET `/api/v1/governance/exceptions`; assert `{"exceptions": [], "total": 0}`
- [X] T005 [P] Write `test_activity_requires_date_range()` in `tests/contract/test_governance_api.py`: GET `/api/v1/governance/activity` without dates; assert 422
- [X] T006 [P] Write `test_activity_rejects_range_over_90_days()`: GET with `from_date` + 91 days later as `to_date`; assert 422 with detail mentioning "90-day"
- [X] T007 [P] Write `test_activity_returns_entries_in_range()`: seed 2 audit entries (one inside range, one outside); GET with 30-day range; assert only in-range entry returned; assert response has `from_date`, `to_date`, `total` fields
- [X] T008 [P] Write `test_activity_filter_by_action()`: seed entries with different `action` values; GET with `?action=lifecycle-transition`; assert only matching entries returned
- [X] T009 [P] Write `test_activity_export_returns_csv()`: GET `/api/v1/governance/activity/export?from_date=2026-01-01&to_date=2026-03-31`; assert `Content-Type: text/csv`; assert `Content-Disposition` header contains `attachment; filename="adp-audit-`; assert response body contains CSV header row with correct columns

### Implementation

- [X] T010 Create `src/adp/api/routers/governance.py` with Pydantic response models:
  - `DesignGovernanceRecord(design_id, title, lifecycle_status, last_activity: datetime | None, audit_count: int, accepted_recommendations: int, reasoning_record_count: int)`
  - `GovernanceStatusResponse(designs: list[DesignGovernanceRecord], total: int)`
  - `ComplianceExceptionRecord(design_id, title, finding_id, finding_summary, severity: Literal["FAIL","ADVISORY"], source: str | None, recorded_at: datetime)`
  - `ComplianceExceptionsResponse(exceptions: list[ComplianceExceptionRecord], total: int)`
  - `AuditActivityEntry(id, design_id, design_title, actor, action, affected_entity, summary, timestamp, origin)`
  - `ActivityFeedResponse(entries: list[AuditActivityEntry], total: int, page: int, page_size: int, from_date: str, to_date: str)`
- [X] T011 Implement `GET /api/v1/governance/status` in `src/adp/api/routers/governance.py` — single aggregating SQL query (from research.md Decision 1): LEFT JOINs `audit_entries`, `operations`, `llm_reasoning_log`; GROUP BY design; ORDER BY `MAX(ae.timestamp) DESC NULLS LAST`; use `Depends(_get_kb_session)` from `adp.api.deps`; return `GovernanceStatusResponse`
- [X] T012 Implement `GET /api/v1/governance/exceptions` in `src/adp/api/routers/governance.py` — load all designs via DesignStore, extract `ArchitectureDescription.findings[]` from each, filter `severity IN ('warning','critical')`, map `critical`→FAIL / `warning`→ADVISORY, sort FAIL-first then by `recorded_at` desc (use `design.updated_at` as approximation); return `ComplianceExceptionsResponse`
- [X] T013 Implement `GET /api/v1/governance/activity` in `src/adp/api/routers/governance.py` — date range validation: parse `from_date` and `to_date` as `date`, raise 422 if missing or range > 90 days; SQL: `SELECT ae.*, d.title AS design_title FROM audit_entries ae JOIN designs d ON d.id = ae.design_id WHERE ae.timestamp BETWEEN :from AND :to AND (:action IS NULL OR ae.action = :action) ORDER BY ae.timestamp DESC LIMIT :limit OFFSET :offset`; support `actor` filter with `ae.actor = :actor`; return paginated `ActivityFeedResponse`
- [X] T014 Implement `GET /api/v1/governance/activity/export` in `src/adp/api/routers/governance.py` — same query as T013 without pagination; stream CSV via `fastapi.responses.StreamingResponse` with Python stdlib `csv.writer`; columns: `id, design_id, design_title, actor, action, affected_entity, summary, timestamp, origin`; filename `adp-audit-{from_date}-{to_date}.csv`; same 90-day validation
- [X] T015 Register `governance.router` (prefix `/api/v1/governance`, tags `["governance"]`) in `src/adp/api/app.py`
- [X] T016 [P] Run `pytest tests/contract/test_governance_api.py -q --no-cov` — all 9 tests pass

**Checkpoint**: All 4 governance endpoints return correct responses; CSV export downloads.

---

## Phase 2: US1 — Design Status Tab

*Architect sees per-design governance summary table: last activity, audit count, accepted recommendations, reasoning records. Sortable. Click row opens that design.*

**Independent test criteria**: Table shows all designs; a design with 0 audit entries still appears (row with zero counts); clicking a row triggers `onSelectDesign(design_id)`.

- [X] T017 [P] [US1] Create `web/src/api/governance.ts` — TypeScript interfaces matching API contracts:
  ```ts
  interface DesignGovernanceRecord { design_id, title, lifecycle_status, last_activity: string|null, audit_count, accepted_recommendations, reasoning_record_count }
  interface ComplianceException { design_id, title, finding_id, finding_summary, severity: "FAIL"|"ADVISORY", source: string|null, recorded_at }
  interface AuditActivityEntry { id, design_id, design_title, actor, action, affected_entity, summary, timestamp, origin }
  interface ActivityFeedResponse { entries, total, page, page_size, from_date, to_date }
  ```
  Plus hooks: `useGovernanceStatus()`, `useComplianceExceptions()`, `useActivityFeed(fromDate, toDate, action?, actor?, page?)`, and function `downloadActivityCSV(fromDate, toDate, action?, actor?)` that creates an anchor element and triggers a download; all use `apiGet` from `../api/client`
- [X] T018 [US1] Create `web/src/governance/DesignStatusTab.tsx` — sortable table with columns: Design (title + lifecycle badge), Last Activity (formatted datetime or "—"), Activity Count, Accepted Recs, Reasoning Records; sort by clicking column headers; click row calls `onSelectDesign(design_id)` then `onNavigate("intake")`; empty state "No designs found"; loading skeleton rows; fetches via `useGovernanceStatus()`

**Checkpoint**: Design Status tab renders table with sort and row-click navigation.

---

## Phase 3: US2 — Compliance Exceptions Tab

*Architect sees only FAIL and ADVISORY validation findings across all designs. FAIL sorted first. Click opens that design.*

**Independent test criteria**: List shows only FAIL/ADVISORY findings; FAIL rows show red badge, ADVISORY amber; info findings absent; empty state "No compliance exceptions — all designs are clean" when list is empty.

- [X] T019 [US2] Create `web/src/governance/ComplianceTab.tsx` — exception list sorted FAIL-first; each row: design title (with lifecycle badge), finding summary text, severity badge (red "FAIL" / amber "ADVISORY"), source text (right-aligned, greyed); click row calls `onSelectDesign(design_id)` + `onNavigate("intake")`; empty state "No compliance exceptions — all designs are clean"; loading skeleton; fetches via `useComplianceExceptions()`

**Checkpoint**: Compliance tab renders exception list with FAIL-first sort and correct severity badges.

---

## Phase 4: US3 — Activity Feed Tab + CSV Export

*Architect can view paginated audit log filtered by date range, action type, and actor. Can export filtered results as CSV.*

**Independent test criteria**: Date range defaults to last 30 days on mount; changing action-type dropdown filters entries; clicking Export CSV triggers file download with correct filename pattern `adp-audit-YYYY-MM-DD-YYYY-MM-DD.csv`; submitting a 91-day range shows validation error.

- [X] T020 [US3] Create `web/src/governance/ActivityFeedTab.tsx`:
  - State: `fromDate` (default: today − 30 days), `toDate` (default: today), `actionFilter: string`, `actorFilter: string`, `page: number`
  - Controls: two date inputs, action-type dropdown (hardcoded list from `contracts/api.md` action types), actor text input, "Apply" button, "Export CSV" button
  - Validate date range client-side: show inline error "Date range cannot exceed 90 days" if >90 days (does not call API)
  - Render paginated entry list: each entry shows timestamp, actor, action badge, design title, summary; pagination controls (Prev / Page N of M / Next)
  - "Export CSV" calls `downloadActivityCSV(fromDate, toDate, actionFilter, actorFilter)` with current filters
  - Loading skeleton; empty state "No activity in this date range"; fetches via `useActivityFeed()`

**Checkpoint**: Activity feed shows filtered paginated entries; CSV export downloads with correct headers.

---

## Phase 5: Governance Page + App Integration

*Assembles the three tabs into a navigable page, wires it to the Portfolio screen and main App.*

- [X] T021 Create `web/src/governance/GovernancePage.tsx` — three-tab layout (`Design Status`, `Compliance`, `Activity Feed`); tab state managed locally; passes `onSelectDesign` and `onNavigate` down to each tab; "← Portfolio" back button calls `onNavigate("portfolio")`; accepts props `onNavigate: (view: AppView) => void` and `onSelectDesign: (id: string) => void`
- [X] T022 Edit `web/src/portfolio/PortfolioPage.tsx` — ensure "Governance Report" button calls `onNavigate("governance")` (this was planned in spec 031 tasks T020; confirm it exists and wires correctly; add if missing)
- [X] T023 Edit `web/src/App.tsx` — extend `AppView` union type to include `"governance"`; import `GovernancePage`; add render branch: `if (view === "governance") return <GovernancePage onNavigate={setView} onSelectDesign={handleSelectDesign} />`
- [X] T024 [P] Run `cd web && npx tsc --noEmit` — zero TypeScript errors

---

## Phase 6: Polish

- [X] T025 [P] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite passes (including governance + portfolio contract tests)
- [X] T026 [P] Run `ruff check src/adp/api/routers/governance.py` — zero errors
- [X] T027 [P] Run `cd web && npx tsc --noEmit` — final TypeScript confirmation
- [X] T028 Manual E2E: navigate to Portfolio → click "Governance Report"; verify Design Status tab loads table with all designs; click column header to sort; switch to Compliance tab; verify FAIL items appear before ADVISORY; switch to Activity Feed; set 30-day range; verify entries load; click Export CSV; verify `adp-audit-*.csv` downloads with id/design_id/actor columns; click "← Portfolio" returns to Portfolio screen

---

## Dependencies

```
T001–T009 (tests) written in parallel; all independent
T010 (Pydantic models) → T011, T012, T013, T014   (models before endpoints)
T015 (register router) → T016                       (router must exist for test client)
T016 (backend tests pass) → T017                    (confirm contracts before TS types)
T017 (TS interfaces + hooks) → T018, T019, T020    (types before components)
T018, T019, T020 → T021                             (all tabs before GovernancePage)
T021 → T022, T023                                   (page before app wiring)
T023 → T024                                         (TypeScript check after all edits)
T025, T026, T027 are independent polish checks
```

## Parallel Opportunities

- T001–T009: all 9 contract tests can be written simultaneously
- T017 (TS hooks) and T018 (DesignStatusTab) share no files — parallel
- T019 (ComplianceTab) and T020 (ActivityFeedTab) share no files — parallel
- T025, T026, T027 all run independently

## Implementation Strategy (MVP)

**MVP = Phase 1 + Phase 2 + Phase 5 (T001–T018, T021–T023)**

Delivers: Governance page accessible from Portfolio with working backend and the Design Status tab. Compliance tab (US2) and Activity Feed tab (US3) follow as fast increments once US1 structure is proven.
