# Implementation Plan: Governance Reporting Dashboard (ADP-SPEC-032)

**Branch**: `032-governance-reporting` | **Date**: 2026-07-05 | **Spec**: [spec.md](./spec.md)

## Summary

Adds a Governance Reporting Dashboard accessible from the Portfolio screen (ADP-SPEC-031). Three tabs: Design Status (aggregated per-design audit + reasoning counts), Compliance Exceptions (FAIL/ADVISORY findings from design JSONB), and Activity Feed (paginated audit log with date-range filter and CSV export). Backend is 4 read-only endpoints querying existing tables — no new DB tables, no new migrations, no new Python packages.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: Python stdlib `csv` module for CSV export; all else existing stack — zero new packages
**Storage**: PostgreSQL 16; reads from `audit_entries`, `designs`, `design_versions.content` (JSONB for findings), `operations`, `llm_reasoning_log` — no new migrations
**Testing**: pytest + FastAPI TestClient; existing contract test patterns
**Target Platform**: Same as ADP
**Performance Goals**: SC-001 — governance status report loads in under 5 seconds for 10-design portfolio; SC-003 — CSV export under 5 seconds for 1,000 entries
**Constraints**: Read-only; no new DB tables; 90-day CSV window enforced server-side; findings sourced from design JSONB (acceptable for 100-design portfolio at current scale)

## Constitution Check

| Article | Requirement | This Plan |
|---|---|---|
| ART-I | Spec-driven | Plan derived from spec.md ✅ |
| ART-II | Model is source of truth | Compliance exceptions sourced from canonical model JSONB (findings[]); audit data from audit_entries (immutable per ART-IX) ✅ |
| ART-IV | TDD | Contract tests before implementation ✅ |
| ART-V | Security | Auth required on all governance endpoints ✅ |
| ART-IX | Audit trail | Governance report exposes audit trail data; no new audit writes needed ✅ |
| ART-XIII | Typed contracts | All response shapes typed Pydantic models (backend) and TypeScript interfaces (frontend) ✅ |

## File Changes

| File | Action |
|---|---|
| `src/adp/api/routers/governance.py` | CREATE — 4 read-only endpoints |
| `src/adp/api/app.py` | EDIT — register governance router |
| `tests/contract/test_governance_api.py` | CREATE — contract tests |
| `web/src/api/governance.ts` | CREATE — TypeScript interfaces + TanStack Query hooks |
| `web/src/governance/GovernancePage.tsx` | CREATE — three-tab layout |
| `web/src/governance/DesignStatusTab.tsx` | CREATE — sortable governance table |
| `web/src/governance/ComplianceTab.tsx` | CREATE — exceptions list |
| `web/src/governance/ActivityFeedTab.tsx` | CREATE — paginated feed + CSV export |
| `web/src/portfolio/PortfolioPage.tsx` | EDIT — add "Governance Report" button that sets view to governance |
| `web/src/App.tsx` | EDIT — add "governance" to AppView + render GovernancePage |

## Phase 1: Backend Governance API

**Goal**: 4 read-only endpoints covering the three report tabs.

### Tests first (TDD — ART-IV)

- [ ] Write `tests/contract/test_governance_api.py` — `test_status_returns_all_designs()`: mock DB; GET /governance/status; assert response has design records with correct fields (design_id, title, lifecycle_status, audit_count)
- [ ] Write `test_status_handles_design_with_no_activity()`: design with 0 audit entries still appears with zeros
- [ ] Write `test_exceptions_returns_only_fail_advisory()`: seed design with critical + info findings; GET /governance/exceptions; assert only critical finding returned, info excluded
- [ ] Write `test_activity_requires_date_range()`: GET /governance/activity without dates; assert 422
- [ ] Write `test_activity_rejects_range_over_90_days()`: from_date + 91 days; assert 422
- [ ] Write `test_activity_export_returns_csv()`: GET /governance/activity/export; assert Content-Type text/csv and Content-Disposition header
- [ ] Write `test_activity_filter_by_action()`: seed entries; GET with `?action=lifecycle-transition`; assert only matching entries returned

### Implementation

- [ ] Create `src/adp/api/routers/governance.py` with:
  - Pydantic models: `DesignGovernanceRecord`, `ComplianceExceptionRecord`, `AuditActivityEntry`, `ActivityFeedResponse`
  - `GET /api/v1/governance/status` — single aggregating SQL JOIN across `designs`, `audit_entries`, `operations`, `llm_reasoning_log`; loads `ArchitectureDescription` for each design to extract findings separately (two-pass for compliance data)
  - `GET /api/v1/governance/exceptions` — loads all designs, extracts `findings[]` with `severity IN ('warning','critical')`, maps severity to FAIL/ADVISORY
  - `GET /api/v1/governance/activity` — paginated query on `audit_entries` JOIN `designs.title`; enforces 90-day window
  - `GET /api/v1/governance/activity/export` — same as activity but no pagination; returns `StreamingResponse` with CSV using Python stdlib `csv`
  - Uses `Depends(_get_kb_session)` from `adp.api.deps` for DB access (shared pool)
- [ ] Register `governance.router` in `src/adp/api/app.py`

**Checkpoint**: All governance contract tests pass.

## Phase 2: Frontend Governance Screen

**Goal**: Three-tab governance dashboard accessible from the Portfolio screen.

- [ ] Create `web/src/api/governance.ts` — TypeScript interfaces + hooks: `useGovernanceStatus()`, `useComplianceExceptions()`, `useActivityFeed(fromDate, toDate, action?, actor?, page?)`, and a `downloadActivityCSV(fromDate, toDate, action?, actor?)` function
- [ ] Create `web/src/governance/DesignStatusTab.tsx` — sortable table; columns: Design (with lifecycle badge), Last Activity, Activity Count, Accepted Recs, Reasoning Records; click row opens that design's Intake view
- [ ] Create `web/src/governance/ComplianceTab.tsx` — exception list sorted FAIL-first; each row shows design, finding summary, severity badge (red/amber), source; click opens design; empty state when clean
- [ ] Create `web/src/governance/ActivityFeedTab.tsx` — date pickers (default: last 30 days), action-type dropdown, actor filter input; paginated entry list; "Export CSV" button calls `downloadActivityCSV` with current filters
- [ ] Create `web/src/governance/GovernancePage.tsx` — three-tab layout (`<DesignStatusTab>`, `<ComplianceTab>`, `<ActivityFeedTab>`); "← Back to Portfolio" button that calls `onNavigate("portfolio")`; tab state managed locally
- [ ] Edit `web/src/portfolio/PortfolioPage.tsx` — add "Governance Report" button/link that calls `onNavigate("governance")`
- [ ] Edit `web/src/App.tsx` — extend `AppView` to include `"governance"`; render `<GovernancePage>` when `view === "governance"`
- [ ] Run `cd web && npx tsc --noEmit` — TypeScript clean

## Phase 3: Polish

- [ ] Run `pytest tests/ --ignore=tests/integration -q --no-cov` — full suite passes
- [ ] Run `ruff check src/adp/api/routers/governance.py` — clean
- [ ] Run `cd web && npx tsc --noEmit` — zero errors
- [ ] Manual E2E: navigate to Portfolio → click Governance Report; verify Design Status table shows all designs; switch to Compliance tab; verify only FAIL/ADVISORY exceptions shown; switch to Activity Feed; set date range; verify entries load; click Export CSV; verify file downloads with correct columns

## Constitution Compliance

- **ART-II** ✅ Compliance exceptions sourced from canonical `ArchitectureDescription.findings[]` — canonical model is authoritative
- **ART-IV** ✅ Contract tests written before implementation in Phase 1
- **ART-IX** ✅ Governance report surfaces existing immutable audit trail; no new audit writes introduced
- **ART-XIII** ✅ All API responses are fully typed Pydantic models

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]  
**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]  
**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]  
**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]  
**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]
**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]  
**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]  
**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]  
**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
