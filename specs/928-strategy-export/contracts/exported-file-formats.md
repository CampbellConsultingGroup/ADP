# Contract: Exported Strategy Domain File Formats (ADP-81p.3)

This feature has no HTTP endpoint — its external interface is the file tree itself, read directly off the filesystem by tools, AI agents, or humans with no platform access. This document is that contract: the guarantees a reader can rely on. It is the sibling of ADP-SPEC-044's and ADP-SPEC-045's own `exported-file-formats.md` contracts, extended to a third domain.

Root: `$ADP_BUSINESS_ARCH_EXPORT_ROOT/strategy/`

```text
strategy/
├── themes/
│   └── <theme-id>.json
├── objectives/
│   └── <objective-id>.json
└── initiatives/
    └── <initiative-id>.json
```

Plus one extension to ADP-SPEC-044's own tree (Clarification Q2 — no new root, no new file):

```text
business-architecture/
├── capabilities/<capability-id>.json          # gains: linked_designs
└── value-streams/<vs-id>/value-stream.json    # gains: linked_designs
```

## Guarantees

- **Filenames are always the entity's own internal ID**, never its display name — identical convention to ADP-SPEC-044/045.
- **Every file that should exist, exists; no file that shouldn't exist remains** (outside the bounded staleness window below) — identical guarantee to ADP-SPEC-044/045.
- **A file's content only ever reflects real data.** Nullable fields are always present as a key with an explicit JSON `null` when unset — never omitted. Every relationship array (`capability_ids`, `value_stream_ids`, `design_ids`, `application_ids`, `control_ids`, `depends_on_objective_ids`, `blocked_objective_ids`, `initiative_ids`, `objective_ids`, `control_mappings`, `linked_designs`) is present and `[]` — never omitted — when no relationship of that kind exists.
- **An objective's `status`/`status_reason` are the platform's own computed value** (Clarification Q1) — the same `compute_status()` result every existing API consumer already sees, derived from progress history + target, never the raw stored column alone.
- **An objective's `progress` array is its complete history**, sorted ascending by `as_of_date` — not a summary, not the most recent entry alone.
- **An initiative's `control_mappings[].compliance_status`/`.evidence_ref`/`.assessed_at` are always the live values**, read via the same mirror-table JOIN the live API uses — never a value captured at link-creation time, and never independently re-synced by this export (there is nothing to re-sync; it is read fresh every reconciliation cycle).
- **Numeric/decimal fields are JSON strings, never binary floats** (e.g. an objective's `target_value`/a progress entry's `actual_value`) — `Decimal`-precision throughout this platform, and the export preserves that, matching ADP-SPEC-045's own established convention.
- **Bounded staleness, not real-time** — identical guarantee to ADP-SPEC-044/045, same configured interval mechanism (reused, not reconfigured separately).
- **A file is only rewritten when its content actually changes** (ignoring `exported_at`) — identical to ADP-SPEC-044/045.
- **This domain has no sensitive-category exposure to document** — unlike ADP-SPEC-045's Application registry, Strategy has no `READ_STRATEGY_*` gate today (confirmed directly against the permission model), so unlike that contract, this one carries no residual-risk guarantee about bypassing an API-level redaction.
- **`objective_ids`/`initiative_ids` are reverse views of the same underlying link**, kept in sync by the same reconciliation cycle — both directions cannot drift from each other, the same guarantee ADP-SPEC-045's `initiative_links`/`members` pair already makes.
- **These files are not writable inputs.** Editing them by hand has no effect on the platform — Postgres remains the source of truth (ART-II); any hand-edit is silently overwritten (or removed) on the next reconciliation cycle.

## Non-guarantees (explicitly out of scope for this contract)

- No guarantee about file modification/creation OS-level timestamps beyond the in-content `exported_at` field.
- No guarantee of atomic visibility across multiple files in the same reconciliation cycle — identical non-guarantee to ADP-SPEC-044/045.
- No standalone file for `capability_design_links`/`value_stream_design_links` themselves — per Clarification Q2, that data lives on the capability's/value-stream's own file (ADP-SPEC-044's tree), not this one.
