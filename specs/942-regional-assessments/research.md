# Research: Regional Assessments (942)

`/speckit-clarify` was skipped, so the five judgment calls under the spec's Assumptions stand as written:
- no roll-up or inheritance;
- a note without a score is allowed;
- scope is a flag plus geographies, with containment in both directions;
- the heat map is a second view on the Heat Map tab;
- columns are kept for the session.

No `NEEDS CLARIFICATION` remained. These are the design decisions.

## R1 — Where it lives

- **Decision**: in `adp.organization`, which already owns the geography tree and the narrow `business_capabilities` mirror (941). Logic goes in a new module, `adp.organization.regional` (writes, snapshot, reads), and derivations in a pure module, `adp.organization.regional_analysis`. Tables are defined in `adp.organization.store`, next to `_geographies`, because `delete_geography` must clean them up (941 R3 precedent).
- **The mirror** gains a nullable `maturity_level` (the baseline). It is nullable because astore's own mirror has no such column, as with `position` in 941.
- **Alternatives**: `adp.business`. Its core files are over the size threshold, the business store doesn't know geographies, and it would have to import the organization store, reversing the dependency direction 940 set.

## R2 — Storage: two tables plus a flag table, nothing on `business_capabilities`

- **`capability_regional_assessments`**: `id`, `capability_id` (FK CASCADE), `geography_id` (FK CASCADE), `maturity_level` (SMALLINT NULL, CHECK 1–5), `note` (TEXT NULL), `created_at`, `updated_at`.
  - UNIQUE `(capability_id, geography_id)`.
  - CHECK `maturity_level IS NOT NULL OR note IS NOT NULL`.
- **`region_specific_capabilities`**: `capability_id` PK (FK CASCADE), `created_at`. The flag: a row exists means the capability is region-specific.
- **`region_specific_capability_geographies`**: `(capability_id, geography_id)` PK, both FKs CASCADE. The capability-side FK points at `region_specific_capabilities`, so clearing the flag cascades its geographies.
- **Why the flag is a separate table** rather than a `business_capabilities` column:
  - the epic's edge case (a geography delete leaves a flagged capability with no geographies, shown as "scope needs updating") needs the flag to survive its last geography, so it can't be derived from the scope rows;
  - a column would touch the business store, models, router, export and the capability form, which are CRLF files that 942 otherwise never needs to change.

  The 1:1 side-table follows APM's precedent (038: risk, cost and governance tables per application).
- **Rules in the store** (422, message names the rule):
  - geography level 1 (Global) refused: "Global is the capability's baseline maturity";
  - neither a score nor a note: "Record a maturity score, a note, or both";
  - note over 1,000 characters: refused by Pydantic, with the CHECK as a backstop;
  - a flagged scope with no geographies.

## R3 — Pure derivations over a small snapshot

`regional.build_snapshot(session)` runs 4 queries:
- the capability mirror, including baseline maturity;
- geographies (id, name, code, level, parent);
- assessments;
- region-specific capabilities plus their geographies.

`regional_analysis` derives, with no I/O:
- **Applicability** (FR-007): if the capability isn't region-specific, it applies everywhere. Otherwise it applies in column G when some scope geography S satisfies any of these:
  - S == G;
  - S is an ancestor of G (G inside S);
  - S is a descendant of G (G contains S).

  If no scope geographies are left, `scope_needs_update` is true and the capability is treated as applicable nowhere, with a visible marker.
- **Cell state** (FR-010/012): `not_applicable`, else `assessed` (score and/or note, and `delta = score − baseline` when both exist), else `not_assessed`. Only the exact (capability, geography) assessment is used; there is no roll-up and no inheritance.
- **Rows**: capabilities in tree pre-order (siblings by position, then name), the same order as 941, sharing its `_preorder` helper.
- **Columns**: the requested geography ids, or by default every level-2 geography (the regions) by name. Global and unknown ids give a 422; more than 12 gives a 422.

## R4 — API shape

All routes are served by the organization router under `/api/v1/business/`, so writes ride the existing `WRITE_BUSINESS_ARCH` prefix rule:
- `GET /regional-assessments?capability_id=` lists assessments, optionally for one capability, with each assessment's geography Ref and code.
- `PUT /regional-assessments/{cap_id}/{geo_id}` with `{maturity_level: 1-5 | null, note: str | null}` records or changes the assessment (upsert, FR-002).
- `DELETE /regional-assessments/{cap_id}/{geo_id}` removes it.
- `GET /regional-heatmap?geography_ids=a,b,c` returns the matrix.
- `GET /capability-region-scope/{cap_id}` and `PUT /capability-region-scope/{cap_id}` with `{region_specific: bool, geography_ids: [...]}`. The PUT replaces the scope; `false` clears the flag and its geographies.

The scope and heat map live under distinct prefixes, so they can't collide with `/regional-assessments/{cap_id}/{geo_id}`.

## R5 — UI

- **Heat Map tab**: a "Capabilities | Regional" view switch at the top. The regional view is a new `RegionalHeatMap.tsx` with a `<table>` matrix in an `overflow-x: auto` container (the `StrategyHeatMap` / `CrossTabGrid` precedent).
  - **Cells** use the same 5-step maturity scale as the existing heat map. The swatches move to a small shared module (`web/src/business/maturityScale.ts`) so both views use one definition.
  - **Indicators**: "▲" / "▼" with the delta show above or below the baseline. "Not assessed" is a muted dashed cell; "Not applicable" is a hatched grey cell.
  - **Notes** show as the cell's `title`, and inside a focus-visible popover.
- **Column picker**: regions are always offered; countries come from a filterable list, up to 12. The choice is held in `BusinessPage` state, so it survives tab switches for the session (no storage).
- **Editing**: clicking a cell, for writers, opens a small inline editor (score select, note textarea, Save / Remove). The same editor appears in a new "Regions" expander on each Capabilities row (`RegionalAssessmentEditor.tsx`), which also edits the region-specific scope.

## R6 — Audit, export, seed

- **Audit**: `_log` events:
  - `regional_assessment.set` (capability, geography, score, note_chars, created);
  - `regional_assessment.remove`;
  - `region_scope.set` (capability, region_specific, geographies).
- **Export**: the capability file gains `regional: {region_specific, scope: [{id, name}], scope_needs_update, assessments: [{geography: {id, name, code}, maturity_level, note}]}`, built by the pure `regional_analysis.export_block` from one snapshot in `business_arch._fetch_all`, and best effort like 941's block.
- **Seed**: phase C5 records assessments for 3–4 capabilities across Europe, the Americas and two countries, with differing scores and one note. It adds one region-specific capability: a new L3, "Statutory eSocial Reporting", under Human Capital Management, scoped to Brazil. The new tables go in `WIPE_TABLES`, before the geography-free tables.
