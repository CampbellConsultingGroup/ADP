---
document_type: sdd-spec
title: Application Business Value — Structured Weighted Assessment Popup
status: approved
audience: ADP engineering, SDD reviewers
last_updated: 2026-08-15
decisions_made:
  - "Entity: Application.business_value (mirrors Health exactly) -- resolved 2026-08-15"
  - "Aggregation: weighted average + Evidence & Measurability soft cap -- resolved 2026-08-15"
  - "Weights: EA-prioritized scheme (section 5.1), confirmed as proposed -- resolved 2026-08-15"
  - "Rounding: round-half-up to nearest integer -- resolved 2026-08-15"
  - "Shared modal: extract HealthAssessmentModal + this into one generic component -- resolved 2026-08-15"
  - "Cap math display: always shown, not conditional on whether it binds -- resolved 2026-08-15"
depends_on:
  - business_value.md
  - application-health-assessment-spec.md
---

# Application Business Value — Structured Weighted Assessment Popup

## 1. Problem

Same problem as `health_score` before `application-health-assessment-spec.md`:
`Application.business_value` is a bare 1–5 number, hand-typed into a plain
number input on the Edit form, with no guidance and no record of *why* a
given score was assigned. `docs/business_value.md` defines a structured
six-dimension rubric; this spec turns that rubric into the mechanism for
setting the score — **same interaction shape as Health, different math**
(resolved with the user before writing this spec — see frontmatter).

## 2. Scope

**In scope — everything Health established, applied to `business_value`:**
- `business_value` on the Application Edit form becomes **read-only
  display only**; a new **"Assess Business Value"** button opens a popup.
- The popup renders the six-dimension rubric (§3) as a table; one radio
  group per dimension, all six required before Save enables.
- The six individual dimension selections are **persisted** (one current
  answer per dimension per application, upserted on re-assessment — no
  history, matching Health's own scoping call).
- Reachable from **both** the Edit form and the read-only Overview tab.
- Disabled in New-application mode (no `application_id` yet).
- `PATCH /applications/{id}` rejects `business_value` outright once this
  ships — same reasoning as Health's Q5 (a value provably derived from a
  real assessment, never independently editable).

**Different from Health — the math (§5):**
- Health: `health_score = MIN(six scores)` — a risk gate.
- Business Value: `business_value = round_half_up(min(weighted_average(six scores), cap(evidence_score)))`
  — a weighted composite with a soft ceiling, not a hard gate. See §5 for
  the full mechanics, weights, and cap table.

**Out of scope:**
- `business_criticality` (Application's sibling field) — untouched, exactly
  as Health left `maturity_level`/`business_criticality` alone.
- Business Capability's own (currently nonexistent) business-value concept
  — this spec is Application-only, per the resolved entity decision. If
  Capability-level business value is wanted later, it's a separate spec
  (the rubric content could likely be reused; the aggregation/persistence
  layer would not, since it's a different table/entity).
- Any live computation from linked Strategic Objectives/capabilities (e.g.
  auto-deriving "Strategic Alignment" from actual `objective_application_links`
  rows) — this is a qualitative self-assessment popup, same as Health;
  nothing here is auto-computed from other ADP data.
- A history/audit trail of past assessments (same call as Health).

## 3. Business Value Rubric (source: `docs/business_value.md`)

Embedded verbatim, same sync-together caveat as Health's rubric.

| Dimension | 1 — Minimal | 2 — Marginal | 3 — Moderate | 4 — Strong | 5 — Exceptional |
|---|---|---|---|---|---|
| **Strategic Alignment** | No connection to any stated strategic objective or theme. | Loosely related to strategy; connection is inferred, not documented. | Supports a secondary or lower-priority objective. | Directly supports a stated strategic objective. | Directly and measurably drives a top-priority strategic objective. |
| **Revenue / Cost Impact** | No identifiable financial impact, or net negative with no offsetting benefit. | Financial impact is assumed but unquantified. | Modest, quantified impact on revenue or cost. | Clear, quantified impact with a credible business case. | Material, quantified impact validated against actuals, not just projections. |
| **Customer / Stakeholder Impact** | No identifiable customer or stakeholder benefit. | Benefit is anecdotal or affects a very narrow group. | Improves experience or outcomes for a defined segment. | Measurably improves experience/outcomes for a broad or key segment. | Materially changes a key customer/stakeholder metric (satisfaction, retention, adoption) at scale. |
| **Competitive Differentiation** | Table stakes at best; absence would go unnoticed by the market. | Keeps pace with competitors; no distinct advantage. | Provides a modest edge in specific situations. | Provides a clear, defensible advantage in the market or industry. | Establishes a durable differentiator competitors can't easily replicate. |
| **Risk / Compliance Contribution** | Increases risk exposure or compliance burden with no offsetting value. | Neutral; neither reduces nor materially adds risk. | Modestly reduces a known risk or compliance gap. | Meaningfully reduces risk or closes a compliance gap. | Eliminates a significant risk or is required for regulatory/compliance standing. |
| **Evidence & Measurability** | Value is asserted with no supporting data or metric. | A metric exists but isn't tracked or reported. | Tracked informally; not reviewed on a regular cadence. | Tracked with a defined metric, reviewed on a regular cadence. | Tracked, reviewed, and tied to a target with demonstrated trend evidence. |

Radio buttons occupy every rating cell, same convention as Health.
**Evidence & Measurability does double duty** (per the doc's own mechanics,
§5 below): it's one of the six weighted inputs *and* separately determines
the soft cap.

## 4. Interaction Design

Identical shape to `application-health-assessment-spec.md` §4 — same two
entry points (Edit form + Overview tab), same New-application-mode
disablement, same pre-fill-on-reopen, same "Save is its own independent,
immediately-persisted action" pattern. Differences only in copy and the
number shown:

- Button label: **"Assess Business Value"**.
- Read-only display: e.g. `Business Value: ★★★★☆ (4)` / `— not assessed —`,
  same star convention.
- Popup footer shows the computed result **before** Save, same as Health's
  "Resulting health score: N" line — here: `Resulting business value: N
  (weighted average W, capped by Evidence & Measurability at C)`. **The cap
  math is always shown** (resolved 2026-08-15), even when it isn't
  currently binding (e.g. `weighted average 4.1, no cap applied — Evidence
  & Measurability scored 4+`) — so the mechanism is visible on every
  assessment, not just the ones where it changes the outcome.

## 5. Aggregation Logic — weighted average + Evidence & Measurability soft cap

This is the section with no Health equivalent — the actual point of this
spec per the user's framing ("difference this time is in the math").

### 5.1 Weights (EA-prioritized, proposed here for review)

| Dimension | Weight |
|---|---|
| Strategic Alignment | 25% |
| Revenue / Cost Impact | 25% |
| Customer / Stakeholder Impact | 15% |
| Risk / Compliance Contribution | 15% |
| Competitive Differentiation | 10% |
| Evidence & Measurability | 10% |

Sums to 100%. Strategic Alignment and Revenue/Cost Impact carry the most
weight (matches `business_value.md`'s own stated reasoning — "closer to how
EAs actually reason about value"); Customer Impact and Risk/Compliance are
mid-tier; Competitive Differentiation and Evidence & Measurability are
lowest-weighted *as averaged inputs* (Evidence & Measurability's real
leverage comes from the cap in §5.2, not its 10% weight here). **Confirmed
as proposed** (resolved 2026-08-15). For this build the weights are a
hardcoded constant, same treatment as the cap table — no UI to edit them.
The user flagged wanting an editable-weights UI later, since this is
expected to be the first of a class of tunable scoring-rubric parameters
ADP will accumulate, not a one-off — tracked as a deliberately deferred
follow-on, `ADP-68z`, out of scope for this build.

### 5.2 The cap table (verbatim from `business_value.md`)

| Evidence & Measurability score | Ceiling applied to overall score |
|---|---|
| 1 — Value asserted, no data | Overall capped at 2 (Marginal) |
| 2 — Metric exists, not tracked | Overall capped at 3 (Moderate) |
| 3 — Tracked informally | Overall capped at 4 (Strong) |
| 4 or 5 — Tracked and reviewed on cadence | No cap; raw average stands |

### 5.3 The formula

```
raw_score = Σ(dimension_score[d] × weight[d]) for d in six dimensions   // §5.1 weights
ceiling   = cap_table[evidence_score]                                    // §5.2, None if evidence_score >= 4
capped    = min(raw_score, ceiling) if ceiling is not None else raw_score
business_value = round_half_up(capped)                                   // §5.4 -- always lands back on 1-5
```

**Worked example (from `business_value.md`):** Strategic Alignment 5,
Revenue Impact 5, Customer Impact 4, Differentiation 4, Risk 3, Evidence 1.
`raw_score = 5(.25) + 5(.25) + 4(.15) + 3(.15) + 4(.10) + 1(.10) = 1.25 +
1.25 + 0.60 + 0.45 + 0.40 + 0.10 = 4.05`. Evidence = 1 → ceiling = 2.
`capped = min(4.05, 2) = 2`. Final `business_value = 2`.

### 5.4 Rounding

Standard Python `round()` uses banker's rounding (`round(4.5) == 4`, not
5) — surprising for a UI that visibly shows "the weighted average is 4.5."
**Round-half-up** instead (`4.5 → 5`, `2.5 → 3`), implemented explicitly
(e.g. `math.floor(x + 0.5)` for positive x in this 1–5 range) rather than
relying on the builtin, since the resolved decision was "round to nearest,"
and "nearest" should mean what a reader expects it to mean.

### 5.5 Pure function, store-layer, mirrors `compute_evolution_stage()`

Per `business_value.md`'s own suggestion and this codebase's established
convention (derived/computed values live as pure, no-I/O functions — see
`adp.strategy.store.compute_status()`, ADP-d8u.5): a new
`compute_business_value_score(scores: dict[BusinessValueDimension, int]) ->
int` pure function, unit-testable directly against the weights/cap table
above with no DB involved, called by the store-layer upsert function the
same way Health's `upsert_health_assessment()` calls `min()` today — except
here it calls this new function instead of a builtin.

## 6. Data model

`applications.business_value` needs no schema change (already exists).
New table, exact same shape as Health's `application_health_assessment`:

**`application_business_value_assessment`** (new table)

| Column | Type | Notes |
|---|---|---|
| `application_id` | TEXT FK → applications, `ON DELETE CASCADE` | part of PK |
| `dimension` | TEXT | part of PK; CHECK constraint, one of six keys (`strategic_alignment`, `revenue_cost_impact`, `customer_stakeholder_impact`, `competitive_differentiation`, `risk_compliance_contribution`, `evidence_measurability`) |
| `score` | SmallInteger | CHECK 1–5 |
| `assessed_at` | TIMESTAMPTZ | overwritten on re-assessment |
| `assessed_by` | TEXT | |

PK: `(application_id, dimension)`. `applications.business_value` is written
by the same transaction that upserts these six rows, via
`compute_business_value_score()` (§5.5) instead of `MIN()`.

## 7. API surface

New sub-resource, same shape as Health's:

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/applications/{id}/business-value-assessment` | Returns the six current dimension answers plus the current `business_value`. |
| `PUT` | `/api/v1/applications/{id}/business-value-assessment` | Body: all six dimension scores, all required (400/422 on partial). Upserts the six rows and recomputes `applications.business_value` via `compute_business_value_score()` in one transaction. |

`PATCH /api/v1/applications/{id}` rejects `business_value` in the request
body (422, `extra="forbid"`) — removed from `ApplicationUpdate`/
`ApplicationCreate`, same mechanism as Health's `health_score` removal.

## 8. UI / screen impact

- `ApplicationForm.tsx`: remove the free "Business Value (1–5)" number
  input; add read-only display + "Assess Business Value" button (disabled
  in New-application mode), same placement pattern as Health's block.
- `ApplicationDetail.tsx`: same button added next to the Overview tab's
  business value display (**note:** confirmed there is currently no
  business-value star/read display on the Overview tab the way there is
  for `health_score` — this spec adds one, mirroring Health's stars
  exactly, since there's nowhere to put the new button otherwise).
- **Confirmed (resolved 2026-08-15): build as one shared, generic
  component**, e.g. `AssessmentModal.tsx`, parameterized by rubric content,
  API hooks, and the aggregation/result-copy for the popup footer.
  `HealthAssessmentModal.tsx` (already shipped) gets refactored to become a
  thin wrapper passing Health's rubric/hooks/MIN-based footer copy into the
  shared component; this spec's popup becomes a second thin wrapper passing
  the §3 rubric, the new hooks below, and the §5 weighted-average+cap
  footer copy. Existing `HealthAssessmentModal.test.tsx` coverage must
  still pass unchanged after the refactor (behavior-preserving), plus new
  tests for the generic component and both thin wrappers.
- New hooks in `web/src/api/application.ts`: `useBusinessValueAssessment`/
  `useSaveBusinessValueAssessment`, same shape as Health's pair.

## 9. Decisions (all open questions resolved 2026-08-15)

| # | Question | Decision |
|---|---|---|
| 1 | Are the §5.1 weights confirmed as proposed? | **Yes.** Hardcoded constant for this build; an editable-weights UI is deliberately deferred, `ADP-68z`. |
| 2 | Shared modal component, or two separate near-duplicates? | **Shared.** `HealthAssessmentModal.tsx` gets refactored into a thin wrapper over a new generic component; this spec's popup is a second thin wrapper. |
| 3 | Always show the cap math, or only when it binds? | **Always shown**, on every assessment. |

This spec is ready for implementation. No remaining open questions.
