# Data Model: Continuous Business Architecture Export to Versioned Files

No new database entity, column, or migration. This feature reads four existing tables (`business_capabilities`, `value_streams`, `value_stream_stages`, `business_domains`) plus one existing join table (`value_stream_stage_capabilities`) — all already defined in `src/adp/business/store.py` (ADP-SPEC-033/034/035) — and produces a file-based *projection* of them. This document describes that projection: what each exported file contains and how the reconciliation algorithm derives it, not a new persisted schema.

## 1. Source data (existing, read-only)

| Table | Columns read | Notes |
|---|---|---|
| `business_capabilities` | `id`, `name`, `description`, `level`, `parent_id`, `position`, `domain_id`, `strategic_relevance`, `maturity_level` | `created_at`/`updated_at` exist but are **not** used for change detection (research.md Decision 1/2 — content comparison instead). |
| `value_streams` | `id`, `name`, `description`, `stakeholder`, `position` | |
| `value_stream_stages` | `id`, `value_stream_id`, `name`, `description`, `position` | Has no `updated_at` column at all — irrelevant here since change detection is content-based, not timestamp-based (research.md Decision 1). |
| `business_domains` | `id`, `name`, `scope_statement`, `classification`, `org_unit`, `risk_flags` | |
| `value_stream_stage_capabilities` | `stage_id`, `capability_id` | Pure join table (no independent identity); folded into each stage's `linked_capability_ids` list (FR-011), not exported as its own file. |

## 2. Exported file shapes

All files are UTF-8 JSON, pretty-printed with sorted keys (deterministic byte-for-byte output is required for research.md Decision 2's content-comparison approach to work — two reconciliation runs over unchanged source data must produce byte-identical file content, or FR-009's "don't rewrite unchanged files" guarantee breaks). Every file includes an `exported_at` field showing when *that specific file* was last actually written (not merely reconciled) — useful context for a human reading the file directly, distinct from the internal comparison mechanism (which compares everything BUT this field, so that the field's own presence doesn't itself cause every file to appear "changed" on every cycle).

### 2.1 Capability — `capabilities/<capability-id>.json`

```json
{
  "id": "cap-uuid",
  "name": "Risk Assessment",
  "description": "Evaluate applicant risk profile",
  "level": 2,
  "parent_id": "cap-parent-uuid",
  "position": 0,
  "domain_id": "domain-uuid",
  "strategic_relevance": 1,
  "maturity_level": 3,
  "exported_at": "2026-08-05T00:00:00Z"
}
```

`domain_id`, `strategic_relevance`, `maturity_level` are `null` when unclassified/unassigned — the file always has the key, with an explicit `null`, never an omitted key (matching FR-010's "exactly as currently stored").

### 2.2 Business Domain — `domains/<domain-id>.json`

```json
{
  "id": "domain-uuid",
  "name": "Underwriting",
  "scope_statement": "...",
  "classification": "core",
  "org_unit": "Insurance Operations",
  "risk_flags": [],
  "exported_at": "2026-08-05T00:00:00Z"
}
```

### 2.3 Value Stream — `value-streams/<value-stream-id>/value-stream.json`

```json
{
  "id": "vs-uuid",
  "name": "Order-to-Cash",
  "description": "...",
  "stakeholder": "VP Sales",
  "position": 0,
  "exported_at": "2026-08-05T00:00:00Z"
}
```

Does not list its own stage IDs inline — the stage files nested under this same value stream's directory (§2.4) already are that list; duplicating it here would be a second place to keep in sync for no reader benefit.

### 2.4 Value Stream Stage — `value-streams/<value-stream-id>/stages/<stage-id>.json`

```json
{
  "id": "stage-uuid",
  "value_stream_id": "vs-uuid",
  "name": "Quote",
  "description": "...",
  "position": 0,
  "linked_capability_ids": ["cap-uuid-1", "cap-uuid-2"],
  "exported_at": "2026-08-05T00:00:00Z"
}
```

`linked_capability_ids` is sorted (deterministic output, per the top-of-section requirement) and empty (`[]`), never omitted, when a stage has no linked capabilities.

## 3. Reconciliation algorithm (per cycle, per entity type)

1. Query the live, complete set of rows for the entity type from Postgres (reusing `adp.business.store`'s existing `list_*` functions — no new query logic duplicating what already exists).
2. For value stream stages specifically, additionally query `value_stream_stage_capabilities` and group by `stage_id` to build each stage's `linked_capability_ids`.
3. For each live row, serialize its target file content (§2) and compare against the current on-disk file's content, ignoring the `exported_at` field on both sides:
   - If the file doesn't exist, or its content (minus `exported_at`) differs → write it (with a fresh `exported_at`).
   - If it exists and matches → leave the file untouched (FR-009; **do not** even rewrite it just to bump `exported_at`).
4. List the IDs currently present as files in that entity type's output directory (scanning filenames, which are always the entity's own ID); for any ID not in the live set from step 1, delete that file (FR-004).
5. For value streams specifically: after reconciling stage files under a value stream's directory (steps 3–4 scoped to that value stream's `stages/` subdirectory), if the value stream itself was deleted, remove its entire directory (value-stream.json plus its stages/ subtree) in one step, rather than reconciling an empty stage set against a value-stream.json that's about to be deleted anyway.

## 4. State transitions

There is no entity lifecycle of its own here — this is a stateless-between-cycles projection. The only "state" is the filesystem itself (Decision 2), which transitions exactly as its source data does: a file is created when its entity is created (or first seen on the initial bootstrap cycle, FR-008), updated when the entity's relevant fields change, and deleted when the entity is deleted. No intermediate states, no queue, nothing to leak or get stuck.
