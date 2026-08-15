---
document_type: sdd-spec
title: Application Health Score — Structured Assessment Popup
status: implemented
audience: ADP engineering, SDD reviewers
last_updated: 2026-08-15
decisions_made:
  - "Q1 (persist per-dimension answers): YES -- resolved 2026-08-15"
  - "Q2 (require all six dimensions): YES -- resolved 2026-08-15"
  - "Q3 (Overview tab also gets an entry point): YES -- resolved 2026-08-15"
  - "Q4 (button label): \"Assess Health\" confirmed -- resolved 2026-08-15"
  - "Q5 (reject direct PATCH health_score writes): YES, reject -- resolved 2026-08-15"
depends_on:
  - health-table.md
---

# Application Health Score — Structured Assessment Popup

## 1. Problem

`Application.health_score` is currently a bare 1–5 number, hand-typed into a
plain number input on the Application edit form (`ApplicationForm.tsx`,
"Health Score (1–5)"). There is no guidance on what a 3 means versus a 4, no
consistency across architects filling it in, and no record of *why* a given
score was assigned — it's a single opaque digit. `docs/health-table.md`
already defines a structured rubric across six dimensions; this spec turns
that rubric into the actual mechanism for setting the score, replacing free
entry with a guided assessment.

## 2. Scope

**In scope:**
- `health_score` on the Application edit screen becomes **read-only display
  only** (no direct typing).
- A new **"Assess Health"** button next to it opens a popup.
- The popup renders the six-dimension rubric from `docs/health-table.md` as a
  table; each dimension row gets one radio button per score column (1–5),
  mutually exclusive within the row.
- The six individual dimension selections are **persisted** (resolved §8 Q1,
  2026-08-15) as their own data, one current answer per dimension per
  application — see §5.
- **All six dimensions are required** — Save stays disabled until every
  dimension has a selection, enforced both client-side (button disabled) and
  server-side (`PUT` rejects a partial submission) — resolved §8 Q2.
- A **Save** button submits all six selections in one call; the server
  computes `health_score = MIN(submitted scores)` and stores both the six
  answers and the derived `health_score` atomically — see §6.
- **Reachable from both the Edit form and the read-only Overview tab**
  (resolved §8 Q3) — not Edit-form-only as originally scoped.
- Because answers are persisted, reopening the popup on an application with
  a prior assessment **pre-fills** each dimension's radio group with its
  last-saved answer (a direct consequence of the Q1 persist decision).
- A **Cancel** action that discards any in-progress (unsaved) changes and
  closes the popup without touching stored data.

**Out of scope:**
- Any change to the Application read-only Overview tab's existing star
  display (`"★".repeat(app.health_score)`) — untouched.
- A history/audit trail of past assessments — each dimension stores its
  *current* answer only; a new assessment overwrites the prior one rather
  than appending to a log. (Revisit as a follow-on if the audit-trail value
  noted in the original Q1 discussion turns out to matter in practice.)
- Any change to `business_criticality` or other unrelated 1–5 score fields on
  Application — this spec only touches `health_score`.

## 3. Health Assessment Rubric (source: `docs/health-table.md`)

Embedded verbatim so the popup's copy has one obvious source of truth to stay
in sync with. If `health-table.md` changes, this table (and the UI copy it
drives) must be updated together.

| Dimension | 1 — Critical | 2 — At Risk | 3 — Fair / Watch | 4 — Healthy | 5 — Thriving |
|---|---|---|---|---|---|
| **Stability & Incidents** | Severe or continuous outages; core function is unreliable or unusable. | Frequent or high-impact incidents; SLA regularly missed; user-facing disruption. | Recurring minor incidents or occasional workarounds; SLA occasionally missed. | Rare, low-impact incidents; quickly resolved; SLA met. | No incidents; consistently meets or exceeds uptime/SLA targets. |
| **Technical Currency & Debt** | Running on end-of-life or unsupported infrastructure with no upgrade path. | Key platform(s) or dependencies unsupported or nearing end-of-life; no funded upgrade plan. | Some components aging without a firm upgrade plan; moderate accumulated debt. | Mostly current; minor debt with a funded or scheduled upgrade path. | All platforms and dependencies on current, vendor-supported versions; minimal debt. |
| **Security Posture** | Known exploitable or critical vulnerabilities; failing compliance requirements. | Known unpatched high-severity vulnerabilities or overdue audit findings. | Some medium-severity findings open past target remediation date. | Only low-severity findings open, with remediation on track. | No known vulnerabilities; passes current audits; patching is current. |
| **Support & Team Capacity** | No one able to support it; original team or vendor is gone. | No dedicated owner or team; support is ad hoc or purely reactive. | Owner identified but thinly resourced; single point of failure on key knowledge. | Clear owner; adequately resourced; minor bus-factor risk. | Clear owner; well-resourced team; more than one person can support it. |
| **Documentation & Knowledge** | No usable documentation; knowledge is effectively lost. | Documentation is sparse; knowledge lives mostly in a few people's heads. | Documentation exists but is outdated or incomplete in key areas. | Good documentation with minor gaps. | Comprehensive, current documentation; onboarding is straightforward. |
| **Business Value & Criticality Alignment** | Value no longer justifies its cost, risk, or existence; candidate for retirement. | Cost or risk is starting to outweigh the value delivered. | Value is unclear, declining, or only partially understood. | Solid, understood value; cost and risk are justified. | Clearly delivers strong, well-understood business value relative to its cost and risk. |

Radio buttons occupy every cell from the 2nd row / 2nd column onward (i.e.
every rating cell, excluding the header row and the Dimension label column).
One radio group per dimension row (6 groups total, 5 options each).

## 4. Interaction Design

**Trigger — two entry points (resolved §8 Q3):**
1. **Edit form** (`ApplicationForm.tsx`): the existing "Health Score (1–5)"
   number input is replaced by a read-only display of the current score
   (e.g. `Health: ★★★☆☆ (3)` or `Health: — not assessed —` if `null`) plus
   an **"Assess Health"** button (label confirmed, §8 Q4) that opens the
   popup. Disabled in New-application mode (see below).
2. **Overview tab** (`ApplicationDetail.tsx`'s existing read view, where
   `app.health_score` is already shown as stars): gains the same
   **"Assess Health"** button next to that display, opening the identical
   popup. Since the popup's Save is already its own independent, immediate
   write (not routed through `ApplicationForm`'s state, per below), this
   needs no "enter edit mode first" step — it's a direct action from the
   read view, gated by the same write-permission the app already enforces
   for editing an Application (no new permission concept introduced here).

**New-application mode:** the Edit-form button is disabled (with a short
explanatory note, e.g. "Save the application first, then assess health")
rather than open — the six answers persist against a real `application_id`
(§5), which doesn't exist until the application's first Save. This keeps the
popup's Save a single atomic call against a real resource rather than
needing a two-phase create-then-assess flow. (Not applicable to the Overview
tab entry point, since that view only exists for already-saved applications.)

**Popup, on open:** fetches the application's current per-dimension answers
(`GET`, §6). If none exist yet (first-ever assessment), every radio group
opens unselected. If a prior assessment exists, each dimension's radio group
pre-selects its last-saved value.

**Popup, Save button:**
- Disabled until all six dimensions have a selection (resolved §8 Q2).
- Submits the selected dimension scores in one call (`PUT`, §6). The server
  — not the client — computes `health_score = MIN(submitted scores)` and
  writes both the six answers and the derived `health_score` in the same
  transaction, so the two can never drift out of sync.
- This is an independent, immediately-persisted action (mirrors the
  Business/Technical Capability Domain-assignment "Assign" pattern) — it does
  **not** route through `ApplicationForm`'s own Save button or local state;
  clicking it saves immediately and the popup closes on success. The parent
  form's read-only score display refreshes via query invalidation.

**Popup, Cancel button:** discards any in-progress, unsaved radio changes and
closes — no network call, no change to previously-saved data.

## 5. Data model

`applications.health_score` itself needs no schema change — it already
exists (`Score15`-equivalent, 1–5, nullable). New table for the six
per-dimension answers:

**`application_health_assessment`** (new table)

| Column | Type | Notes |
|---|---|---|
| `application_id` | TEXT FK → applications, `ON DELETE CASCADE` | part of PK |
| `dimension` | TEXT | part of PK; CHECK constraint, one of the six §3 row keys (`stability_incidents`, `technical_currency_debt`, `security_posture`, `support_team_capacity`, `documentation_knowledge`, `business_value_criticality`) |
| `score` | SmallInteger | CHECK 1–5 |
| `assessed_at` | TIMESTAMPTZ | overwritten on re-assessment |
| `assessed_by` | TEXT | actor, matches existing "who did this" convention (plain TEXT, no `users` table) |

PK: `(application_id, dimension)` — one *current* answer per dimension per
application; a re-assessment upserts in place rather than appending (no
history, per §2).

`applications.health_score` continues to be the single derived value read
everywhere else in the app (Overview stars, portfolio heat maps, etc.) — it
is written by the same transaction that upserts the six rows below it (§6),
never edited independently once this ships.

## 6. API surface

New sub-resource under the existing applications router, following the
established one-router-per-domain-object pattern:

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/applications/{id}/health-assessment` | Returns the six current dimension answers (each `null`/absent if never assessed) plus the current `health_score`. Ungated read, consistent with other Application sub-resource reads. |
| `PUT` | `/api/v1/applications/{id}/health-assessment` | Body: all six dimension scores, all required (400 on a partial submission — resolved §8 Q2). Upserts the six `application_health_assessment` rows and recomputes `applications.health_score = MIN(scores)` in one transaction. Returns the updated assessment + score. Same write permission as the existing `PATCH /applications/{id}`. |

**Resolved §8 Q5:** the existing `PATCH /api/v1/applications/{id}` rejects any
request body that includes `health_score` (400, with a message pointing at
the new endpoint) once this ships — `ApplicationUpdate.health_score` is
removed from the writable field set (validated at the model/router layer,
not just a UI-level omission), so `health_score` can only ever change through
`PUT .../health-assessment`, and can never silently drift from the six
answers behind it.

## 7. UI / screen impact

- `ApplicationForm.tsx`: remove the free "Health Score (1–5)" number input;
  add the read-only display + "Assess Health" button described in §4
  (disabled in New-application mode, per §4). Also drop `healthScore`
  local state and its inclusion in the create/update payload — `health_score`
  is no longer settable through this form's own Save at all (§6 Q5).
  `ApplicationCreate`/`ApplicationUpdate`'s TS types lose the `health_score`
  field to match the backend model change.
- `ApplicationDetail.tsx`: the Overview tab's existing star display gains an
  adjacent "Assess Health" button (§4, §8 Q3), opening the same popup used
  from the Edit form.
- New shared component, e.g. `HealthAssessmentModal.tsx` (used from both
  entry points above): renders the §3 rubric as a radio-button table;
  fetches current answers on open (`GET`, §6), submits on Save (`PUT`, §6),
  Save disabled until all six dimensions are answered (§8 Q2). Rubric copy
  (dimension names + all 30 cell descriptions) is a hardcoded TS constant
  transcribed from `docs/health-table.md` (mirrors how other rubric-style
  copy is hardcoded elsewhere in this codebase, e.g.
  `STRATEGIC_RELEVANCE_LABEL`) — not parsed from the Markdown file at
  runtime.
- New API hooks in `web/src/api/application.ts`: a query hook for `GET
  .../health-assessment` and a mutation hook for `PUT .../health-assessment`
  that invalidates the application detail query on success, mirroring this
  codebase's established TanStack Query conventions.

## 8. Decisions (all open questions resolved 2026-08-15)

| # | Question | Decision |
|---|---|---|
| Q1 | Persist the six dimension answers, or compute-and-discard? | **Persist** — new `application_health_assessment` table, §5. |
| Q2 | Require all six dimensions before Save enables, or allow partial? | **Require all six**, enforced client- and server-side. |
| Q3 | Should the read-only Overview tab also get an entry point, or Edit-form only? | **Both** — Overview tab gains its own "Assess Health" button alongside the Edit form's. |
| Q4 | Final button/label copy? | **"Assess Health"** confirmed. |
| Q5 | Should `PATCH /applications/{id}` still accept a direct `health_score` write? | **No** — rejected (400); `health_score` is only ever set via `PUT .../health-assessment`. |

This spec is ready for implementation. No remaining open questions.
