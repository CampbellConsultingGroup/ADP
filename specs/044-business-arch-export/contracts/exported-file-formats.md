# Contract: Exported Business Architecture File Formats (ADP-SPEC-044 / ADP-81p.1)

This feature has no HTTP endpoint — its external interface is the file tree itself, read directly off the filesystem by tools, AI agents, or humans with no platform access. This document is that contract: the guarantees a reader can rely on.

Root: `$ADP_BUSINESS_ARCH_EXPORT_ROOT/business-architecture/`

```text
business-architecture/
├── capabilities/
│   └── <capability-id>.json
├── domains/
│   └── <domain-id>.json
└── value-streams/
    └── <value-stream-id>/
        ├── value-stream.json
        └── stages/
            └── <stage-id>.json
```

## Guarantees

- **Filenames are always the entity's own internal ID**, never its display name. IDs are stable across renames; a reader tracking a specific capability across its history should key on the filename (ID), not on the `name` field inside it.
- **Every file that should exist, exists; no file that shouldn't exist remains.** At any point in time (outside the bounded staleness window described below), the set of files under each subdirectory is in 1:1 correspondence with the live entities of that type. A missing file means that entity does not currently exist; there is no "tombstone" file for deletions.
- **A file's content only ever reflects real data.** Nullable fields (`domain_id`, `strategic_relevance`, `maturity_level` on a capability) are always present as a key, with an explicit JSON `null` when unclassified — never omitted, and never defaulted to a value that looks real.
- **Bounded staleness, not real-time.** A change made in the platform is reflected in these files within `ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS` (a configured interval, default documented in quickstart.md) — not instantly. A reader needing the absolute current state for something consequential should use the live API, not these files.
- **A file is only rewritten when its content actually changes** (ignoring its own `exported_at` timestamp field). A file's unchanged presence across many reconciliation cycles is not itself informative of anything; only its content and the fact that it exists are.
- **`value-streams/<id>/stages/<stage-id>.json`'s `linked_capability_ids`** is the authoritative list of which capabilities that stage invokes, sorted, and empty (`[]` — never omitted) when none are linked.
- **These files are not writable inputs.** Editing them by hand has no effect on the platform — Postgres remains the source of truth (ART-II); any hand-edit will be silently overwritten (or removed, if it doesn't correspond to a real entity) on the next reconciliation cycle.

## Non-guarantees (explicitly out of scope for this contract)

- No guarantee about file modification/creation OS-level timestamps beyond the in-content `exported_at` field — do not rely on filesystem `mtime`.
- No guarantee of atomic visibility *across* multiple files in the same reconciliation cycle — a reader polling the directory mid-cycle could see some files already updated and others not yet, for what was logically one batch of underlying changes. Individual files are never partially written (each file's own write is atomic), but the whole tree is not a single transaction.
- No links to entities outside this domain (applications, designs) — see spec.md's Assumptions for what's excluded and why.
