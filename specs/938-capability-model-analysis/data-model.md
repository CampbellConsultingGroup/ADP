# Data Model: Capability Model Analysis (938)

## Stored (new)

### `technical_capabilities` (two additive columns, migration `047`)

| Column | Type | Rules |
|---|---|---|
| `lifecycle_status` | TEXT NOT NULL, default `'current'` | CHECK in `emerging, current, contained, retiring, retired` |
| `end_of_life_date` | DATE NULL | optional for every status |

Existing rows become `current` with no date. The downgrade drops both columns.

Pydantic: `TechCapLifecycle = Literal["emerging","current","contained","retiring","retired"]`.
- `TechnicalCapability` gains `lifecycle_status: TechCapLifecycle = "current"` and `end_of_life_date: date | None = None`.
- `TechnicalCapabilityCreate` and `TechnicalCapabilityUpdate` gain both fields, as optional.
- On update, `lifecycle_status: None` is rejected: the status is not nullable. An explicit `end_of_life_date: null` clears the date.

## Derived (never stored, guard test)

### `CapabilitySnapshot` (frozen dataclass, built per request)

| Field | Contents |
|---|---|
| `business` | id → (name, level, parent_id) |
| `app_caps` | id → (name, level, parent_id) |
| `technical` | id → (name, level, parent_id, lifecycle_status, end_of_life_date) |
| `biz_to_ac` | business L3 id → set of application capability ids |
| `ac_to_tc` | application capability id → set of technical capability ids |
| `ac_to_apps` | application capability id → set of app ids |
| `apps` | app id → (name, lifecycle_status, health_score) |
| `risk` | app id → risk fields; empty and `risk_visible=False` when the caller lacks the permission |
| `cost` | app id → TCO; empty and `cost_visible=False` when the caller lacks the permission |

### Enumerations

- `RiskBand = high | medium | low | unknown`. Worst first; unknown never sets the worst value. Rules are in research R4.
- `LifecycleBand = past_end_of_life | retiring | contained | current | emerging`. Worst first. Rules are in research R5.

### `CapabilityRollup` (one per business capability)

| Field | Meaning |
|---|---|
| `capability_id`, `level` | |
| `contributing_apps` | `[{id, name, via: [app capability refs]}]`, distinct, excluding retired |
| `excluded_retired_apps` | `[{id, name}]` |
| `health` | `{worst: 1-5 \| null, spread: {"1".."5", "unassessed", "no_data"}}` |
| `risk` | `{worst: RiskBand \| null, spread: {...}}`, or `null` when not visible |
| `cost` | `{total_tco: decimal-string \| null, apps_without_cost: int}`, or `null` when not visible |
| `exposure` | `{worst: LifecycleBand \| null, spread: {...}}` |

The spread for an L3 counts applications (health and risk) or technical capabilities (exposure). For L2 and L1 it counts **leaf L3s** by their own worst value, with `no_data` for leaves that have none (FR-007).

### `ImpactResult` (one per technical capability)

- `technical_capability` (ref with path)
- `covered_technical_ids`: itself, plus its children when it is an L2
- `application_capabilities`: `[{ref + path, via_technical_id}]`
- `applications`: `[{id, name, lifecycle_status, via: [ac ids]}]`, including retired applications, marked as such
- `business_capabilities`: `[{ref + path, routes: [ac ids]}]`, each listed once

### `TechnologyDependencies` (one per business L3)

- `[{technical ref + path, effective_band, via_app_capability}]`

### `CapabilityFindings`

- `overlaps`: `[{business ref + path, applications: [{id, name, via: [ac refs]}]}]`. Only entries with 2 or more distinct non-retired applications.
- `gaps.business_without_app_capability`: `[business L3 ref + path]`
- `gaps.app_capability_without_business`: `[app cap L3 ref + path]`
- `gaps.app_capability_without_application`: `[app cap L3 ref + path]`
- `shared`: `[{app cap L3 ref + path, business: [refs], count}]`, with count ≥ 3

## State transitions

Lifecycle status is set freely between any two values. There are no transition rules: it is an assessment, not a workflow. Past-end-of-life is derived from the date and never written to the status.
