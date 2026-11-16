# Research: Mapping Rationale (943)

`/speckit-clarify` confirmed four defaults on 2026-11-16:
- one rationale and one optional geography per realization;
- "no target" is judged across the whole overlap;
- TIME and 7R give context plus a non-blocking hint;
- the Redundant list is a fourth findings tab.

No `NEEDS CLARIFICATION` remains. These are the design decisions.

## R1 — Storage: two nullable columns on the existing link

- **Decision**: migration `051` adds two columns to `app_capability_realizations`:
  - `rationale` (`TEXT NULL`, CHECK `IN ('target','tactical','transitional','redundant')`);
  - `geography_id` (`String(36) NULL`, FK → `geographies.id` `ON DELETE SET NULL`).

  Plus a plain index on `geography_id`. The composite primary key `(app_capability_id, app_id)` is unchanged: one rationale per realization, as clarified. Existing rows get NULL in both columns ("unclassified, everywhere"), with no back-fill (FR-003).
- **In the SQLAlchemy metadata**, `geography_id` is a plain column with **no** `ForeignKey`, because `geographies` lives on the organization metadata. The real FK exists only in the migration. This is the precedent `applications.owning_org_unit_id` set in 940, which avoids a cross-metadata FK that every fixture would have to resolve.
- **Alternatives**:
  - a separate 1:1 `realization_rationales` table: an extra join everywhere for two scalar attributes of a link row, with no gain;
  - a geography in the primary key (several rows per pair): rejected by clarification Q1.

## R2 — Validating the geography

- **Decision**: on write, the application-capability store validates `geography_id` through a new `adp.organization.store.geography_level(geo_id, session) -> int | None` (lazy import, as the application router already does for `org_unit_exists`):
  - an unknown id gives a 422 "Geography … not found";
  - level 1 (Global) gives a 422 "No geography already means everywhere".
- The dependency direction stays application → organization, as set by 940.

## R3 — A deleted geography

- **Decision**:
  - **On Postgres**, the FK's `SET NULL` clears the column.
  - **On SQLite**, which doesn't enforce FKs, reads treat a `geography_id` that isn't in the geography index as "everywhere" (the read-side orphan-tolerance precedent from 937/941).
- This gives the spec's edge case ("falls back to everywhere") on both engines, without a new mirror table on the organization metadata or an explicit cleanup step in `delete_geography`.

## R4 — Snapshot additions (938 engine stays pure)

`cap_analysis_store.build_snapshot` gains:
- **realization attributes**: the existing realization query also selects `rationale` and `geography_id`. This becomes a new `realizations: Mapping[(ac_id, app_id), Realization(rationale, geography_id)]`, next to the existing `ac_to_apps`.
- **application context**: `AppInfo` gains `time_classification` and `r_strategy`. They are read by the same applications query, with no extra round trip.
- **a geography index**: `geo_parent: Mapping[str, str | None]` plus names and codes. It is queried **only if at least one realization names a geography**:
  - the query count stays the same for everyone without regional realizations;
  - existing 938 fixtures, which create only the application metadata, keep working unchanged.

  The query reads the organization store's `_geographies` through a small public function, `adp.organization.store.geography_index(session)`.

## R5 — The overlap classification (pure, derived on read)

In `cap_analysis.findings()`, an overlap (unchanged: a business L3 with two or more non-retired applications) gets its **mappings**: one entry per (application, application capability) pair reaching it, with rationale and geography.

The reasons are computed over those mappings:

| Code | Rule |
|---|---|
| `unclassified` | Any mapping has no rationale. Lists the applications |
| `redundant` | Any mapping is redundant. Lists the applications |
| `no_target` | Every mapping is classified, none is redundant, and none is target |
| `competing_targets` | Two target mappings **of different applications** share a scope: both have no geography, or one's geography equals or contains the other's |

- `no_target` is reported only when `unclassified` doesn't apply, so a fully unclassified overlap reads as one clear message rather than two. This narrows FR-007(c) as worded ("no mapping is target"). It's recorded here and in FR-008's "every reason that applies": an unclassified mapping might yet become the target, so "no target" isn't yet known.
- `status` is `needs_attention` if there's any reason, else `explained`.
- **Containment** uses the snapshot's `geo_parent`: walk up from each geography, as 942's applicability check does in both directions. A dangling id counts as "everywhere" (R3).
- **Ordering**: needs attention first, then explained; by business name within each.
- **Compatibility**: existing fields stay as they are (`business`, `applications[].via`). New fields are added: `status`, `reasons`, and `applications[].mappings`.

## R6 — The consistency hint (FR-013)

A pure helper, `consistency_hint(rationale, time_classification) -> str | None`:
- target with `Eliminate` or `Migrate` gives "TIME says Eliminate/Migrate";
- redundant with `Invest` gives "TIME says Invest";
- anything else gives None.

Where it's used: **server side** only. It fills `hint` on each realization in `realized_by`, on each overlap mapping and on each Redundant entry.

*Implementation note:* the client-side copy of the rule was dropped. The realization editor saves on choose and refetches, so the server's hint shows straight away, and the rule lives in one place.

## R7 — Redundant list (FR-012)

`findings()` also returns `redundant: list[RedundantGroup]`:
- one group per business L3 reached by a redundant mapping of a non-retired application, ordered by business name;
- then a group with `business: null` for redundant mappings that reach no business L3.

Each entry carries the application with its TIME and 7R, the application capability, the geography and the hint. The data comes from the same snapshot and endpoint as the other findings (`GET /api/v1/application-capabilities/analysis/findings`), so the four tabs and the Governance tile always agree (SC-004).

## R8 — API shape

- `POST /application-capabilities/{ac_id}/applications` (existing): `RealizationCreate` gains optional `rationale` and `geography_id`.
- `PATCH /application-capabilities/{ac_id}/applications/{app_id}` (new): `{rationale?, geography_id?}`.
  - An explicitly sent `null` clears the field; an omitted field is left as it is (Pydantic `model_fields_set`, the 929 precedent).
  - Returns the application capability detail.
  - An unknown link gives 404.
- Reads: `realized_by` entries (`AppRef` in the detail and summaries) gain `rationale`, `geography` (`{id, name, code}` or null) and `hint`.
  - Every place that lists realizations shows them with no extra calls (FR-014).
  - The application's own capability list reads its own entry out of `realized_by`.

## R9 — UI

- **Realizations editor**: the "Realized by applications" section of `AppCapDetail.tsx` stops using the generic link list. A dedicated `RealizationList` shows each application row with:
  - a **rationale select**: Unclassified / Target / Tactical / Transitional / Redundant;
  - a **geography select**: Everywhere / regions / countries;
  - the hint;
  - Remove.

  Both selects **save on choose**, the convention ADP-w7z just set for this app. The add row keeps its application picker and adds optional rationale and geography selects that are sent with the add.
- **Findings**: `CapFindingsViews` overlaps mode splits into "Needs attention (n)" and "Explained (n)" sections. Each entry shows its reason chips, and each application shows its rationale chip and geography. A new `redundant` mode backs a fourth tab, Redundant, in `AppCapabilitiesView.tsx`.
- **Governance**: the Architecture Health overlaps tile counts `status === "needs_attention"`, with "n explained" as its subtext. The section beneath reuses `CapFindingsViews mode="overlaps"`.

## R10 — Audit, export, seed

- **Audit**: one `_log` line per add (now with rationale and geography) and per PATCH, carrying the old and new rationale and geography (FR-006):
  `application_capability.realization.update ac=<id> app=<id> rationale=<old>-><new> geography=<old>-><new> actor=<sub>`.
- **Export**: the application capability file gains `realizations: [{application_id, rationale, geography: {id, name, code} | null}]`, sorted by application id, built from the export's existing bulk realization query (no N+1). `realized_by_application_ids` is kept.
- **Seed**: phase G in `seed_retail.py` classifies realizations so that:
  - the existing Apply Promotions overlap is **explained** (Store POS target, Commerce Cloud tactical in the Americas);
  - one overlap is left **needing attention** (one mapping unclassified);
  - one mapping is **redundant**.

  The seed is not run against the shared local database (it hard-wipes). It's verified with the same writes made through the API.
