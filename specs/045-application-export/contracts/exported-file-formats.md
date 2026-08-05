# Contract: Exported Application Registry File Formats (ADP-SPEC-045 / ADP-81p.2)

This feature has no HTTP endpoint — its external interface is the file tree itself, read directly off the filesystem by tools, AI agents, or humans with no platform access. This document is that contract: the guarantees a reader can rely on. It is the sibling of ADP-SPEC-044's own `exported-file-formats.md` contract, extended to a second domain.

Root: `$ADP_BUSINESS_ARCH_EXPORT_ROOT/applications/`

```text
applications/
├── applications/
│   └── <app-id>.json
├── technical-capabilities/
│   └── <tech-cap-id>.json
├── transformation-initiatives/
│   └── <initiative-id>.json
└── integrations/
    └── <integration-id>.json
```

## Guarantees

- **Filenames are always the entity's own internal ID**, never its display name — identical convention to ADP-SPEC-044.
- **Every file that should exist, exists; no file that shouldn't exist remains** (outside the bounded staleness window below) — identical guarantee to ADP-SPEC-044.
- **A file's content only ever reflects real data.** Nullable fields are always present as a key with an explicit JSON `null` when unset — never omitted, never defaulted to a value that looks real. This includes an application's `risk`/`cost`/`governance`/`quality` sub-objects: an application with no risk record ever recorded still has a `risk` key, with every field inside it `null` (or, for `cost`, every bucket `"0"`) — the absence of a database row is represented as an all-unset record, not as a missing `risk` key.
- **This export includes data the live API gates behind `READ_APPLICATION_RISK`/`READ_APPLICATION_COST`/`READ_APPLICATION_GOVERNANCE`, by explicit decision (spec.md Clarification Q1) — unlike ADP-SPEC-044's domain, which has no sensitive categories at all.** A reader with filesystem or git-history access to this export tree sees this data regardless of what platform role or API permissions they hold. The operator of the export destination is responsible for applying access control equivalent to what the live API enforces (see spec.md Threat Model / Assumptions) — this contract does not include any access-control guarantee of its own.
- **Cost amounts are JSON strings, never binary floats** (e.g. `"2000.50"`, not `2000.5` as a JSON number) — money is `Decimal`-precision throughout this platform and the export preserves that.
- **Bounded staleness, not real-time** — identical guarantee to ADP-SPEC-044, same configured interval mechanism (reused, not reconfigured separately).
- **A file is only rewritten when its content actually changes** (ignoring `exported_at`) — identical to ADP-SPEC-044.
- **An application's relationship arrays** (`linked_business_capabilities`, `linked_technical_capabilities`, `linked_value_stream_stages`, `domain_integrations`, `initiative_links`) are the authoritative list of that application's outbound relationships, and empty (`[]`) — never omitted — when none exist.
- **A transformation initiative's `members`** is the reverse view of the same link data embedded in each linked application's own `initiative_links` — both directions are kept in sync by the same reconciliation cycle; they are not independently maintained and cannot drift from each other.
- **`applications/<app-id>.json`'s `linked_business_capabilities[].capability_id`** refers to a file in ADP-SPEC-044's own `business-architecture/capabilities/` tree — this export does not duplicate that entity's own data (name only, for readability, is embedded as `capability_name`), consistent with the platform's ART-II single-source-of-truth principle applied to the exported file tree itself.
- **These files are not writable inputs.** Editing them by hand has no effect on the platform — Postgres remains the source of truth (ART-II); any hand-edit is silently overwritten (or removed) on the next reconciliation cycle.

## Non-guarantees (explicitly out of scope for this contract)

- No guarantee about file modification/creation OS-level timestamps beyond the in-content `exported_at` field.
- No guarantee of atomic visibility across multiple files in the same reconciliation cycle — identical non-guarantee to ADP-SPEC-044.
- No link to an application's designs (`application_design_links`) — already covered by ADP-SPEC-011's separate export mechanism (spec.md FR-014).
- No access-control mechanism for the sensitive data this export includes (see Guarantees above) — that responsibility sits entirely with whoever operates the export destination, not with this feature.
