# Feature Specification: Continuous Application Registry Export to Versioned Files

**Feature Branch**: `045-application-export`
**Created**: 2026-08-05
**Status**: Draft
**Input**: User description: "ADP-81p.2 — Continuous export of the Application registry (applications, technical capabilities, and their relationships/extension records) from Postgres to versioned, git-tracked JSON files, extending the ADP-SPEC-044 continuous-export pattern to a second domain"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: Postgres remains authoritative; exported files are a generated, read-only *projection*, identical in spirit to ADP-SPEC-044.
- **ART-III** — Everything is Machine-Readable: closes the same gap ADP-SPEC-044 closed for Business Architecture, now for the Application registry — application inventory, technical capabilities, and their relationships currently live only in Postgres rows.
- **ART-V** — Security by Design: unlike ADP-SPEC-044's domain, this one has real sensitivity gating today (`READ_APPLICATION_{RISK,COST,GOVERNANCE}`) enforced at the API layer. Per Clarification Q1, this feature deliberately includes those categories in the export anyway (a background process has no per-viewer permission context to apply the gate selectively), which means the exported file tree becomes an access-control-free copy of data the live API otherwise gates — an explicitly accepted residual risk, not an oversight (see Threat Model).
- **ART-VI** — Observability is Not Optional: same staleness/failure-must-be-observable requirement as ADP-SPEC-044.
- **ART-IX** — Provenance and Auditability: this feature exports already-committed data; it introduces no new consequential mutation of its own.

ART-VIII (Human-in-the-Loop for Consequence) does not require a new confirmation gate — this feature only creates a derived, read-only file projection of already-committed data. ART-VII (Grounded AI Only) does not apply — no AI-generated content is involved.

## Clarifications

### Session 2026-08-05

- Q: Should the exported files include the three sensitive extension categories (risk & compliance, cost/TCO, ownership & governance) that the live API gates behind `READ_APPLICATION_{RISK,COST,GOVERNANCE}`, given a background export process has no requesting user to check those permissions against? → **A: Include all three, unredacted.** The exported files become a full mirror of an application's Postgres-stored data, maximizing usefulness to AI/tooling readers, at the explicit cost of the exported file tree bypassing the API's own sensitivity gate — anyone with filesystem or git-history access to the export sees this data regardless of platform role. Accepted as a residual risk; see below.
- Q: Should this increment cover the full breadth of the Application registry domain in one shot, or a narrower "core only" slice deferring most extension tables/relationships to a later increment? → **A: Full breadth in this increment** — every entity, relationship, and (per the answer above) every extension category, mirroring how ADP-SPEC-044 covered its entire domain in one increment rather than splitting by user story. The only exclusion is the application-to-design link (FR-014), already covered by ADP-SPEC-011's separate export mechanism.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: application inventory data (names, ownership, lifecycle state), technical capability taxonomy, and — per Clarification Q1 above — application risk posture (security posture, vulnerability status, data classification, regulatory tags), cost/TCO figures, and governance/contract data (contract terms, renewal dates, business/IT owner names, decision rights).

**Trust boundaries crossed**: a system-internal boundary (Postgres → filesystem, potentially → git history), the same shape as ADP-SPEC-044 — no new browser-facing surface.

**Abuse cases**:
- An application, technical capability, or initiative with a maliciously or accidentally crafted name is used to construct a file path → mitigated identically to ADP-SPEC-044: file/directory names are derived from existing internal IDs, never from user-supplied free-text.
- The sync mechanism falls silently behind or fails, and an AI tool or human trusts stale exported files as current → mitigated identically to ADP-SPEC-044: sync failures are a first-class, logged/observable event.
- **The exported file tree carries data the live API deliberately gates behind `READ_APPLICATION_RISK`/`READ_APPLICATION_COST`/`READ_APPLICATION_GOVERNANCE`, with no equivalent gate of its own.** Anyone with filesystem or git-history access to the export location — regardless of platform role or API permissions — sees security posture, vulnerability status, contract terms, and cost data that a `Reviewer`-level API caller (for example) cannot read through the platform itself. This is an explicit, chosen trade-off (Clarification Q1), not an oversight, but it means the operator of the exported location (and any git remote it's pushed to) is now the sole access-control boundary for this data — the same protection the API's permission gate previously provided.

**Residual risk**: same class of accepted risk as ADP-SPEC-044 for the non-sensitive categories. For the sensitive categories, the residual risk is real and explicitly accepted: the exported file tree must be treated by its operator as equivalently sensitive to the live API's gated endpoints (e.g., a private git remote/repository, restrictive filesystem permissions on `export_root`) — this feature does not implement any new access-control mechanism for the files themselves, and treating the export location as public or broadly-readable would materially widen exposure of data the platform otherwise protects.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An AI tool or teammate reads current application architecture straight from the repo (Priority: P1)

Someone (an AI coding/analysis tool, or a teammate without direct database access) wants to understand the organization's current application inventory, technical capability taxonomy, and how applications relate to business capabilities, value streams, business domains, other applications, and transformation initiatives. Instead of needing API/database access, they open the versioned files already checked into the repository and find application registry data that reflects what's actually in the platform today.

**Why this priority**: this is the entire reason this feature exists — the same "only in Postgres, not in git" gap ADP-SPEC-044 closed for Business Architecture, now for the Application registry (the parent epic's largest remaining uncovered domain).

**Independent Test**: can be fully tested by creating/editing applications, technical capabilities, and their relationships through the existing platform, then confirming the corresponding files exist, are well-formed, and contain the current data.

**Acceptance Scenarios**:

1. **Given** an application and a technical capability exist in the platform, **When** someone looks at the exported files, **Then** each one appears in the export with its current identity, classification, and lifecycle data.
2. **Given** an application's lifecycle status or rationalization scores change through the existing platform, **When** the next export sync runs, **Then** the exported file for that application reflects the new values, not the old ones.
3. **Given** an application is linked to a business capability, a technical capability, a value stream stage, or another application, **When** someone looks at the exported files, **Then** those relationships are visible without needing database access.
4. **Given** an application has a recorded risk & compliance record, cost/TCO record, or ownership & governance record, **When** someone looks at the exported files, **Then** that data is present in the export exactly as stored (Clarification Q1) — this feature does not filter it by any notion of the reader's platform permissions, since the export process has none to apply.

---

### User Story 2 - A reviewer sees exactly what changed in the application portfolio as a readable diff (Priority: P2)

An architect or reviewer wants to know what changed in the application portfolio over some period (e.g., "which applications were reclassified as Eliminate last sprint?"). They look at the version history of the exported files and see a clear, human-readable diff of exactly what changed, when.

**Why this priority**: the same second-order "reviewable history" benefit ADP-SPEC-044 established; only has value once Story 1's export mechanism exists and is trustworthy.

**Independent Test**: can be fully tested by making an application registry change, letting the export sync run, and confirming the resulting file change is a small, targeted diff clearly attributable to that specific change.

**Acceptance Scenarios**:

1. **Given** a single application's time classification is changed, **When** the export sync runs, **Then** the resulting file change is limited to that application's data — unrelated applications' exported content is untouched.
2. **Given** an application is deleted, **When** the export sync runs, **Then** its exported file (and any relationship record whose existence depends on it) is removed rather than left behind as stale, orphaned content.

---

### Edge Cases

- What happens when an application, technical capability, or transformation initiative is deleted? Its corresponding exported file MUST be removed on the next sync, along with any relationship record whose existence depends on it (e.g., an application–capability link where the application no longer exists).
- What happens when the export sync itself fails partway? Same as ADP-SPEC-044: the failure MUST be surfaced, and MUST NOT leave a partially-written, corrupted file in place of a previously-good one.
- What happens on the very first run, before any export has ever happened? The system MUST perform a full initial export of everything that currently exists, not require a separate "bootstrap" action.
- What happens if an application has no relationships to any other in-scope entity? It MUST still be exported with its own file; the absence of relationship data is not an error condition.
- What happens if an application has no risk, cost, or governance record at all (never populated)? Its exported file MUST reflect that absence explicitly (e.g., as explicit nulls/defaults matching the platform's own "unset" representation), not omit the fields entirely or fabricate values.
- What happens if the same underlying data is exported again with no actual changes since the last sync? Same as ADP-SPEC-044: the system SHOULD NOT rewrite files whose content is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST export every application and every technical capability to a versioned file representation.
- **FR-002**: System MUST keep the exported files up to date via a debounced/scheduled background sync (not synchronous with the write that changes the underlying data), reusing the same sync mechanism ADP-SPEC-044 established.
- **FR-003**: System MUST write one file per individual application and per individual technical capability instance (not one aggregate file per entity type) — so a change to one entity produces a diff scoped to that entity alone.
- **FR-004**: System MUST remove the exported file representation for any application or technical capability that has been deleted from the platform.
- **FR-005**: System MUST NOT modify the underlying application or technical capability data as a side effect of exporting it — this is a read-only export.
- **FR-006**: System MUST log an observable failure event when an export sync attempt does not complete successfully, rather than failing silently.
- **FR-007**: System MUST NOT leave a partially-written or corrupted exported file in place of a previously-valid one if an export attempt fails partway through.
- **FR-008**: System MUST perform a complete export of all existing applications, technical capabilities, and their in-scope relationships on first run, without requiring a separate manual bootstrap step.
- **FR-009**: System MUST NOT rewrite an exported file whose underlying data has not changed since its last successful export.
- **FR-010**: An application's exported file representation MUST include its identity, name, classification fields (time classification, R-strategy, pace layer, lifecycle status, hosting model, architecture pattern), rationalization/technical-fit scores (business value, business criticality, health score), ownership fields (owning business unit, business owner, technical owner), tech-debt flags, and quality & performance signals (uptime, incidents, satisfaction score, ticket volume).
- **FR-011**: An application's exported file representation MUST include which business capabilities it is linked to (with fit score), which technical capabilities it uses or provides, which value stream stages it participates in, and which business domain integrations it has — mirroring ADP-SPEC-044's FR-011 precedent of including relationship data between two entities that are both in scope.
- **FR-012**: System MUST export application-to-application integration records (source, target, integration type, description) as their own versioned file representation.
- **FR-013**: System MUST export transformation initiatives, and which applications are linked to each with their planned disposition, as their own versioned file representation.
- **FR-014**: System MUST NOT include an application's linked design IDs in the exported files — that relationship is already covered by ADP-SPEC-011's separate, existing design-export mechanism, mirroring ADP-SPEC-044's precedent of excluding links to out-of-scope entities.
- **FR-015**: An application's exported file representation MUST include its risk & compliance record in full (security posture, vulnerability status, data classification, regulatory tags, DR/BC status, end-of-life and end-of-support dates), per Clarification Q1 — unredacted, with no per-viewer filtering.
- **FR-016**: An application's exported file representation MUST include its cost/TCO record in full (currency, horizon, all cost buckets), per Clarification Q1 — unredacted, with no per-viewer filtering.
- **FR-017**: An application's exported file representation MUST include its ownership & governance record in full (contract terms, renewal date, SLA, business sponsor, IT owner, decision rights), per Clarification Q1 — unredacted, with no per-viewer filtering.
- **FR-018**: When an application has no recorded risk, cost, or governance record, its exported file MUST represent that absence with explicit nulls/defaults matching the platform's own "unset" representation for that record — not by omitting the fields or fabricating values.

### Key Entities *(include if feature involves data)*

- **Application, Technical Capability** *(existing entities, not introduced by this feature)*: the platform's existing typed application registry data (ADP-SPEC-036). This feature defines no new entity or field for either — it produces a file-based, versioned representation, kept in sync with live Postgres state.
- **Transformation Initiative** *(existing entity)*: a roadmap/decommission-tracking entity (ADP-SPEC-038 US6), exported as its own file per instance, carrying its linked applications and their planned dispositions.
- **Application relationship records** *(existing, not new)*: application–business-capability links (with fit score), application–technical-capability links (with usage type), application–value-stream-stage links, application–business-domain integrations, and application–application integrations.
- **Application Risk, Application Cost, Application Governance** *(existing sensitive extension records, ADP-SPEC-038 US3/US4/US7)*: included in the export in full per Clarification Q1 — not new entities, no new fields; the exported representation mirrors what the platform stores today, including for applications with no record populated (FR-018).
- **Export Sync State** *(new, minimal)*: same internal change-detection/deletion-tracking concept ADP-SPEC-044 introduced, extended to cover this domain's additional entity types — exact shape is a planning-phase decision.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Someone with no database or API access can determine the platform's complete, current application inventory, technical capability taxonomy, their relationships to each other and to business capabilities/value streams/domains, and — per Clarification Q1 — their risk, cost, and governance data, entirely from the exported files.
- **SC-002**: A change made to a single application, technical capability, transformation initiative, or relationship is reflected in its corresponding exported file within a bounded, predictable delay (matching ADP-SPEC-044's established delay), with zero unrelated files changed as a side effect.
- **SC-003**: 100% of currently-existing applications, technical capabilities, transformation initiatives, and in-scope relationships have a corresponding, up-to-date exported file at all times (excluding the bounded sync delay in SC-002) — zero orphaned files for deleted entities, zero missing files for existing entities.
- **SC-004**: When an export sync attempt fails, that failure is discoverable in logs within the same operational visibility the platform already provides (matching ADP-SPEC-044's SC-004).

## Assumptions

- This feature does not itself commit the exported files to git or push them anywhere — identical assumption to ADP-SPEC-044. Because this export now includes data equivalently sensitive to the API's gated endpoints (Clarification Q1), the operator is responsible for applying access control to wherever these files land (e.g., a private git remote, restrictive filesystem permissions on `export_root`) — this feature implements no access-control mechanism of its own for the exported files, and that gap is an accepted, explicitly-documented residual risk (see Threat Model), not an oversight.
- The export writes to the same configured filesystem location concept (`export_root`) ADP-SPEC-044 already established, most likely as sibling subdirectories under the same root rather than a second, separately-configured destination.
- Reading application/technical-capability data (including the sensitive categories) is permission-gated today at the API level; this feature's export process itself has no per-viewer permission context and, per Clarification Q1, exports everything unfiltered rather than attempting partial/best-effort gating.
- The bounded sync delay referenced in SC-002 is expected to match whatever cadence ADP-SPEC-044 established for its own background sync, reusing the same underlying mechanism rather than introducing a second, differently-tuned one.
