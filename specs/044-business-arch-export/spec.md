# Feature Specification: Continuous Business Architecture Export to Versioned Files

**Feature Branch**: `044-business-arch-export`
**Created**: 2026-08-05
**Status**: Draft
**Input**: User description: "ADP-81p.1 — Continuous export of Business Architecture data (capabilities, value streams, domains) from Postgres to versioned, git-tracked JSON files, extending the existing ADP-SPEC-011 export pattern beyond one-design-at-a-time"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: Postgres remains authoritative; the exported files are a generated, read-only *projection*, exactly like how `architecture-description.schema.json` is generated from `models.py` rather than hand-authored. Nothing in this feature makes the exported files a second place to author business architecture data.
- **ART-III** — Everything is Machine-Readable: this feature exists specifically to close a gap against this article — business capability/value stream/domain data currently lives only in Postgres rows, unreadable by an AI or tool without direct database access; this feature makes it available as versioned, diffable files instead.
- **ART-V** — Security by Design: this feature writes business architecture data (capability names, hierarchy, strategic classifications) to the filesystem continuously and automatically, with no per-write human confirmation gate — a materially different exposure shape than the existing one-at-a-time, human-confirmed design export (ADP-SPEC-011). The threat model below is central, not incidental.
- **ART-VI** — Observability is Not Optional: a sync mechanism that can silently fall behind or fail (leaving the exported files stale and actively misleading) must have its failures surfaced, not swallowed.
- **ART-IX** — Provenance and Auditability: this feature does not itself introduce a new consequential mutation (it exports data that already went through its own write path and, where applicable, its own audit trail) — see Assumptions for how this differs from ADP-SPEC-011's own per-export audit entry.

ART-VIII (Human-in-the-Loop for Consequence) does **not** require a new confirmation gate here: the underlying business capability/value stream/domain writes this feature exports already went through whatever human/system confirmation their own write paths require (or don't — most business architecture writes today are not gated). This feature only creates a derived, read-only file projection of already-committed data; it is not itself a new consequential action a human takes. ART-VII (Grounded AI Only) does not apply — no AI-generated content is involved.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: business capability, value stream, and business domain data (names, hierarchy, strategic classifications) — already readable via the existing API by any authenticated role, but this feature additionally places it on the filesystem (and, once committed, in git history) continuously and automatically, without the per-export human confirmation step the existing design-export feature (ADP-SPEC-011) has.

**Trust boundaries crossed**: this is a new system-internal boundary (Postgres → filesystem, potentially → git history), not a new user-facing one — there is no new browser-facing surface.

**Abuse cases**:
- A capability, value stream, or domain with a maliciously or accidentally crafted name (special characters, path-traversal sequences) is used to construct a file path → mitigated by deriving file/directory names from the entities' existing internal IDs (already-validated UUIDs), never from user-supplied free-text names.
- The sync mechanism falls silently behind or fails, and an AI tool or human trusts the exported files as current when they are stale → mitigated by treating sync failures as a first-class, logged/observable event (ART-VI) rather than a silent no-op, and by documenting clearly (in the generated files themselves and in this spec) that Postgres remains the interactive source of truth — the exported files are a best-effort, eventually-consistent projection, not to be relied on for anything consequential without cross-checking the live system.
- Scope creep: this feature is explicitly limited to business capabilities, value streams, and business domains — it does NOT cover the application registry, which includes sensitive categories (risk, cost, governance data) gated behind their own dedicated read permissions (`READ_APPLICATION_{RISK,COST,GOVERNANCE}`). If this export pattern is later extended to applications (a separate future increment per the parent epic, ADP-81p), that extension MUST re-examine whether the same "export everything automatically" approach is appropriate for those sensitive categories, or whether they need to be excluded/gated in the exported files too. This spec does not answer that question because it is out of scope for this increment.

**Residual risk**: this is the same class of risk the platform already accepts for one-at-a-time design export (ADP-SPEC-011) — business architecture data leaving the database and landing in files/git — now made continuous and automatic rather than manually triggered per item. Accepted because Postgres remains authoritative, the exported data itself is not in a sensitive category, and the export failure/staleness case is made observable rather than silent.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An AI tool or teammate reads current business architecture straight from the repo (Priority: P1)

Someone (an AI coding/analysis tool, or a teammate without direct database access) wants to understand the organization's current business capabilities, value streams, and domains. Instead of needing API/database access, they open the versioned files already checked into the repository and find business architecture data that reflects what's actually in the platform today.

**Why this priority**: this is the entire reason this feature exists — closing the "only in Postgres, not in git, not directly readable without DB access" gap the parent epic (ADP-81p) identifies. Nothing else in this feature has value without this working.

**Independent Test**: can be fully tested by creating/editing business capabilities, value streams, and domains through the existing platform, then confirming the corresponding files exist, are well-formed, and contain the current data.

**Acceptance Scenarios**:

1. **Given** a business capability, value stream, and business domain exist in the platform, **When** someone looks at the exported files, **Then** each one appears in the export with its current name, hierarchy position, and classification data.
2. **Given** a business capability's classification (e.g., maturity level) is changed through the existing platform, **When** the next export sync runs, **Then** the exported file for that capability reflects the new value, not the old one.
3. **Given** the exported files, **When** someone reads them without any platform/database access at all, **Then** they can understand the full current business capability hierarchy, value stream structure, and domain assignments from the files alone.

---

### User Story 2 - A reviewer sees exactly what changed in business architecture as a readable diff (Priority: P2)

An architect or reviewer wants to know what changed in the organization's business architecture over some period (e.g., "what capabilities were reclassified last sprint?"). They look at the version history of the exported files and see a clear, human-readable diff of exactly what changed, when.

**Why this priority**: this is the second-order benefit of "files in git" over "rows in a database" — reviewable history — but it only has value once Story 1's export mechanism exists and is trustworthy.

**Independent Test**: can be fully tested by making a business architecture change, letting the export sync run, and confirming the resulting file change is a small, targeted diff clearly attributable to that specific change (not a wholesale rewrite of unrelated content).

**Acceptance Scenarios**:

1. **Given** a single business capability's maturity level is changed, **When** the export sync runs, **Then** the resulting file change is limited to that capability's data — unrelated capabilities' exported content is untouched.
2. **Given** a business capability is deleted, **When** the export sync runs, **Then** its exported file is removed rather than left behind as stale, orphaned content.

---

### Edge Cases

- What happens when a business capability, value stream, or domain is deleted? Its corresponding exported file MUST be removed on the next sync, not left behind — an orphaned file describing a since-deleted entity is exactly the kind of "actively misleading" staleness this feature exists to avoid.
- What happens when the export sync itself fails partway (e.g., disk full, filesystem permission error)? The failure MUST be surfaced (logged, observable) rather than silently swallowed, and MUST NOT leave a partially-written, corrupted file in place of a previously-good one.
- What happens on the very first run, before any export has ever happened (no existing exported files yet)? The system MUST perform a full initial export of everything that currently exists, not require a separate "bootstrap" action.
- What happens if two changes to different capabilities happen in rapid succession? Both changes MUST eventually be reflected in the export; the mechanism MUST NOT lose one change while processing the other.
- What happens if the same underlying data is exported again with no actual changes since the last sync? The system SHOULD NOT rewrite files whose content is unchanged, to avoid manufacturing noise in the file history for anyone (or anything) watching for real changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST export every business capability, value stream, value stream stage, and business domain to a versioned file representation.
- **FR-002**: System MUST keep the exported files up to date via a debounced/scheduled background sync (not synchronous with the write that changes the underlying data) — the write path incurs no added latency or coupling to the export mechanism, and a bounded staleness window (per SC-002) is explicitly acceptable.
- **FR-003**: System MUST write one file per individual business capability, value stream, value stream stage, and business domain instance (not one aggregate file per entity type) — so that a change to one entity produces a diff scoped to that entity alone, and a deleted entity's file can be removed independently (FR-004) without touching any other entity's exported content.
- **FR-004**: System MUST remove the exported file representation for any business capability, value stream, value stream stage, or business domain that has been deleted from the platform.
- **FR-005**: System MUST NOT modify the underlying business capability/value stream/domain data as a side effect of exporting it — this is a read-only export.
- **FR-006**: System MUST log an observable failure event when an export sync attempt does not complete successfully, rather than failing silently.
- **FR-007**: System MUST NOT leave a partially-written or corrupted exported file in place of a previously-valid one if an export attempt fails partway through.
- **FR-008**: System MUST perform a complete export of all existing business capabilities, value streams, value stream stages, and business domains on first run, without requiring a separate manual bootstrap step.
- **FR-009**: System MUST NOT rewrite an exported file whose underlying data has not changed since its last successful export.
- **FR-010**: The exported file representation MUST include, at minimum, each entity's identity, name, hierarchy position (for capabilities: level and parent), and existing classification fields (strategic relevance, maturity level, domain assignment) exactly as currently stored.
- **FR-011**: A value stream stage's exported file representation MUST include which business capabilities are linked to that stage — omitting this would leave the value-stream export nearly meaningless, since "which capabilities are invoked at each stage" is the core fact a value stream exists to capture (this is the one piece of ADP-SPEC-034/035's cross-entity link data that stays in scope here, precisely because both entities it connects — a stage and a capability — are themselves already in scope; links to entities that remain out of scope, e.g. a capability's linked designs, are not included by this requirement).

### Key Entities *(include if feature involves data)*

- **Business Capability, Value Stream, Value Stream Stage, Business Domain** *(existing entities, not introduced by this feature)*: the platform's existing typed business architecture data (ADP-SPEC-033/034/035). This feature defines no new entity or field — it produces a file-based, versioned *representation* of these existing entities for external readability, kept in sync with their live state in Postgres. A value stream stage's representation additionally carries the IDs of its linked business capabilities (FR-011).
- **Export Sync State** *(new, minimal)*: whatever this feature needs to internally track to know an entity's data hasn't changed since its last successful export (FR-009) and to detect deletions (FR-004) — its exact shape is an implementation decision for the planning phase, not specified here.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Someone with no database or API access can determine the platform's complete, current business capability hierarchy, value stream structure, and domain assignments entirely from the exported files.
- **SC-002**: A change made to a single business capability, value stream, or domain is reflected in its corresponding exported file within a bounded, predictable delay (defined during planning), with zero unrelated files changed as a side effect.
- **SC-003**: 100% of currently-existing business capabilities, value streams, value stream stages, and business domains have a corresponding, up-to-date exported file at all times (excluding the bounded sync delay in SC-002) — zero orphaned files for deleted entities, zero missing files for existing entities.
- **SC-004**: When an export sync attempt fails, that failure is discoverable (e.g., in logs) within the same operational visibility the platform already provides for its other background/automated processes — never silent.

## Assumptions

- **This feature does not itself commit the exported files to git or push them anywhere.** It keeps a directory of files up to date; committing/pushing that directory is an external, later concern (a scheduled job, a manual step, or a follow-up increment) — mirroring the exact precedent already established by ADP-SPEC-011's own design export, which writes files to a configured directory and does not run git commands itself. Automating git commit/push (and the credential-handling and merge-conflict questions that come with running git from the live application process) is explicitly out of scope for this increment.
- The export writes to the same general class of configured filesystem location (`export_root`) that ADP-SPEC-011's design export already uses, rather than introducing a second, differently-configured destination concept.
- This increment covers exactly the entities in ADP-SPEC-033/035 (business capabilities, value streams, value stream stages, business domains) plus the one ADP-SPEC-034/035 relationship that connects two in-scope entities to each other (which capabilities a value stream stage links to, FR-011). It explicitly excludes ADP-SPEC-034's *other* links (`capability_design_links`, `value_stream_design_links`) — those connect a business architecture entity to a design, and designs already have their own separate export mechanism (ADP-SPEC-011); it also excludes the application registry (ADP-SPEC-036/038) and any other domain entirely. Each of those is a separate future increment under the parent epic (ADP-81p) — see Threat Model's scope-creep note regarding sensitive application data categories.
- No new user-facing screen or control is introduced by this feature — there is no "click to export" action for business architecture (unlike ADP-SPEC-011's manual, confirmation-gated design export); the sync is automatic and requires no human trigger, consistent with the parent epic's "continuous" framing.
- Reading business capability/value stream/domain data is not permission-gated today; this feature does not change that and introduces no new read permission.
- The bounded sync delay referenced in SC-002 is expected to be on the order of seconds to low minutes, not hours — the exact figure is a planning-phase decision informed by the trigger mechanism chosen in FR-002.
