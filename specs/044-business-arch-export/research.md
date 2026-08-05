# Research: Continuous Business Architecture Export to Versioned Files

## Decision 1 — Sync mechanism: periodic full-reconciliation, not event-driven

**Decision**: An in-process background task (started from the FastAPI app's existing lifespan/startup hook, alongside other in-process singletons like the JWKS cache — no new worker process or external scheduler) that wakes up on a fixed interval and does a **full reconciliation pass**: read every business capability, value stream, value stream stage (with its linked capability IDs), and business domain currently in Postgres, and reconcile the exported file tree against that complete live snapshot (write what's missing/changed, delete what's gone).

**Rationale**: The alternative — hooking export logic into every write path in `adp/business/store.py` (create/update/delete for four entity types plus the stage-reorder and stage-capability-link operations) — was rejected for a concrete reason found during research: `value_stream_stages` has **no `updated_at` column at all**, and none of `add_stage`/`update_stage`/`delete_stage`/`reorder_stages` touch the parent value stream's `updated_at` either (confirmed by reading `src/adp/business/store.py`). An event/timestamp-driven approach would need to either add a schema change (out of scope — this feature explicitly introduces no new persisted classification value, per spec.md FR-005's spirit) or modify five existing, already-shipped write functions to emit change events, meaningfully raising the risk of accidentally breaking currently-working write paths for a purely-additive read-side feature. A periodic full scan needs to touch none of that code at all — it only ever *reads* `adp.business.store`'s existing list/get functions.

At the expected data volume (hundreds, not millions, of business architecture rows), a full reconciliation scan every cycle is computationally cheap. This also gets FR-008 (first-run bootstrap) and FR-004 (deletion cleanup) essentially for free — a "from scratch" reconciliation and a "steady state" reconciliation are the same code path, not two.

**Alternatives considered**:
- *Write-path hooks / change events* — rejected above (missing timestamp column, risk to existing write paths).
- *Postgres LISTEN/NOTIFY* — would solve the missing-timestamp problem, but introduces a new persistent connection/listener component and asyncpg-specific plumbing this codebase doesn't otherwise use for its business domain; disproportionate for a bounded-staleness-is-fine (per spec.md's resolved FR-002) v1.
- *External scheduled job (cron/separate process)* — rejected: introduces new deployment/ops surface (a second process to run, monitor, and keep in sync with the API's own codebase and DB credentials) where an in-process `asyncio` task, already this codebase's pattern for its other background-ish concerns, is sufficient at this scale.

## Decision 2 — Change detection: compare against on-disk content, not a new database table

**Decision**: For each entity, serialize what its exported file's content *should* be, then compare it against the current on-disk file's content (if any). Write only on a mismatch (FR-009). No new database table is introduced to track "last exported state" — the exported file tree itself, on disk, **is** the state to diff against.

**Rationale**: spec.md's Key Entities section left "Export Sync State" open as "an implementation decision for the planning phase." Once Decision 1 settled on full reconciliation (not event-driven), a separate persisted sync-state table would be pure duplication — the filesystem already holds exactly the information needed ("what did we export last time"), and reading a small JSON file to compare is no more expensive than reading a database row would have been. This also sidesteps the `value_stream_stages` missing-`updated_at` problem from Decision 1 entirely: content comparison never depends on any timestamp column existing.

Deletion detection (FR-004) follows the same content-vs-filesystem approach: each reconciliation pass also lists the IDs already present in each output subdirectory and removes any file whose ID is no longer in the current live query result.

**Alternatives considered**:
- *New `export_sync_state` table (id, entity_type, content_hash, last_synced_at)* — rejected as redundant once the filesystem itself serves as the comparison baseline; would also be the first schema migration this feature needs, for no functional gain.
- *Rely on `updated_at` timestamps* — rejected per Decision 1 (the column doesn't exist for stages, and isn't bumped by every relevant write even where it does exist).

## Decision 3 — File layout: one nested tree, stages under their parent value stream

**Decision**: Under a configured root, one file per entity instance, keyed by the entity's existing internal ID (never its user-editable name, per spec.md's Threat Model path-traversal mitigation):

```text
<export_root>/business-architecture/
  capabilities/<capability-id>.json
  domains/<domain-id>.json
  value-streams/<value-stream-id>/value-stream.json
  value-streams/<value-stream-id>/stages/<stage-id>.json
```

Each stage's file includes `linked_capability_ids: [...]` (FR-011). A capability's file includes its own `domain_id`/`strategic_relevance`/`maturity_level` (already on the entity, FR-010) but not a reverse-index of which value stream stages link to it — that reverse view, if wanted, is a projection over the already-exported stage files, not something worth duplicating into every capability file.

**Rationale**: Nesting stages under their owning value stream directory means deleting a value stream (FR-004) is a single subtree removal, and a reviewer looking at "what changed in Order-to-Cash's stages" finds them in one place — directly serving Story 2's "diff scoped to exactly what changed" goal. IDs (not names) as filenames satisfy the Threat Model's path-traversal mitigation without needing a separate sanitization step for arbitrary user-entered names.

**Alternatives considered**:
- *Flat `value-stream-stages/<stage-id>.json` alongside `value-streams/<vs-id>.json`* — rejected: loses the natural "delete the whole value stream's subtree on value-stream deletion" property; a reviewer has to cross-reference `value_stream_id` fields instead of just looking in one directory.
- *Capability files embedding the reverse stage-link index* — rejected: would require rewriting every linked capability's file whenever a stage's links change, multiplying the blast radius of a small edit and working against FR-003/FR-009's "diff scoped to exactly what changed, and don't rewrite the unchanged" goals.

## Decision 4 — Configuration: new env var, feature disabled by default

**Decision**: A new environment variable, `ADP_BUSINESS_ARCH_EXPORT_ROOT`, following this codebase's existing `ADP_`-prefixed convention (`.env.example`). If unset, the background sync task is **not started at all** — this feature is opt-in, not a silent default write to some assumed path. A second env var, `ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS` (default a low-double-digit number of seconds), controls the reconciliation cadence, satisfying spec.md's "bounded staleness window... on the order of seconds to low minutes" assumption.

**Rationale**: ADP-SPEC-011's existing design export takes `export_root` as a **per-request** field (the caller, e.g. the web UI, supplies it each time) — there is no existing server-side default path to reuse, because that feature has no notion of "where exports always go," only "where THIS export goes." This feature has no per-request trigger at all (it's a background task), so the destination has to come from configuration, not a request. Defaulting to "disabled unless configured" avoids ever writing to a guessed path on a developer's or CI's filesystem by surprise.

**Alternatives considered**:
- *A default path like `./architecture-export/`* — rejected: writing to the filesystem automatically and continuously with no explicit opt-in is a bigger, more surprising default than this feature's incremental, additive framing calls for.

## Decision 5 — Failure handling and atomicity

**Decision**: Each reconciliation cycle is wrapped in a single try/except at the top level; any exception is logged as a structured `WARNING`-or-higher event (ART-VI) with enough context to diagnose (which cycle, what was in progress), and the background task loop continues to the next scheduled cycle rather than crashing the whole API process (FR-006). Each individual file write within a cycle uses a write-to-temp-file-then-atomic-rename pattern (`os.replace`), so a crash mid-write never leaves a half-written file in place of a previously-good one (FR-007) — this is a lighter-weight, per-file analogue of ADP-SPEC-011's own tempdir-then-`copytree` atomicity, appropriately scaled down since this feature writes many small independent files per cycle rather than one large bundle.

**Alternatives considered**:
- *Let an unhandled exception propagate and crash the background task permanently* — rejected: a single bad cycle (e.g., a transient DB blip) would then permanently stop all future syncs until a process restart, defeating FR-006's "surfaced, not silent" requirement by turning one transient failure into a total, possibly-unnoticed outage of the whole feature.
- *Whole-tree tempdir-then-`copytree` per cycle (mirroring ADP-SPEC-011 exactly)* — rejected: ADP-SPEC-011 replaces one whole bundle per (manually-triggered, infrequent) export; this feature runs continuously and mutates a small subset of many files per cycle (per Decision 2's content-diffing), so an atomic per-file rename achieves the same "never leave a corrupted file" guarantee (FR-007) without rewriting every unrelated file on every cycle, which would itself violate FR-009.
