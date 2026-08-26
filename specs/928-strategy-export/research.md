# Phase 0 Research: Continuous Strategy Domain Export to Versioned Files

**Feature**: 928-strategy-export
**Date**: 2026-08-26

No `[NEEDS CLARIFICATION]` markers remained in spec.md going into this phase — all three open
questions were resolved directly with the user during `/speckit.specify`. The decisions below
resolve implementation-level detail the spec deliberately left to plan.md, each by direct analogy
to ADP-SPEC-044/045's own already-shipped precedent rather than inventing a new pattern.

## Decision 1: Sync mechanism — reuse the existing periodic full-reconciliation loop unchanged

**Decision**: `adp.export.strategy.start_background_sync`/`stop_background_sync` are thin,
domain-bound wrappers around `adp.export.common`'s generic lifecycle functions, identical in
shape to `business_arch.py`'s and `application_arch.py`'s own wrappers. `adp.api.app`'s lifespan
hook gains a third `start_strategy_export()`/`stop_strategy_export()` pair, reusing
`ADP_BUSINESS_ARCH_EXPORT_ROOT`/`ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS` — no new env var.

**Rationale**: Identical problem to ADP-SPEC-045's own Decision 1 — a periodic full scan (not
write-path hooks) keeps this feature from touching any existing Strategy write path at all, and
reusing the same env vars means zero new configuration surface, matching the established
"three domains, one export root" pattern the parent epic's own progress comments describe.

**Alternatives considered**: A fourth, separately-configured env var/interval for this domain.
Rejected — no domain-specific reason exists for Strategy to sync on a different cadence than the
other two, and a fourth knob is pure configuration-surface growth with no corresponding benefit.

## Decision 2: Change detection — reuse the existing content-comparison, no new database table

**Decision**: `_write_entity_file` (from `adp.export.common`) is called unchanged — no new
"last exported" tracking table or column.

**Rationale**: Identical to both prior increments' own Decision 2 — comparing candidate content
against the file already on disk (ignoring the `exported_at` stamp) is a complete, already-tested
mechanism; there is nothing Strategy-specific to add.

## Decision 3: File layout — one file per theme/objective/initiative; every relationship embedded in the owning entity's file

**Decision**:

```text
export_root/strategy/
├── themes/
│   └── <theme_id>.json          # StrategicTheme fields + framework_ids (already on the model)
├── objectives/
│   └── <objective_id>.json      # StrategicObjective fields, computed status, progress[], + new
│                                 #   initiative_ids / depends_on_objective_ids / blocked_objective_ids
└── initiatives/
    └── <initiative_id>.json     # StrategyInitiative fields, objective_ids, control_mappings[]
```

No nested subdirectory (unlike ADP-SPEC-044's `value-streams/<id>/stages/`) — every relationship
this increment covers is either a flat scalar-id list or a small nested object list, both of which
fit directly as a field on the owning entity's own file, the same shape `application_arch.py`
already established for applications' `linked_business_capabilities`/`initiative_links`/etc.

**Objective's own file, beyond the existing `StrategicObjective` read-model fields**:
- `progress: list[{as_of_date, actual_value, note, recorded_by}]` — the objective's complete
  `ObjectiveProgressEntry` history (FR-012), ordered ascending by date (matching
  `list_progress_entries`'s own existing order).
- `depends_on_objective_ids` / `blocked_objective_ids` — both directions of
  `strategic_objective_dependencies` (FR-013), mirroring `ObjectiveDependenciesResponse`'s own
  `depends_on`/`blocks` field names exactly rather than inventing new ones.
- `initiative_ids` — the reverse of `StrategyInitiative.objective_ids` (FR-014). This field does
  not exist on the live `StrategicObjective` read model today (only the initiative's own model
  exposes the forward direction) — added here specifically because the parent epic's own stated
  purpose is closing exactly this kind of traceability gap, and the underlying join table
  (`strategy_initiative_objective_links`) already supports the reverse query trivially via the
  same bulk group-by this feature already needs for the forward direction.

**Initiative's own file**: matches `StrategyInitiative`'s existing read-model shape exactly
(`objective_ids`, `control_mappings` with live status/evidence/assessed_at) — no new field needed,
since that model already carries everything this increment's scope calls for.

**Theme's own file**: matches `StrategicTheme`'s existing read-model shape exactly
(`framework_ids` already present, added in 927-theme-framework-mapping) — no new field needed.

**Rationale**: Every new field name is chosen to match an existing API response shape
(`ObjectiveDependenciesResponse.depends_on`/`.blocks`) or an existing sibling model's own
convention (`StrategyInitiative.objective_ids` → `initiative_ids` the mirror image), rather than
inventing fresh naming for the same underlying concept.

## Decision 4: Bulk read strategy — one small, fixed set of group-by queries, not N+1 per entity

**Decision**: `_fetch_all(session)` builds one `StrategyExportSnapshot` via a fixed number of
queries regardless of how many themes/objectives/initiatives exist, mirroring
ADP-SPEC-045's own Decision 4 exactly:

- `list_themes(session)` (existing bulk function, already returns `framework_ids` per theme).
- `list_objectives(session)` returns *summaries* only (no linked ids) — this feature does **not**
  call `get_objective()` once per objective (an N+1 pattern this codebase's own precedent
  explicitly rejects). Instead: one raw `SELECT` on `_objectives` for every scalar field, plus one
  bulk group-by query per link table (`_objective_capabilities`, `_objective_value_streams`,
  `_objective_design_links`, `_objective_application_links`, `_objective_control_links`,
  `_objective_dependencies` — read once, grouped both by `objective_id` for `depends_on` and by
  `depends_on_objective_id` for `blocks`, `strategy_initiative_objective_links` — read once,
  grouped both by `objective_id` for the reverse `initiative_ids` and by `initiative_id` for the
  initiative's own forward `objective_ids`) — each producing a `dict[str, list[str]]` keyed by
  `objective_id`.
- **Status is computed in-memory, not re-queried per objective**: `_progress` is read once in
  full, grouped by `objective_id` and sorted by `as_of_date` (matching `list_progress_entries`'s
  own order), then `compute_status()` (the existing pure function, imported directly) is called
  once per objective against its own pre-fetched progress list — zero additional I/O beyond the
  single bulk progress read.
- `list_initiatives(session)` (existing function) — **implementation-time deviation from this
  decision's original text, recorded rather than silently patched over**: `list_initiatives()`
  actually calls `get_initiative()` once per initiative internally (1 query for `objective_ids` +
  5 mirror-table JOINs for `control_mappings` each), an N+1 shape this decision originally set out
  to avoid by re-deriving `_linked_control_mappings`' five-table dispatch in bulk here too. Reused
  as-is instead: at this domain's stated scale (low hundreds of initiatives), ~7 queries per
  initiative stays well within "completes within its own interval" (plan.md's actual performance
  goal), and reusing already-correct, already-tested per-initiative logic is lower-risk than
  duplicating the same five-table `target_type` dispatch a second time in this new module for a
  query-count win this domain's scale doesn't actually need. Themes and objectives (the two
  entity types with real per-row volume) still use the fully-bulk approach below.
- `capability_design_links`/`value_stream_design_links` (Clarification Q2) are read via
  `adp.business.store._cap_design_links`/`._vs_design_links` directly (that module's own Table
  objects, imported read-only) — one bulk group-by query each, added to `business_arch.py`'s own
  existing `_fetch_all()`, not duplicated in this module.

**Rationale**: Directly reuses ADP-SPEC-045's own justification — a background reconciliation
cycle runs on a fixed schedule regardless of data volume; a per-entity query pattern would
degrade linearly with theme/objective/initiative count for no benefit over a small, fixed set of
`GROUP BY`-style reads.

**Alternatives considered**: Calling `get_objective()`/`get_theme()` once per entity (the simplest
code to write). Rejected — this is the exact N+1 pattern ADP-SPEC-045's Decision 4 already
rejected for the same reason, and nothing about Strategy's own data shape makes the tradeoff
different here.

## Decision 5: Shared export infrastructure — reuse `adp.export.common` verbatim, no refactor needed

**Decision**: `adp.export.strategy` imports `adp.export.common`'s helpers exactly as
`application_arch.py` already does — no changes to `common.py` itself.

**Rationale**: The extraction this feature would otherwise have needed already happened in
ADP-SPEC-045 (its own Decision 5), specifically anticipating a third domain. This is the payoff of
that earlier investment: this increment needs strictly less new plumbing than either prior one.

## Decision 6: Extending `business_arch.py` for Clarification Q2, not a new ownerless location

**Decision**: `_serialize_capability`/`_serialize_value_stream` (in the already-shipped
`adp.export.business_arch`) each gain one new parameter, `linked_designs: list[str]`, populated
from the new bulk queries added to that module's own `_fetch_all()`. This is the one
non-purely-additive change in this feature (Complexity Tracking, plan.md).

**Rationale**: `capability_design_links`/`value_stream_design_links` connect a Business
Architecture entity (already exported by ADP-SPEC-044) to a Design (not exported by any of these
three modules, addressed only by id everywhere else in this export tree — e.g.
`objective_design_links`'s own `design_ids` field is a bare id list too). Since a capability's or
value stream's own file is the correct, already-established home for "which designs this
capability/value-stream is linked to," extending it directly — the same way `_serialize_stage`
already embeds `linked_capability_ids` — is more consistent than inventing a third file location
owned by neither Business Architecture nor Strategy.

**Regression safety**: `business_arch.py`'s existing serialization tests
(`test_business_arch_serialize.py`) use exact-dict equality (`assert result == {...}`) and must be
updated, not just left passing, to include the new field — tasks.md sequences this as an explicit
task, not an incidental side effect discovered during implementation.

## Decision 7: Module name — `adp.export.strategy`, not `adp.export.strategy_arch`

**Decision**: The new sibling module is named `strategy.py`, breaking the superficial
`<domain>_arch.py` naming pattern of its two siblings.

**Rationale**: `business_arch`/`application_arch` name themselves after "architecture" domains
(Business Architecture, Application Architecture, per this platform's own domain vocabulary).
Strategy is not itself an architecture domain in that sense (it is planning/execution data that
*traces to* architecture), so forcing an `_arch` suffix onto it would misname the module rather
than follow a real convention. `adp.strategy` (the domain package this module reads from) already
uses the bare domain name with no such suffix, which this module's own name matches.

**Alternatives considered**: `strategy_export.py` (parallels neither sibling's actual name, which
is `<domain>_arch.py`, not `<domain>_export.py`). Rejected as inventing a third naming pattern for
no benefit over reusing the domain's own bare name.
