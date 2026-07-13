# Feature Specification: Governance Reporting Dashboard

**Feature Branch**: `032-governance-reporting`
**Created**: 2026-07-05
**Status**: Draft
**Depends on**: ADP-SPEC-027 (LLM Reasoning Store), ADP-SPEC-030 (Design Lifecycle)
**Can be implemented in parallel with**: ADP-SPEC-031 (Portfolio Analysis)

## Context

ADP generates a substantial amount of governance-relevant data through its normal operation: every design change is recorded in an audit log, every AI recommendation produces a reasoning record, every validation run produces verdicts. But none of this data is currently surfaced in a governance-facing format.

Enterprise architecture governance boards need evidence. They need to answer: "Which designs have been formally reviewed this quarter?", "Which designs have outstanding validation failures?", "Who accepted AI recommendations without checking the reasoning?", "What is our architecture team's activity over the past 30 days?". This data already exists in ADP's tables — it just needs a reporting surface.

This spec adds a Governance Reporting Dashboard — a dedicated screen accessible from the Portfolio view — that presents three reports from existing data: a per-design governance status table, a compliance exceptions list, and an audit activity feed. No new data collection is required — only new queries and display.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-IV** — Test-Driven Development: always applies
- **ART-IX** — Audit Trail: this spec surfaces the audit trail data (ART-IX) in a human-readable governance format; no new audit writes required
- **ART-XI** — Traceability: the governance report connects decisions (accepted recommendations) to their AI reasoning records (ADP-SPEC-027) and their audit entries

## Threat Model

**Assets at risk**: Governance reports expose internal decision history — who accepted AI recommendations, what validation findings were recorded, architect activity patterns. Sensitive in regulated environments.

**Trust boundaries crossed**: Browser → ADP API (read-only governance query endpoints).

**Abuse cases**:
- Surveillance of individual architects' activity: mitigated by requiring authentication (ADP-SPEC-026); activity is visible to all authenticated architects (no per-user data hiding in v1). This is accepted — ADP is a collaborative tool, audit trail is intentionally transparent.
- CSV export of full audit history to exfiltrate: mitigated by requiring authentication; exports are bounded to the date range requested (max 90 days per export).

**Residual risk**: No role-based restriction on who can see governance reports in v1. Any authenticated user can see all activity. Accepted for single-tenant, trusted-team deployment.

## User Scenarios & Testing

### User Story 1 — Design Governance Status Report (Priority: P1)

An EA governance lead opens the Governance screen before a monthly review board meeting. She sees a table listing every design with: its lifecycle status, the date of its last activity, how many validation verdicts it has received (with a pass/fail/advisory breakdown), how many AI recommendations were accepted, and how many LLM reasoning records are available. She can sort by "most recently active" to identify which designs need attention.

**Why this priority**: The governance status report is the primary artifact the spec produces — it synthesises all the existing ADP data into one view that a governance board can consume directly.

**Independent Test**: With 2 designs, one with 3 audit entries + 1 failed verdict and one with 0 audit entries, the governance table shows both with correct counts; sorting by activity puts the active design first.

**Acceptance Scenarios**:

1. **Given** designs in the system, **When** the Governance screen loads, **Then** a table shows one row per design with: title, lifecycle status badge, last activity date, validation verdict count (pass/advisory/fail), accepted recommendation count, and reasoning record count.
2. **Given** the governance table is displayed, **When** an architect clicks a column header, **Then** the table sorts by that column (ascending/descending toggle).
3. **Given** a design has no audit activity, **Then** its "last activity" shows "—" and its counts show 0.
4. **Given** a design has failed validation verdicts, **Then** its verdict count displays the fail count prominently (e.g. in red).

---

### User Story 2 — Compliance Exceptions Report (Priority: P1)

An architect responsible for standards compliance opens the Compliance Exceptions tab. She sees a list of designs that have LLM-as-a-judge validation findings rated as FAIL or ADVISORY (from the existing validation layer). Each exception shows: the design name, the specific principle or standard that was flagged, the finding severity, and the date the finding was recorded. She can click a finding to open the relevant design.

**Why this priority**: Compliance exceptions are the core governance deliverable — the list of open findings that the organisation has committed to address.

**Independent Test**: With a design that has one FAIL verdict and one PASS verdict, the compliance exceptions list shows only the FAIL finding; the PASS finding is not shown.

**Acceptance Scenarios**:

1. **Given** validation verdicts exist in the system, **When** the Compliance Exceptions tab is selected, **Then** only FAIL and ADVISORY findings are shown; PASS verdicts are excluded.
2. **Given** compliance exceptions are listed, **Then** each row shows: design title, finding summary, severity (FAIL / ADVISORY), and date recorded.
3. **Given** a compliance exception row is clicked, **Then** the user is taken to the relevant design's canvas view.
4. **Given** no compliance exceptions exist, **Then** a "No outstanding compliance exceptions" success state is shown.

---

### User Story 3 — Audit Activity Feed (Priority: P2)

A portfolio manager wants to review who has been making changes to the architecture over the past two weeks. She opens the Activity Feed tab, sets the date range to the last 14 days, and sees a chronological list of all audit entries across all designs — who did what, when, and to which design. She can filter by action type (e.g. "show only lifecycle transitions") and export the filtered results to CSV.

**Why this priority**: The activity feed is the governance evidence trail — it proves to auditors that architecture decisions are being recorded and reviewed.

**Acceptance Scenarios**:

1. **Given** audit entries exist across multiple designs, **When** the Activity Feed tab is selected, **Then** a paginated list shows entries sorted by timestamp descending (most recent first).
2. **Given** the activity feed, **When** an architect sets a date range filter, **Then** only entries within that range are shown.
3. **Given** the activity feed, **When** an architect selects an action type filter (e.g. "lifecycle-transition"), **Then** only entries matching that action are shown.
4. **Given** filtered results are shown, **When** the architect clicks "Export CSV", **Then** a CSV file downloads containing all filtered entries (not just the current page) up to the 90-day limit.

---

### Edge Cases

- System with 0 designs: all reports show empty states with helpful messages.
- Designs created before ADP-SPEC-027 (no reasoning records): reasoning count shows 0; no error.
- Designs created before validation was introduced: verdict counts show 0; no error.
- CSV export with large date range (>90 days): request rejected with a message asking to narrow the range; max 90 days enforced.
- Audit entries from before individual design tracking: gracefully excluded from per-design reports.

## Requirements

### Functional Requirements

**Governance Data API (FR-001 to FR-006)**

- **FR-001**: `GET /api/v1/governance/status` MUST return a list of per-design governance records including: `design_id`, `title`, `lifecycle_status`, `last_activity` (timestamp of most recent audit entry), `verdict_counts: {pass, advisory, fail}`, `accepted_recommendations`, `reasoning_record_count`. Queries join the `designs`, `audit_entries`, `operations`, and `llm_reasoning_log` tables.
- **FR-002**: `GET /api/v1/governance/exceptions` MUST return all FAIL and ADVISORY validation findings across all designs, including: `design_id`, `title`, `finding_summary`, `severity`, `recorded_at`. Sourced from `audit_entries` with `action = 'verdict'` or from the findings recorded in design content.
- **FR-003**: `GET /api/v1/governance/activity` MUST accept `from_date`, `to_date`, and optional `action_type` query parameters and return paginated audit entries across all designs sorted by timestamp descending. `from_date` and `to_date` must be within a 90-day window.
- **FR-004**: `GET /api/v1/governance/activity/export` MUST return all filtered audit entries (not paginated) as a CSV response with `Content-Disposition: attachment; filename="adp-audit-{from}-{to}.csv"`. Enforces the 90-day window.
- **FR-005**: All governance query endpoints MUST respond in under 3 seconds for a portfolio of 100 designs with 12 months of audit history.
- **FR-006**: The governance status endpoint MUST handle designs with no audit entries, no verdicts, and no reasoning records without error — returning zero counts for those fields.

**Governance Screen (FR-007 to FR-014)**

- **FR-007**: A "Governance" link MUST be accessible from the Portfolio screen (either as a tab or a top-level navigation button). It does not need to appear in the main `NavBar` alongside Intake/Recommendations/Canvas/Knowledge/Portfolio.
- **FR-008**: The Governance screen MUST have three tabs: "Design Status", "Compliance Exceptions", and "Activity Feed".
- **FR-009**: The Design Status tab MUST render the data from FR-001 as a sortable table. Columns: Design, Status, Last Activity, Verdicts (pass/advisory/fail breakdown), Accepted Recs, Reasoning Records.
- **FR-010**: The Compliance Exceptions tab MUST render data from FR-002 as a list sorted by severity descending (FAIL before ADVISORY), then by date descending.
- **FR-011**: The Activity Feed tab MUST render paginated audit entries (FR-003) with date-range pickers (default: last 30 days) and an action-type filter dropdown.
- **FR-012**: The Activity Feed tab MUST include an "Export CSV" button that calls FR-004 and triggers a browser download.
- **FR-013**: All three report tabs MUST show loading skeletons while data is fetching and error states if queries fail.
- **FR-014**: Clicking a design in any report tab MUST navigate the user to the Intake view for that design.

### Key Entities

- **DesignGovernanceRecord**: `design_id`, `title`, `lifecycle_status`, `last_activity`, `verdict_counts`, `accepted_recommendations`, `reasoning_record_count`
- **ComplianceException**: `design_id`, `title`, `finding_summary`, `severity`, `recorded_at`
- **AuditActivityEntry**: `id`, `design_id`, `design_title`, `actor`, `action`, `affected_entity`, `summary`, `timestamp`

## Success Criteria

- **SC-001**: A governance lead can produce the Design Status report for a 10-design portfolio in under 5 seconds from opening the Governance screen.
- **SC-002**: The Compliance Exceptions report correctly shows only FAIL and ADVISORY findings, with zero false positives (PASS findings never appear).
- **SC-003**: The Activity Feed export produces a valid CSV file containing all audit entries in the specified date range, downloadable in under 5 seconds for up to 1,000 entries.
- **SC-004**: All three report tabs handle the zero-data case (new ADP installation with no designs) without errors.

## Assumptions

- Verdict data is sourced from the `audit_entries` table where `action` matches validation-related actions (the exact action strings are determined during planning from the existing codebase).
- Accepted recommendation count is derived from `audit_entries` where `action = 'accept-recommendation'`.
- Reasoning record count is sourced from `llm_reasoning_log` via count by `design_id` (cross-referenced through `operations` table).
- The governance screen is accessible from the Portfolio screen (ADP-SPEC-031) via a button or link, not as a top-level nav tab, to keep the main navigation uncluttered.
- CSV export uses the browser's native download mechanism (Blob + URL.createObjectURL), consistent with the existing CALM export pattern.
- No email or scheduled report delivery in v1.
