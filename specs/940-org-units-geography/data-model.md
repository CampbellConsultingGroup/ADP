# Data Model: Org Units and Geography (940)

Migration `048` (`down_revision="047"`). All ids are `String(36)`, except the seeded geography ids (R4), which are short stable strings and fit the same column.

## `org_units` (new)

| Column | Type | Rules |
|---|---|---|
| id | String(36) PK | uuid4 |
| name | String(255) NOT NULL | trimmed, non-blank |
| description | Text NULL | |
| parent_id | String(36) NULL FK → org_units.id | fixed after create |
| level | SmallInteger NOT NULL | CHECK 1–3; parent level + 1 (FR-001) |
| primary_geography_id | String(36) NULL FK → geographies.id ON DELETE SET NULL | FR-009 |
| created_at, updated_at | timestamptz NOT NULL | |

Index: unique `(lower(name), coalesce(parent_id,''))` for sibling uniqueness.

Derived on read (never stored): `kind` = enterprise | division | function, from level; `path` (L1 › L2); `application_count`.

## `geographies` (new, seeded)

| Column | Type | Rules |
|---|---|---|
| id | String(36) PK | seeded: `geo-001`, `geo-m49-NNN`, `geo-XX`; new rows get a uuid4 |
| name | String(255) NOT NULL | |
| code | String(8) NULL | countries: ISO 3166 alpha-2, `^[A-Z]{2}$`, unique where level=3 (partial unique index) |
| m49 | String(3) NULL | optional numeric code |
| parent_id | String(36) NULL FK → geographies.id | fixed after create |
| level | SmallInteger NOT NULL | CHECK 1–3 (global / region / country) |
| created_at, updated_at | timestamptz NOT NULL | |

Index: unique `(lower(name), coalesce(parent_id,''))`.

Derived on read: `kind`, `path`, `org_unit_count`.

## `org_unit_geographies` (new)

| Column | Type |
|---|---|
| org_unit_id | String(36) FK → org_units.id ON DELETE CASCADE |
| geography_id | String(36) FK → geographies.id ON DELETE CASCADE |
| created_at | timestamptz NOT NULL |

PK `(org_unit_id, geography_id)`, so a duplicate link is refused (409) (FR-008).

## `applications` (changed)

| Column | Change |
|---|---|
| owning_org_unit_id | **new** String(36) NULL FK → org_units.id ON DELETE SET NULL (FR-010, FR-013) |
| owning_business_unit | unchanged free text; never written by this feature (SC-004) |

Pydantic changes:
- `Application`, `ApplicationCreate` and `ApplicationUpdate` gain `owning_org_unit_id: str | None`.
- In `ApplicationUpdate`, an explicit null clears it (the existing `model_fields_set` idiom).

## Derived: unmatched value

`{ value: str, application_count: int, sample_app_ids: list[str] (≤5) }`. These are distinct exact `owning_business_unit` values with `owning_org_unit_id IS NULL`, after a trim test for emptiness.

## Pydantic models (`adp.organization.models`)

| Model | Fields |
|---|---|
| `OrgUnit` | id, name, description, parent_id, level, kind, primary_geography_id, geography_ids, path: list[Ref], application_count, timestamps |
| `OrgUnitCreate` | name, description, parent_id, primary_geography_id |
| `OrgUnitUpdate` | name, description, primary_geography_id (explicit null clears) |
| `Geography` | id, name, code, m49, parent_id, level, kind, path, org_unit_count |
| `GeographyCreate` | name, code, m49, parent_id |
| `GeographyUpdate` | name, code, m49 |
| `UnmatchedValue`, `ResolveUnmatched` | `ResolveUnmatched`: value, plus exactly one of org_unit_id / create{name, description?, parent_id} |
| `ResolveResult` | org_unit, updated_count |

Errors: `NotFound` (404), `Depth` (422), `HasChildren` (409), `DuplicateSibling` (409), `DuplicateCode` (409), `DuplicateLink` (409), `InvalidCode` (422).
