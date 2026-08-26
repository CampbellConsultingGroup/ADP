# Data Model: Application Type Grouping Dimension

## `Application` (extended, `adp.application.models`)

One new field, added identically to `Application`, `ApplicationCreate`, and `ApplicationUpdate`
(same three-model pattern every other optional classification field on this entity already
follows):

| Field | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `application_type` | `Literal["custom", "cots", "saas", "legacy"] \| None` | Yes | `None` | Build-vs-buy/vendor classification. Independent of `hosting_model` (deployment location) — see spec.md Edge Cases. |

New literal type alias in `adp.application.models`, alongside `HostingModel`:

```python
ApplicationType = Literal["custom", "cots", "saas", "legacy"]
```

## Database: `applications` table (migration `039`)

```sql
ALTER TABLE applications ADD COLUMN application_type TEXT;
ALTER TABLE applications ADD CONSTRAINT ck_app_application_type
  CHECK (application_type IS NULL OR application_type IN ('custom', 'cots', 'saas', 'legacy'));
CREATE INDEX ix_applications_application_type ON applications (application_type);
```

Mirrors migration `016`'s `hosting_model` column/constraint/index shape exactly. Reversible:
`downgrade()` drops the index, then the constraint, then the column, in that order (matching `016`'s
own reverse order).

## API surface (no new endpoint)

- `POST /api/v1/applications` — `ApplicationCreate.application_type` optional, omitted → `None`.
- `PUT /api/v1/applications/{id}` — `ApplicationUpdate.application_type` optional;
  `model_fields_set`-based clear-vs-omit semantics (existing `update_application` mechanism,
  unchanged) — explicit `null` clears, omitted field leaves unchanged.
- `GET /api/v1/applications?application_type=cots` — new optional equality filter, mirroring
  `hosting_model`'s own query param.
- Every response shape (`Application`, `ApplicationListResponse`) includes `application_type`
  automatically once it's on `Application` — no response-model change needed beyond the field
  itself.

## Export projection (`adp.export.application_arch`, ADP-SPEC-045)

`_serialize_application()`'s returned dict gains one new key, `"application_type"`, sourced from
`app.application_type` — same treatment as every other scalar field already listed there. No new
file, no new export subtree — this is a field addition to the existing per-application JSON file
(`applications/<id>.json`).

## Frontend types (`web/src/api/application.ts`)

```typescript
export type ApplicationType = "custom" | "cots" | "saas" | "legacy";
```

added to the `Application` and `ApplicationCreate` interfaces (`ApplicationUpdate` inherits it via
`Partial<ApplicationCreate>`, unchanged).

## Frontend grouping dimension (`web/src/portfolio/groupApplications.ts`)

- `Dimension` union gains `"application_type"`.
- `DIMENSION_LABELS`/`ALL_DIMENSIONS` gain the new key/entry — placed last (6th), after
  `criticality`, matching the bead's own position as a later follow-on to the original 5.
- New `groupByApplicationType(apps)` using `bucketize()` with a fixed order
  `["custom", "cots", "saas", "legacy"]` and labels `Custom-Built` / `COTS` / `SaaS` /
  `Legacy/Mainframe`.
- `groupApplications()`'s switch statement gains a `case "application_type"` branch.
- `ALL_FILTER_FIELDS`/`FILTER_FIELD_LABELS` automatically inherit the new dimension (both are
  defined as `[...ALL_DIMENSIONS, ...]`/`{...DIMENSION_LABELS, ...}` — no separate edit needed
  there).
- `fieldHasBuckets()`/`operatorsForField()` — `application_type` is not listed in
  `NUMERIC_ONLY_FIELDS`/`STRING_ONLY_FIELDS`/either dual-mode array, so both functions already
  correctly treat it as a pure-bucket field (`operatorsForField` falls through to its `["eq"]`
  default) with zero code change needed in either function.

## No new entity, no new relationship, no new table
