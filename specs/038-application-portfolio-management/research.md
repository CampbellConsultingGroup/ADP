# Research & Decisions: Application Portfolio Management (ADP-SPEC-038)

Phase 0 output. Each decision records the choice, rationale, and rejected alternatives.

## D1 — Migration numbering (resolves FR-015 coordination)

**Decision**: Assign a contiguous block `012`–`021` chaining from head `011_searchable_items`, one migration per slice, with the three feeder beads mapped to specific numbers (015 = ADP-9x6 TCO, 020 = ADP-33v strategic relevance, 021 = ADP-4ga maturity).

**Rationale**: Three open beads each independently reserved "the next migration after 011"; without coordination they would all claim `012` and collide. A single owning epic assigns the block. Per-slice migrations keep each user story independently shippable and reversible.

**Rejected**: One mega-migration for all APM tables — breaks per-story shippability and makes down-revisions coarse. Letting each feeder bead pick its own number ad hoc — the collision we are preventing.

## D2 — Money representation

**Decision**: `NUMERIC(14,2)` at rest, `Decimal` in Pydantic, ISO-4217 `CHAR(3)` currency, `horizon_years SMALLINT`. No float anywhere in cost paths.

**Rationale**: First monetary data in the codebase — sets the convention. Binary floating point cannot represent decimal currency exactly; NUMERIC/Decimal is the only correct choice for money that is summed and rolled up. `14,2` accommodates estate-scale figures.

**Rejected**: Integer cents — workable but less readable and still needs Decimal at the boundary; float — incorrect for money (SC-007 would fail).

## D3 — TCO bucket shape (clarification 2026-07-16)

**Decision**: Each of the eight buckets stores a `one_time` and an `annual` amount; `TCO = Σ(one_time) + Σ(annual) × horizon_years`, computed on read.

**Rationale**: Matches the spec's worked example ($5k/yr × 5 + setup) and lets a horizon change re-derive TCO with no re-entry (SC-006). Computing on read avoids a stored-total drift.

**Rejected**: One lump per bucket — cannot re-derive across horizons and buries the run-vs-change split. Storing a precomputed TCO — drift risk.

## D4 — Business-value scales (clarification 2026-07-16)

**Decision**: Two separate `SMALLINT NULL CHECK 1..5` scores — `business_value` and `business_criticality`; `NULL` = not assessed. The TIME quadrant's value axis uses `business_value`.

**Rationale**: The APM taxonomy lists business value and criticality as distinct concepts; 1–5 aligns with existing `health_score`/`fit_score`/`maturity`. `NULL` (not 1) prevents unassessed apps from silently landing in a quadrant (FR-002, SC-001).

**Rejected**: Single composite score — loses the value/criticality distinction the taxonomy calls for. High/Med/Low — inconsistent with the estate's 1–5 scores and coarser for placement.

## D5 — Rationalization projection is derived, not stored

**Decision**: The TIME quadrant is a read-only projection computed from `business_value × health_score` in a single query pass; unassessed applications are returned in a separate list, never placed.

**Rationale**: Quadrant placement is a pure function of two stored scores — persisting it would duplicate state and drift. A single-pass query avoids N+1 over the estate.

**Quadrant mapping** (thresholds at the 1–5 midpoint, ≥3 = high): high value + high health → **Invest**; high value + low health → **Migrate**; low value + high health → **Tolerate**; low value + low health → **Eliminate**. (Exact threshold is a UI/reporting concern; the projection exposes both raw scores so the boundary can be tuned without a migration.)

## D6 — Sensitive-category authorization

**Decision**: Dedicated read + write permission actions for cost, risk & compliance, and governance; general application read does not grant them. Aggregate/rollup endpoints re-check the relevant read action before returning per-application sensitive values.

**Rationale**: APM's sensitive fields (costs, contracts, security posture, data classification) are the highest-value assets in the threat model. Field-category gating on both direct reads and aggregates closes the leak-via-rollup abuse case (SC-004). Reuses the existing action-based mechanism (ADP-SPEC-004) — no new authz machinery.

**Rejected**: Single blanket application-read permission — would expose cost/risk/contract data to anyone who can view an application. Row-level security in the DB — heavier and redundant with the app-level permission table.

## D7 — Reconcile with existing data, do not duplicate (ART-II)

**Decision**: Technology stack/version stays in `element_technology_tags`; app-to-app dependencies stay in `application_integrations`; strategic relevance (ADP-33v) and maturity (ADP-4ga) attach to capabilities and feed Business fit. APM references these rather than re-modeling them.

**Rationale**: ART-II — one source of truth. Re-capturing stack/dependencies on the application would create divergent copies.

## D8 — Quality metrics manual in v1 (clarification 2026-07-16)

**Decision**: Quality & performance metrics are manually entered advisory values in v1; no external ingestion. They surface alongside `health_score` but do not override it.

**Rationale**: Automated ingestion adds an external integration boundary with its own threat model and connector work — out of proportion to v1. Manual capture still delivers the panel and the advisory signal.

**Rejected (deferred)**: Monitoring/ITSM ingestion — a worthwhile future feature; filed separately when prioritized.

## Open items for `/speckit.tasks`

- Reparent feeder beads (ADP-9x6, ADP-33v, ADP-4ga, ADP-zg3.4) under the APM epic.
- Confirm the exact enum vocabularies (security_posture, vulnerability_status, dr_bc_status) with the risk owner during US3 task breakdown — modeled as boundary Literals so changes are code-only, no migration.
