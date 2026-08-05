# Phase 1 Data Model: Continuous Application Registry Export

## 1. Source tables (existing, read-only — ADP-SPEC-036/038, `src/adp/application/store.py`)

| Table | Key columns | Notes |
|---|---|---|
| `applications` | `id`, `name`, `description`, `vendor`, `primary_owner`, `time_classification`, `r_strategy`, `pace_layer`, `health_score`, `business_value`, `business_criticality`, `owning_business_unit`, `business_owner`, `technical_owner`, `lifecycle_status`, `hosting_model`, `architecture_pattern`, `tech_debt_flags` (JSON array), `created_at`, `updated_at` | Bulk-listed via `list_applications(session)`. |
| `technical_capabilities` | `id`, `name`, `description`, `parent_id`, `level`, `created_at`, `strategic_relevance` | Bulk-listed via `list_technical_capabilities(session)`. |
| `transformation_initiatives` | `id`, `name`, `description`, `target_date`, `created_at`, `updated_at` | Bulk-listed via `list_initiatives(session)`. |
| `application_integrations` | `id`, `source_app_id`, `target_app_id`, `integration_type`, `description`, `created_at`, `updated_at` | Bulk-listed via `list_integrations(app_id=None, session)`. |
| `application_risk` | `app_id` (PK), `security_posture`, `vulnerability_status`, `data_classification`, `regulatory_tags` (JSON array), `dr_bc_status`, `end_of_life_date`, `end_of_support_date`, `updated_at` | 1:1 with `applications`. No bulk-list function — read directly via `sa.select(astore._application_risk)` (Decision 4). |
| `application_cost` | `app_id` (PK), `currency`, `horizon_years`, 8 buckets × (`{bucket}_one_time`, `{bucket}_annual`) as `Numeric(14,2)`, `updated_at` | 1:1 with `applications`. Direct query, same as above. |
| `application_contracts` | `app_id` (PK), `contract_terms`, `renewal_date`, `sla`, `business_sponsor`, `it_owner`, `decision_rights`, `updated_at` | 1:1 with `applications` (this is the "governance" record). Direct query. |
| `application_quality_metrics` | `app_id` (PK), `uptime_pct` (`Numeric(5,2)`), `incidents_ytd`, `satisfaction_score`, `perf_note`, `ticket_volume_30d`, `updated_at` | 1:1 with `applications`. Direct query. |
| `application_capability_links` | `app_id`, `capability_id`, `fit_score` | Join to `business_capabilities` (ADP-SPEC-033/044) for `capability_name`. Direct query, all rows, no `app_id` filter. |
| `application_tech_cap_links` | `app_id`, `tech_cap_id`, `usage_type` | Join to `technical_capabilities` for `tech_cap_name`. Direct query, all rows. |
| `application_stage_links` | `app_id`, `stage_id` | Join to `value_stream_stages` (ADP-SPEC-044) for `stage_name`. Direct query, all rows. |
| `application_domain_integrations` | `id`, `app_id`, `domain_id` (nullable), `integration_type`, `direction`, `created_at` | Join to `business_domains` (ADP-SPEC-044) for `domain_name` when `domain_id` is set. Direct query, all rows. |
| `application_initiative_links` | `app_id`, `initiative_id`, `planned_disposition` | Join to `transformation_initiatives` for `initiative_name`. Direct query, all rows. |

Explicitly **excluded** (spec FR-014): `application_design_links` — connects to `designs`, already covered by ADP-SPEC-011's separate export mechanism.

## 2. Exported file shapes

All files share the same envelope convention as ADP-SPEC-044: `exported_at` (ISO-8601 UTC) is stamped at write time by the shared `adp.export.common` helper and is excluded from content-comparison (Decision 2), so it never by itself makes an unchanged entity look changed.

### 2.1 `applications/applications/<app_id>.json`

```json
{
  "id": "…",
  "name": "…",
  "description": null,
  "vendor": null,
  "primary_owner": null,
  "time_classification": null,
  "r_strategy": null,
  "pace_layer": null,
  "health_score": null,
  "business_value": null,
  "business_criticality": null,
  "owning_business_unit": null,
  "business_owner": null,
  "technical_owner": null,
  "lifecycle_status": "active",
  "hosting_model": null,
  "architecture_pattern": null,
  "tech_debt_flags": [],
  "risk": {
    "security_posture": null, "vulnerability_status": null, "data_classification": null,
    "regulatory_tags": [], "dr_bc_status": null,
    "end_of_life_date": null, "end_of_support_date": null
  },
  "cost": {
    "currency": "USD", "horizon_years": 5,
    "acquisition": {"one_time": "0", "annual": "0"},
    "implementation": {"one_time": "0", "annual": "0"},
    "training": {"one_time": "0", "annual": "0"},
    "operational": {"one_time": "0", "annual": "0"},
    "maintenance": {"one_time": "0", "annual": "0"},
    "upgrades": {"one_time": "0", "annual": "0"},
    "risk_downtime": {"one_time": "0", "annual": "0"},
    "end_of_life": {"one_time": "0", "annual": "0"}
  },
  "governance": {
    "contract_terms": null, "renewal_date": null, "sla": null,
    "business_sponsor": null, "it_owner": null, "decision_rights": null
  },
  "quality": {
    "uptime_pct": null, "incidents_ytd": null, "satisfaction_score": null,
    "perf_note": null, "ticket_volume_30d": null
  },
  "linked_business_capabilities": [
    {"capability_id": "…", "capability_name": "…", "fit_score": 4}
  ],
  "linked_technical_capabilities": [
    {"tech_cap_id": "…", "tech_cap_name": "…", "usage_type": "provides"}
  ],
  "linked_value_stream_stages": [
    {"stage_id": "…", "stage_name": "…"}
  ],
  "domain_integrations": [
    {"id": "…", "domain_id": "…", "domain_name": "…", "integration_type": "…", "direction": "inbound"}
  ],
  "initiative_links": [
    {"initiative_id": "…", "initiative_name": "…", "planned_disposition": "modernize"}
  ],
  "exported_at": "…"
}
```

`risk`/`cost`/`governance`/`quality` are present with all-null/all-zero fields (never omitted) when the application has no such record at all (edge case in spec.md, FR-018) — this is the platform's own "unset" shape (mirroring what `ApplicationRisk()`/`ApplicationCost()`/etc. default-construct to when the API's `GET` returns a record that was never upserted), not a special "no data" marker. `Decimal` cost amounts are serialized as JSON strings (e.g. `"0"`, `"2000.50"`), matching how `ApplicationCost`'s own Pydantic JSON serialization already renders `Decimal` — never as a binary float, per the codebase's existing "money must never use binary floating point" convention (`models.py` comment above `TCO_BUCKET_NAMES`).

### 2.2 `applications/technical-capabilities/<tc_id>.json`

```json
{
  "id": "…", "name": "…", "description": null,
  "parent_id": null, "level": 1, "strategic_relevance": null,
  "exported_at": "…"
}
```

### 2.3 `applications/transformation-initiatives/<initiative_id>.json`

```json
{
  "id": "…", "name": "…", "description": null, "target_date": null,
  "members": [
    {"app_id": "…", "app_name": "…", "planned_disposition": "retire"}
  ],
  "exported_at": "…"
}
```

`members` is the initiative-side view of the same `application_initiative_links` rows embedded in each application's own file (§2.1 `initiative_links`) — both directions are exported so a reader can navigate from either the application or the initiative without cross-referencing IDs by hand, mirroring how ADP-SPEC-044's stage file embeds capability IDs without requiring a capability-side back-reference (this domain's initiative case is symmetric enough on both sides to warrant it).

### 2.4 `applications/integrations/<integration_id>.json`

```json
{
  "id": "…",
  "source_app_id": "…", "source_app_name": "…",
  "target_app_id": "…", "target_app_name": "…",
  "integration_type": "API", "description": null,
  "exported_at": "…"
}
```

## 3. Reconciliation algorithm (one cycle)

1. **Fetch** (Decision 4 — small, fixed query count): `list_applications`, `list_technical_capabilities`, `list_initiatives`, `list_integrations(app_id=None)`, plus direct `sa.select()` against `_application_risk`, `_application_cost`, `_application_contracts`, `_application_quality_metrics`, `_app_cap_links` (joined to `_biz_caps`), `_app_tech_cap_links` (joined to `_tech_caps`), `_app_stage_links` (joined to `_stages`), `_app_domain_integrations` (left-joined to `_domains`), `_app_initiative_links` (joined to `_transformation_initiatives`).
2. **Group** each 1:1 record and each relationship-row list by `app_id` (and, for initiatives, additionally by `initiative_id` for the reverse `members` view) — all in Python, no extra queries.
3. **Serialize and write** (via the shared `adp.export.common` helpers, Decision 5): one file per application (embedding its own 1:1 records + relationship arrays), one per technical capability, one per transformation initiative (embedding its `members`), one per app-to-app integration. Skip the write if on-disk content (minus `exported_at`) already matches.
4. **Clean up orphans**: for each of the four file-bearing entity types, delete any `<id>.json` in its directory whose `id` is no longer in that entity's live set (same `_cleanup_orphan_files` helper as ADP-SPEC-044 — no directory-level cleanup is needed here since, unlike ADP-SPEC-044's per-value-stream subdirectories, every entity type in this domain is a flat directory of files).
5. **On any exception**, log a structured warning and return — never raise out of the reconciliation cycle, never leave a partial file (the shared atomic-write helper already guarantees the latter per-file).
