# Research: Capability Model Analysis (938)

The spec has no open NEEDS CLARIFICATION items. These are the design decisions, checked against main at 64d6a52 (migration head `046`).

## R1 — One pure engine over a per-request snapshot

**Decision**:
- `adp.application.cap_analysis` (new) holds pure functions with no I/O: risk band, effective lifecycle band, roll-up, impact, exposure, gaps/overlaps/shared.
- They take a frozen `CapabilitySnapshot` dataclass and an `as_of: date`.
- `adp.application.cap_analysis_store` (new) builds the snapshot from a fixed number of queries.

**Rationale**:
- This is the same split as 936 (`adp.patterns.engine` over `adp.patterns.snapshot`) and as `compute_compliance_status()`.
- The engine can be tested exhaustively against hand-built snapshots without a database.
- `as_of` makes the date rules (end of support passed, end of life within 12 months, "today counts as past") deterministic in tests.

**Alternatives considered**:
- SQL aggregation (recursive CTEs over three trees). Rejected: the worst case, the spread over leaves, the distinct-application union and the exclusion of Retired applications are awkward in SQL and would need the SQLite test tier to match Postgres.

## R2 — Snapshot queries (fixed count, no N+1)

**Decision**: one snapshot per request:

| # | Query | Always |
|---|---|---|
| 1 | `business_capabilities` (id, name, level, parent_id) via the existing `_biz_caps` mirror | yes |
| 2 | `application_capabilities` (id, name, level, parent_id) | yes |
| 3 | `business_capability_app_capability_links` | yes |
| 4 | `app_capability_tech_cap_links` | yes |
| 5 | `app_capability_realizations` joined to `applications` (id, name, lifecycle_status, health_score) | yes |
| 6 | `technical_capabilities` (id, name, level, parent_id, lifecycle_status, end_of_life_date) | yes |
| 7 | `application_risk` (app_id, security_posture, vulnerability_status, end_of_support_date) | only when the caller holds `READ_APPLICATION_RISK` |
| 8 | `list_all_costs()` (existing helper; TCO is computed in Python) | only when the caller holds `READ_APPLICATION_COST` |

Reads inner-join the far ends, as 937 does, so dangling rows on SQLite never appear.

**Rationale**:
- At the SC-005 scale (500 + 500 capabilities, 2,000 links) this is a few thousand small rows, well inside 2 seconds.
- Skipping queries 7 and 8 for callers without the permission means the gated data is never loaded at all, which is stronger than redacting it afterwards.

**Alternatives considered**: per-capability endpoints. Rejected: the heat map needs every capability at once (FR-019).

## R3 — Gated metrics: never loaded, explicitly marked

**Decision**:
- The router checks `is_permitted(user.role, READ_APPLICATION_RISK | READ_APPLICATION_COST)` inline. This mirrors `adp.api.routers.portfolio` (heat map cost) and `adp.patterns.adoptions_router`.
- It passes `risk_visible` and `cost_visible` flags to the snapshot builder.
- Responses carry `risk_available: bool` and `cost_available: bool` at the top level. When either is false, the matching per-capability fields are `null`.
- "No data" is a separate state with real counts: `worst: null` with `no_data` counted in the spread.

**Rationale**: FR-008 needs "unavailable" to be distinguishable from "no data". A route-level 403 would also hide health and exposure from those callers.

**Alternatives considered**: separate endpoints per metric with route-level gates. Rejected: it breaks FR-019's single fetch and repeats the snapshot work.

## R4 — Risk band (FR-006), fixed mapping

**Decision**: `risk_band(risk, as_of) -> "high" | "medium" | "low" | "unknown"`. Rules are checked in order:
1. **High**: `vulnerability_status ∈ {open_high, critical}`, or `security_posture == weak`, or `end_of_support_date <= as_of`.
2. **Medium**: `vulnerability_status == open_low`, or `security_posture == adequate`, or `end_of_support_date <= as_of + 365 days`.
3. **Low**: `security_posture == strong` and `vulnerability_status == none_known`.
4. **Unknown**: anything else, including no risk record.

Order for "worst": high > medium > low. Unknown never sets the worst value; it is counted in the spread only.

## R5 — Effective lifecycle band (FR-012)

**Decision**: `effective_band(tc, as_of)`. Rules are checked in order:
1. `past_end_of_life`: status `retired`, or `end_of_life_date <= as_of`.
2. `retiring`: status `retiring`, or `end_of_life_date <= as_of + 365 days`.
3. Otherwise the status itself: `contained`, `current` or `emerging`.

Severity order: past_end_of_life > retiring > contained > current > emerging.

## R6 — Roll-up shape (FR-005..FR-010)

**Decision**: for each business L3, compute its contributing applications. These are the distinct realizing applications of its linked application capabilities, excluding `lifecycle_status == "retired"`. Excluded retired applications are kept in a separate list for the detail view.

Each L3 gets:
- **Health**: `worst` = min score (lower is worse), plus a spread `{1..5, unassessed}` over its applications. `no_data` when there are no contributing applications.
- **Risk**: as health, with bands.
- **Cost**: the sum of TCO over contributing applications, plus a count of `apps_without_cost`.
- **Exposure**: the worst effective band over technical capabilities reached through its application capabilities. A linked technical L2 expands to itself and its children.

Parents (L2, L1):
- `worst` = worst over leaf L3 values;
- spread = count of **leaves** per value (FR-007), including `no_data` leaves;
- cost = the sum over the **distinct union** of contributing applications across descendants, so each application is counted once per capability.

Health "lower is worse" follows `health_score` 1–5, where 5 is healthy, as in the existing heat map swatches.

## R7 — Where the routes live

**Decision**: new routes go on the existing 937 router under a literal `/analysis/` segment, registered before `/{ac_id}`:
- `GET /api/v1/application-capabilities/analysis/business-rollup`
- `GET /api/v1/application-capabilities/analysis/technical-capabilities/{tc_id}/impact`
- `GET /api/v1/application-capabilities/analysis/business-capabilities/{cap_id}/technology`
- `GET /api/v1/application-capabilities/analysis/findings`

**Rationale**:
- They are all GETs, which authz treats as open (`SAFE_METHODS`), so no new rule is needed.
- They sit with the data they analyse, and no new router module is needed. Analysis adds about 150 lines to the router.

**Alternatives considered**: `adp.portfolio` (cross-domain aggregator). Rejected: everything here is in the `adp.application` tables already.

## R8 — Technical capability lifecycle storage (D1)

**Decision**: migration `047` (`down_revision="046"`) adds two columns to `technical_capabilities`:
- `lifecycle_status TEXT NOT NULL DEFAULT 'current'`, with `CHECK (lifecycle_status IN ('emerging','current','contained','retiring','retired'))`;
- `end_of_life_date DATE NULL`.

The store's `_tech_caps` table also gets a Python-side `default="current"`. This is the 926 lesson: some fixtures insert raw rows.

The fields are written through the existing `PATCH /technical-capabilities/{id}`. `TechnicalCapabilityUpdate` gains both fields, with `model_fields_set` semantics so an explicit null clears the date. They are also accepted on create.

Logging: `technical_capability.lifecycle id=… actor=… from=… to=… eol_from=… eol_to=…`, emitted only when either field changes (FR-003).

The fields are exported in `_serialize_technical_capability` (FR-004).

**Alternatives considered**: a separate lifecycle table with history. Rejected: no requirement for history, and conformance history (ADP-5mc) is a follow-on.

## R9 — Guard test (FR-022)

**Decision**: `tests/unit/application/test_cap_analysis_not_stored.py` mirrors `tests/unit/patterns/test_no_status_column.py`. It asserts that no column on any `adp.application.store` table, and none in migration `047`'s DDL, matches `/rollup|worst|spread|band|exposure|impact|overlap|gap|finding/i`. The two allowed new columns are `lifecycle_status` and `end_of_life_date`.

## R10 — Frontend

**Decision**:
- **Business heat map**: `CapabilityHeatMap.tsx` gains metrics `health | risk | cost | exposure`. They come from one `useCapabilityRollup()` query, fetched only when one of these metrics is first chosen and cached afterwards, so switching between them needs no fetch. Unavailable metrics render a disabled option with "not available to you". A cell's tooltip and focus detail lists the contributing applications, the application capabilities they act through, and any excluded retired applications.
- **Business L3 rows** (`CapabilityNode.tsx`): a "Technology dependencies" expander beside 937's "Application capabilities" one, using the same lazy `Expander` pattern.
- **Technical capabilities**: `TechCapForm.tsx` gains a lifecycle select and an end-of-life date. Tree rows show a lifecycle chip and a "past end of life" flag. `TechCapImpactPanel.tsx` (new) is a lazy expander on each row, like 937's `TechCapUsedBy`.
- **Applications → Capabilities**: `AppCapabilitiesView.tsx`'s tab group gains Overlaps, Gaps and Shared, all from one `useCapabilityFindings()` query.

Navigation reuses 937's `AppCapNavContext` for application capabilities. It adds analogous callbacks for business capabilities (scroll and highlight, the 043 precedent), technical capabilities and applications, only where an opener already exists.

## R11 — Seed (FR-023)

**Decision**: `scripts/seed_retail.py` changes:
- Store POS is already seeded at health 2. Confirm the health assessment produces 2.
- Set "Local Data Store with Offline Sync" to `retiring` with an end-of-life date of `2027-06-30`.
- Add an application capability "Online Promotion Evaluation" (under Pricing), realized by Salesforce Commerce Cloud and linked to "Apply Promotions". This creates the overlap.
- Business L3s with no application capability already exist (every non-POS L3).
- Give Store POS a risk record with `security_posture=weak`, so the risk metric has something to show.
