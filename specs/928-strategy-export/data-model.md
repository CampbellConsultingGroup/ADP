# Data Model: Continuous Strategy Domain Export to Versioned Files

**Feature**: 928-strategy-export
**Date**: 2026-08-26

No new database tables, columns, or migration — this feature reads exclusively from existing
tables (specs 050/915/916/917/918/925/927/034) and writes only to the filesystem. The tables below
are already-shipped and unchanged by this feature; this document records which fields of each are
projected into the exported JSON, and the one existing-file extension (Clarification Q2).

## Source tables (read-only, all pre-existing)

| Table | Owning module | Used for |
|---|---|---|
| `strategic_themes` | `adp.strategy.store` | Theme file |
| `strategic_objectives` | `adp.strategy.store` | Objective file (scalar fields) |
| `strategic_objective_progress` | `adp.strategy.store` | Objective file's `progress` list |
| `strategic_objective_capabilities` | `adp.strategy.store` | Objective file's `capability_ids` |
| `strategic_objective_value_streams` | `adp.strategy.store` | Objective file's `value_stream_ids` |
| `objective_design_links` | `adp.strategy.store` | Objective file's `design_ids` |
| `objective_application_links` | `adp.strategy.store` | Objective file's `application_ids` |
| `objective_control_links` | `adp.strategy.store` | Objective file's `control_ids` |
| `strategic_objective_dependencies` | `adp.strategy.initiatives` | Objective file's `depends_on_objective_ids`/`blocked_objective_ids` |
| `theme_framework_links` | `adp.strategy.store` | Theme file's `framework_ids` (already on the read model) |
| `strategy_initiatives` | `adp.strategy.initiatives` | Initiative file (scalar fields) |
| `strategy_initiative_objective_links` | `adp.strategy.initiatives` | Initiative file's `objective_ids`; Objective file's `initiative_ids` (reverse) |
| `initiative_control_{capability,application,design,pattern,organization}_mapping` (5 tables) | `adp.strategy.initiatives` | Initiative file's `control_mappings` |
| `control_{capability,application,design,pattern,organization}_mapping` (5 mirror tables) | `adp.strategy.store` | Live `compliance_status`/`evidence_ref`/`assessed_at` joined into `control_mappings` (never a value captured at link time) |
| `capability_design_links` | `adp.business.store` | **Extends** ADP-SPEC-044's capability file: `linked_designs` |
| `value_stream_design_links` | `adp.business.store` | **Extends** ADP-SPEC-044's value-stream file: `linked_designs` |

## Exported file shapes

### `strategy/themes/<theme_id>.json`

```json
{
  "id": "...", "name": "...", "description": null, "owner": null, "priority": null,
  "framework_ids": [],
  "created_at": "..."
}
```

Directly mirrors `StrategicTheme` (adp.strategy.models) — no new field, no field omitted.

### `strategy/objectives/<objective_id>.json`

```json
{
  "id": "...", "theme_id": "...", "owner": "...", "statement": "...",
  "metric_name": null, "target_value": null, "target_unit": null, "direction": null,
  "fiscal_year": 2026, "period": "Q1",
  "status": "on_track", "status_reason": null,
  "capability_ids": [], "value_stream_ids": [], "design_ids": [], "application_ids": [],
  "control_ids": [],
  "depends_on_objective_ids": [], "blocked_objective_ids": [],
  "initiative_ids": [],
  "progress": [
    {"as_of_date": "2026-06-30", "actual_value": "12.5", "note": null, "recorded_by": "..."}
  ],
  "created_at": "...", "updated_at": "..."
}
```

`status`/`status_reason` mirror `StrategicObjective`'s own read model exactly (Clarification Q1 —
the computed value, via `compute_status()`, not raw stored columns). `depends_on_objective_ids`/
`blocked_objective_ids` mirror `ObjectiveDependenciesResponse.depends_on`/`.blocks`'s own field
names. `initiative_ids` and `progress` are the two additions beyond the live `StrategicObjective`
read model (research.md Decision 3) — both are data this objective already owns via an existing
join table/child table, just not currently surfaced on that one response shape. `target_value`/
`actual_value` are rendered as JSON strings (Decimal-precision money/metric values, matching
`application_arch.py`'s own established convention for `Decimal` fields — never a binary float).

### `strategy/initiatives/<initiative_id>.json`

```json
{
  "id": "...", "name": "...", "description": null, "owner": null, "status": "planned",
  "objective_ids": [],
  "control_mappings": [
    {
      "control_id": "...", "target_type": "application", "target_id": "...",
      "compliance_status": "non_compliant", "evidence_ref": null, "assessed_at": null
    }
  ],
  "created_at": "...", "updated_at": "..."
}
```

Directly mirrors `StrategyInitiative` (adp.strategy.initiatives) — no new field, no field omitted.
`control_mappings` entries mirror `ControlMappingRef` exactly, including live status (never
captured at link-creation time — the same JOIN-at-read-time guarantee the live API already makes).

### Extension to `business-architecture/capabilities/<capability_id>.json` and `business-architecture/value-streams/<vs_id>/value-stream.json`

Both gain one new field:

```json
{
  "...": "... (all existing fields, unchanged) ...",
  "linked_designs": ["DSN-001", "DSN-047"]
}
```

Empty list (not omitted) when no link exists — matching every other "absence" convention this
export tree already uses (e.g. `_serialize_stage`'s `linked_capability_ids`).

## Validation rules

- No new validation — every value written is already validated at the point it was originally
  written to Postgres (via the existing Strategy/Business Architecture write paths). This feature
  performs no writes of its own beyond the exported files themselves.
- `progress` is always sorted ascending by `as_of_date` (matching `list_progress_entries`'s own
  existing order) so a diff of the exported file reads the same direction a human would expect.
- Every `*_ids` list is sorted (string sort) for diff stability — matching
  `_linked_capability_ids`/`_linked_value_stream_ids`/etc.'s own existing `ORDER BY` clauses.

## State transitions

None — this feature is a read-only projection; no entity's lifecycle state is introduced or
changed by it.
