# Phase 0 Research: Continuous Application Registry Export

All five decisions below extend or directly reuse ADP-SPEC-044's already-shipped mechanism (`adp.export.business_arch`) rather than inventing a second one. Where this domain differs materially from Business Architecture — sensitivity gating, per-app relationship tables, no bulk-list functions for several tables — each decision says so explicitly.

## Decision 1: Sync mechanism — reuse ADP-SPEC-044's periodic full-reconciliation loop unchanged

**Decision**: The same `_background_loop` / `start_background_sync` / `stop_background_sync` shape ADP-SPEC-044 built is reused as-is (extracted into a shared module, see Decision 5) — a periodic full scan of live application-registry data, not event-driven write-path hooks.

**Rationale**: Several tables in this domain (`application_risk`, `application_cost`, `application_contracts`, `application_quality_metrics`) are simple upsert-only 1:1 tables with an `updated_at` column and *would* support timestamp-based change detection — unlike ADP-SPEC-044's `value_stream_stages`, which had no `updated_at` at all. But several others genuinely have none appropriate for this purpose (`application_capability_links`, `application_tech_cap_links`, `application_stage_links`, `application_initiative_links` are pure join tables with no timestamp column of their own), so a uniform mechanism across the whole domain still requires full reconciliation for at least the relationship tables. Rather than run two different sync strategies in the same feature (timestamp-diffing for some tables, full-scan for others), one uniform full-reconciliation pass is simpler and is what ADP-SPEC-044 already proved reliable.

**Alternatives considered**: Hybrid — timestamp-based incremental sync for the six 1:1/entity tables that have `updated_at`, full reconciliation only for the four join tables. Rejected: doubles the mechanisms this feature has to test and reason about for a domain whose total row count (hundreds of applications, low thousands of relationship rows) doesn't come close to needing the extra complexity — full reconciliation's own cost is `O(rows)` table scans, not `O(rows²)`, and stays well within budget at this scale.

## Decision 2: Change detection — reuse ADP-SPEC-044's content-comparison, no new database table

**Decision**: Identical to ADP-SPEC-044 — compare each candidate file's serialized content (minus `exported_at`) against what's already on disk; write only on a real difference. No new database table.

**Rationale**: Already proven correct and adequate at this scale in production use (ADP-SPEC-044); introducing a second change-detection strategy for this domain would be inconsistent for no benefit.

**Alternatives considered**: None seriously — this is a direct precedent reuse, not a new design question.

## Decision 3: File layout — one file per application/technical-capability/initiative/integration; relationships embedded in the owning entity's file

**Decision**: New subdirectories under the same `export_root` as ADP-SPEC-044, sibling to `business-architecture/`:

```
<export_root>/applications/
├── applications/<app_id>.json              # core fields + risk + cost + governance +
│                                            # quality + all outbound relationships, embedded
├── technical-capabilities/<tc_id>.json
├── transformation-initiatives/<ti_id>.json  # includes member app links + disposition
└── integrations/<integration_id>.json       # app-to-app; belongs to neither side alone
```

An application's own file embeds: its risk/cost/governance/quality records (all strictly 1:1 with the application — spec FR-015/016/017 phrase this explicitly as part of "an application's exported file representation"), and its outbound relationship arrays (linked business capabilities with fit score, linked technical capabilities with usage type, linked value-stream stages, domain integrations). This mirrors ADP-SPEC-044's own precedent of embedding a value-stream-stage's `linked_capability_ids` directly in the stage's file rather than as a separate relationship file.

**Rationale**: Every embedded record is either strictly 1:1 with the application (risk/cost/governance/quality — there is exactly one row per app, if any) or naturally "owned" by the application as the many-side of a many-to-one/many-to-many relationship it initiates. Application-to-application integrations are the one relationship type that does NOT have a natural single owner (it connects two peer applications symmetrically), so it gets its own file per FR-012 and the spec's explicit call-out.

**Alternatives considered**: A separate file per relationship record (e.g., one file per capability link) — rejected as needless proliferation of tiny files for data that is meaningless without its owning application's context, and a worse diff experience (a single app's relationship change would still touch only that app's file either way, so the "scoped diff" property FR-003 wants is achieved without the extra files).

## Decision 4: Bulk read strategy — direct Core Table queries where no bulk-list store function exists

**Decision**: `adp.application.store` has full bulk-list functions for `Application` (`list_applications`), `TechnicalCapability` (`list_technical_capabilities`), `TransformationInitiative` (`list_initiatives`), and app-to-app integrations (`list_integrations(app_id=None, ...)` — already bulk when called with no `app_id` filter) — all reused directly, unmodified. However, `application_risk`, `application_cost`, `application_contracts`, `application_quality_metrics`, and all four relationship/join tables (`application_capability_links`, `application_tech_cap_links`, `application_stage_links`, `application_initiative_links`) have only per-application-scoped store functions (e.g. `get_application_risk(app_id, ...)`, `list_app_capability_links(app_id, ...)`) — calling these once per application would be an `O(applications)` query fan-out per reconciliation cycle. Direct `sa.select()` against the store module's own (already-defined) Core `Table` objects is used instead, exactly as ADP-SPEC-044 did for `value_stream_stages`/`value_stream_stage_capabilities` (which had the identical gap).

**Rationale**: Keeps the reconciliation cycle at a small, fixed number of queries (roughly one per table, ~14 total) regardless of application count, matching ADP-SPEC-044's own stated goal ("a small, fixed number of queries (not one per entity)").

**Alternatives considered**: Add new bulk-list functions to `adp.application.store` itself (e.g., `list_all_application_risk(session)`). Rejected for this increment: it would touch already-shipped, tested store code for a need that's specific to this export feature and isn't needed by any existing API caller — same reasoning ADP-SPEC-044 used to justify reading `bstore._stages`/`bstore._stage_caps` directly rather than adding a new store function.

## Decision 5: Shared export infrastructure — extract common helpers from `adp.export.business_arch` into `adp.export.common`

**Decision**: Refactor the domain-agnostic parts of `adp.export.business_arch` (`_safe_path_component`, `_safe_filename`, `_write_file_atomic`, the content-comparison-aware `_write_entity_file`, `_cleanup_orphan_files`, `_cleanup_orphan_dirs`, and the `_background_loop`/`start_background_sync`/`stop_background_sync` lifecycle) into a new shared module, `adp.export.common`. `adp.export.business_arch` is refactored to import from it (behavior-preserving; its existing test suite continues to pass unchanged and is the regression safety net for the refactor). The new `adp.export.application_arch` module (this feature) uses the same shared helpers rather than re-implementing them a second time.

**Rationale**: This is the second domain built on this pattern, and the parent epic (ADP-81p) already anticipates more; duplicating ~150 lines of atomic-write/background-loop/orphan-cleanup logic a second time now, only to duplicate it a third time for the next domain, is the kind of complexity ADP-SPEC-044's own plan explicitly favored avoiding ("every design decision picks the simpler alternative"). The domain-specific parts (what to fetch, how to serialize, the file-tree shape) stay in each domain's own module; only the truly generic mechanics move to the shared module.

**Alternatives considered**:
- **Duplicate the ~150 lines into the new module, as-is.** Rejected: guarantees the two implementations silently drift over time (e.g., a future bugfix to atomic-write handling applied to one module and not the other) and makes a third domain's author choose between duplicating again or doing this exact refactor later, under more time pressure and with more call sites to update.
- **Extract now AND migrate `adp.export.bundle` (ADP-SPEC-011) onto the same shared helpers too.** Rejected as out of scope: ADP-SPEC-011's exporter has different semantics entirely (manual trigger, confirmation-gated, whole-directory `copytree` rather than per-file atomic writes) — forcing it onto this shared module would be a change to already-shipped, unrelated behavior with no benefit to this feature, and is exactly the kind of scope creep the original ADP-81p epic bead warned against.
