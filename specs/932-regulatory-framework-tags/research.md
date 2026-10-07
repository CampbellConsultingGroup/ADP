# Research: Regulatory Framework Tags for Application Risk & Compliance

All items below were resolved by direct code inspection against this codebase's own established
precedents, not invented — each decision names the precedent it mirrors.

## D1 — Which domain owns the link table

**Decision**: The new `application_framework_tags` link table lives in `adp.application` (not
`adp.compliance`), with a narrow read-only mirror of `regulatory_frameworks` (id, name, status)
inside `adp.application.store` for existence/status validation — zero import of `adp.compliance`
from `adp.application`.

**Rationale**: This is a bare, unassessed "applies here" tag — structurally identical to
`theme_framework_links` (927-theme-framework-mapping, COMPLY-05 link #3), which lives in
`adp.strategy` (the *other* domain, not Compliance) for the exact same reason: it carries no
`compliance_status` of its own, unlike the five `control_*_mapping` tables which Compliance does
own because Compliance is what assesses them. `adp.application.store` already has this identical
cross-domain mirror idiom for a different foreign key (`_applications`/`_designs` style mirrors
used throughout `adp.strategy.store` and `adp.compliance.store`); this feature is the first time
`adp.application` itself needs one, but the pattern transplants directly.

**Alternatives considered**: Owning the link in `adp.compliance` (rejected — breaks the
established "the assessed-status owner owns the mapping table" rule; this tag has no assessed
status) and a genuinely new shared package (rejected — no second domain-pair needs this yet, and
every sibling COMPLY-05 link lives inside one of the two existing domains it connects).

## D2 — API shape: batched full-set replace vs. per-item link/unlink

**Decision**: No new endpoints. The existing `PUT /api/v1/applications/{app_id}/risk` continues
to accept the full `ApplicationRiskUpdate` body, with `regulatory_tags: list[str]` now meaning "the
complete desired set of framework ids" rather than free text. The store reconciles the submitted
set against `application_framework_tags` (delete rows no longer present, insert rows newly
present) inside the same transaction as the rest of the risk record's upsert.

**Rationale**: `RiskPanel.tsx` is already a single batched form with one Save button submitting
every risk field (`security_posture`, `vulnerability_status`, `regulatory_tags`, dates, …) in one
`PUT`. That UX is unchanged by this feature (FR-001..009 describe no new save/cancel flow), so the
API contract that already serves it should stay unchanged in shape. This is deliberately *not*
`927`'s own link/unlink-per-call shape (`POST/DELETE .../frameworks/{id}`) — that shape exists
because `ObjectiveControlLinkEditor.tsx`-style editors save each link immediately on click; this
feature's editor does not.

**Alternatives considered**: Per-item link/unlink endpoints mirroring 927 (rejected — would force
an unrelated UX change to a form that already works; no requirement asks for immediate-save
semantics here).

## D3 — Wire shape of `regulatory_tags` (bare ids vs. resolved objects)

**Decision**: `regulatory_tags` stays `list[str]` (framework ids) on the wire, in both
`ApplicationRiskUpdate` and the `ApplicationRisk` read model — no breaking schema change to the
field's type. Display (FR-003) is resolved client-side by cross-referencing the already-fetched
`useFrameworks()` list (`GET /api/v1/compliance/frameworks`, already open/ungated), the same way
`StrategicTheme.framework_ids: list[str]` (927) is resolved against the same hook on
`CompliancePage.tsx`'s own sibling screens.

**Rationale**: Avoids duplicating framework name/jurisdiction/version into every application's risk
payload; keeps `ApplicationRisk` from needing to join against Compliance data on every read when
the frontend already holds the full framework list in cache for the picker itself. Matches the
"ids forward, resolve client-side" shape used everywhere else in this codebase
(`StrategicObjective.control_ids`, `StrategicTheme.framework_ids`).

**Alternatives considered**: Returning resolved `{id, name, jurisdiction, version}` objects
(rejected — needless duplication and a join the frontend doesn't need, since it always has the
full framework list in cache already via `useFrameworks()`).

## D4 — Enforcing the `in_force`/`amended` status filter (FR-001) server-side

**Decision**: The mirror table in `adp.application.store` carries `status` alongside `id`/`name`.
`upsert_application_risk` validates every **newly added** framework id (present in the submitted
set but not already linked) against both existence and `status IN ('in_force', 'amended')`,
rejecting the whole write (422) if any newly-added id fails either check. A framework id that was
**already** linked is never re-validated against its current status on an unrelated save — this is
what lets an already-tagged, later-`repealed` framework's tag survive untouched (the Edge Case the
spec records), while still blocking a new attempt to tag a repealed one.

**Rationale**: FR-001 describes picker-level (client) filtering, but a client-side-only filter is
not a security/integrity boundary — the server is the one place this can be guaranteed. Diffing
"newly added" vs. "already present" (rather than validating the whole submitted set every time) is
what makes the status-filter rule and the "historical tags survive a status change" edge case both
true simultaneously without contradiction.

**Alternatives considered**: Re-validating the entire set's status on every save (rejected —
would silently un-tag an application the moment a previously-valid framework transitions to
`repealed`, contradicting the recorded Edge Case); trusting the client filter alone (rejected —
not a real boundary, and FR-002 already establishes that invalid ids are rejected server-side).

## D5 — Enforcing uniqueness (FR-009)

**Decision**: Composite primary key `(application_id, framework_id)` on `application_framework_tags`
database-enforces at-most-once. The store's reconciliation diffs the submitted list against the
existing linked set *by id* before issuing inserts, so a caller submitting the same id twice in one
request simply inserts it once (de-duplicated in Python before the query), rather than relying on
the database to reject a duplicate within the same statement.

**Rationale**: Matches every sibling COMPLY link table's composite-PK precedent
(`theme_framework_links`, `objective_control_links`, all five `control_*_mapping` tables).

## D6 — Migration shape and satisfying FR-006 (discard existing free text)

**Decision**: New migration `041` (`down_revision="040"`): creates `application_framework_tags`
(composite PK, both legs `ON DELETE CASCADE` — `application_id → applications.id`,
`framework_id → regulatory_frameworks.id`; index on `framework_id` for any future reverse lookup,
mirroring `ix_tfl_framework_id`), and **drops** the now-superseded `application_risk.regulatory_tags`
JSON column.

**Rationale**: Dropping the column is what makes FR-006 ("discard outright... every application
starts with zero regulatory framework tags") true by construction, atomically, at migration time —
every application's new tag set is the new table, which starts empty for every row, for every
application, with no custom data-migration/backfill logic needed at all. Keeping the old column
around unused (rather than dropping it) was considered and rejected: it would leave a dead,
confusing column that no code reads, and ART-II ("hand-edited/duplicated records MUST NOT exist as
primary records alongside the real one") argues against letting two representations of "an
application's regulatory tags" coexist in the schema even briefly.

**Alternatives considered**: Best-effort string→id matching at migration time (rejected by the
user directly during `/speckit.clarify`, Option B chosen over Option A); keeping the old column as
inert legacy storage (rejected, see above).

## D7 — Scope boundary: no framework→application reverse lookup in this pass

**Decision**: No `GET /compliance/frameworks/{id}/applications`-style reverse endpoint is built in
this feature, at the API layer or the UI layer.

**Rationale**: The spec's own Assumptions section explicitly defers this as a named follow-on
("valuable but out of scope for this pass... filed as a follow-on if wanted"), unlike 927 (which
built the reverse-lookup *endpoint* in-pass but deferred only its UI). Building it anyway here
would be scope creep beyond the nine approved FRs, none of which describe a framework-centric view.

**Alternatives considered**: Building the read endpoint eagerly, matching 927's own precedent of
"always ship both directions at the API level even if UI lags" (rejected — the spec's Assumptions
already settled this question explicitly for this feature; a later follow-on bead is the right
place to revisit it, not a silent scope addition during planning).

## D8 — Existing consumers requiring an update

Confirmed by direct `grep` — the full footprint of `regulatory_tags` outside tests is:

- `src/adp/application/store.py` — `_application_risk` table definition, `_row_to_risk`,
  `upsert_application_risk` (all rewritten per D1-D6 above).
- `src/adp/application/models.py` — `ApplicationRiskUpdate.regulatory_tags`,
  `ApplicationRisk.regulatory_tags` (type unchanged per D3; validation semantics change).
- `src/adp/export/application_arch.py` — **Ground-Truth Correction, found during implementation,
  not anticipated here**: `_serialize_risk` itself (line ~66, `list(risk.regulatory_tags)`) needed
  no change, as originally assessed. But `_fetch_all`'s bulk-fetch path (the reconciliation cycle's
  own no-N+1 query set) calls `astore._row_to_risk(row)` directly against a raw
  `_application_risk` row, bypassing `get_application_risk`'s per-application join entirely — this
  broke the moment `_row_to_risk`'s signature gained a required `regulatory_tags` parameter
  (research.md D3/D6). Fixed with one additional bulk query (grouping every
  `_application_framework_tags` row by `app_id`, mirroring every other `*_by_app` dict already
  built in this same function), preserving the function's own stated "small, fixed number of
  queries" invariant rather than reverting to N+1. Existing fixture/test data using values like
  `["PCI"]` was updated to use plausible framework-id-shaped strings in this feature's test
  changes (these are pure serialization tests with no I/O, so any string round-trips regardless —
  the change is for fixture honesty, not because anything would otherwise fail).
- `web/src/application/RiskPanel.tsx` — replaces the free-text `<input>` with a framework
  checkbox/multi-select list sourced from `useFrameworks()`, filtered to `status` ∈
  {`in_force`, `amended`}.
- `web/src/api/application.ts` — type is unchanged (`regulatory_tags: string[]`); no edit needed
  there beyond what `RiskPanel.tsx` itself does locally.
- `web/src/api/compliance.ts` — `RegulatoryFramework` interface is missing `status` (and the other
  five 926-era optional fields) entirely — a pre-existing gap, confirmed by direct read, since 926
  was explicitly backend/API-only. This feature must add at least `status` to the frontend
  interface to implement the FR-001 picker filter; the other still-missing 926 fields are not
  needed here and are left for a future pass (not this feature's concern).

## D9 — A pre-existing multi-domain fixture collision, surfaced (not caused) by D1

**Discovery (during implementation, not anticipated by D1-D8)**: `tests/contract/
test_compliance_mappings_api.py`'s `full_client` fixture creates `bstore`, `astore`, and `cstore`'s
table metadata against one shared SQLite connection, in that order, relying on
`create_all()`'s default `checkfirst=True` to let each domain's own real table "win" over any
other domain's same-named mirror of it (`cstore` mirrors `bstore`'s `business_capabilities` and
`ADP-SPEC-002`'s `designs`; `cstore` also mirrors `astore`'s real `applications`). Adding `astore`'s
own narrow mirror of `regulatory_frameworks` (D1) introduced the first case where the relationship
runs the *other* way for one table: `cstore` is the real owner, `astore` is the mirror, but `astore`
still runs before `cstore` in this fixture's existing order — so `astore`'s narrower 3-column mirror
silently "won" instead, leaving every other real column (`jurisdiction`, `authority`, ...) missing
and breaking two previously-passing reverse-lookup tests.

**Fix**: `astore`'s call in that one fixture now explicitly excludes the `regulatory_frameworks`
table (`tables=[t for t in astore._metadata.tables.values() if t.name != "regulatory_frameworks"]`),
letting `cstore`'s later call create the genuine table for the first time instead of finding it
already present. The original `bstore → astore → cstore` ordering is otherwise untouched —
reversing the whole order was tried first and rejected, since it broke the pre-existing, correct
resolution for `business_capabilities`/`designs`/`applications` the other direction.

**Why this matters beyond this one fixture**: this confirms the collision pattern is structural,
not hypothetical — `adp.strategy.store` has carried an identical narrow `regulatory_frameworks`
mirror since 927 with no test ever exercising this exact dual-`create_all` scenario for it. This
feature's own fix is scoped to the one fixture it broke; no attempt is made here to pre-emptively
audit every other possible mirror/mirror-of-mirror combination across the suite, which is out of
scope for this feature.
