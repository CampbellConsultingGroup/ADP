# Data Model: Application Capabilities (937)

Migration `046` (`down_revision = "045"`). All ids are `String(36)`.

## application_capabilities

| Column | Type | Rules |
|---|---|---|
| id | String(36) PK | uuid4 |
| name | String(255) NOT NULL | not blank; unique among siblings, case-insensitive |
| description | Text NULL | |
| parent_id | String(36) NULL, FK → application_capabilities.id | immutable after create |
| level | SmallInteger NOT NULL | derived: 1 if no parent, else parent.level + 1; ≤ 3; CHECK 1–3 |
| created_at / updated_at | timestamptz NOT NULL | |

Index: `uq_app_cap_sibling_name` UNIQUE on `(COALESCE(parent_id, ''), lower(name))`.
Delete is refused while children exist (store), so the self-FK needs no cascade.

## business_capability_app_capability_links

| Column | Type | Rules |
|---|---|---|
| business_capability_id | FK → business_capabilities.id ON DELETE CASCADE | target must be level 3 |
| app_capability_id | FK → application_capabilities.id ON DELETE CASCADE | must be level 3 |
| created_at | timestamptz NOT NULL | |

PK `(business_capability_id, app_capability_id)`, index on `app_capability_id`.

## app_capability_tech_cap_links

| Column | Type | Rules |
|---|---|---|
| app_capability_id | FK → application_capabilities.id ON DELETE CASCADE | must be level 3 |
| tech_cap_id | FK → technical_capabilities.id ON DELETE CASCADE | target must be level 2 or 3 |
| created_at | timestamptz NOT NULL | |

PK `(app_capability_id, tech_cap_id)`, index on `tech_cap_id`.

## app_capability_realizations

| Column | Type | Rules |
|---|---|---|
| app_capability_id | FK → application_capabilities.id ON DELETE CASCADE | must be level 3 |
| app_id | FK → applications.id ON DELETE CASCADE | any application |
| created_at | timestamptz NOT NULL | |

PK `(app_capability_id, app_id)`, index on `app_id`.

## Read models (Pydantic, `adp.application.models`)

- `ApplicationCapability` contains:
  - `id`, `name`, `description`, `parent_id`, `level: Literal[1,2,3]`;
  - `created_at`, `updated_at`;
  - `business_capability_count`, `technical_capability_count`, `realization_count`;
  - `warnings: list[AppCapWarning]`, where `AppCapWarning = Literal["missing_technical_capability"]`.
- `ApplicationCapabilityCreate` (`name`, `description`, `parent_id`) and `ApplicationCapabilityUpdate` (`name`, `description`). Both have `extra="forbid"` and a non-blank name.
- `ApplicationCapabilityDetail` = `ApplicationCapability` plus:
  - `path: list[CapRef]` (ancestors, L1 first);
  - `business_capabilities: list[CapRef]` (each with a `path`);
  - `technical_capabilities: list[TechCapRef]` (each with `level`);
  - `realized_by: list[AppRef]`.
- `AppCapSummary` (for reverse lookups) contains `id`, `name`, `level`, `path`, `warnings`, and `realized_by: list[AppRef]`.
- Link bodies: `{business_capability_id}`, `{tech_cap_id}`, `{app_id}`.

## Derived (never stored)

`warnings` contains `"missing_technical_capability"` when `level == 3 and technical_capability_count == 0`.

## Errors

| Store exception | HTTP | When |
|---|---|---|
| `AppCapNotFoundError` | 404 | application capability, or the far end, missing |
| `AppCapDepthError` | 422 | parent is L3 |
| `AppCapHasChildrenError` | 409 | delete with children |
| `DuplicateSiblingNameError` | 409 | sibling name taken |
| `CapabilityLevelError` | 422 | a level rule is broken (message names the rule) |
| `DuplicateAppCapLinkError` | 409 | link exists |
