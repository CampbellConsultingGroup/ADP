# Feature Specification: Regulatory Framework Tags for Application Risk & Compliance

**Feature Branch**: `932-regulatory-framework-tags`
**Created**: 2026-10-07
**Status**: Draft
**Input**: User description: "ADP-bkg — regulatory_tags becomes a multi-select of real regulatory_frameworks ids (COMPLY-01), a lightweight 'this framework applies to this app' tag that sits alongside — not replaces — the existing per-control ControlMapping linkage on the Regulatory Compliance tab."

## Clarifications

### Session 2026-10-07

- Q: Should the framework picker offer every tracked regulatory framework regardless of its own lifecycle status (`in_force`/`amended`/`repealed`/`not_yet_applicable`), or should it filter by status? → A: Only `in_force` or `amended` frameworks are selectable; `repealed` and `not_yet_applicable` frameworks are hidden from the picker.
- Q: Can the same regulatory framework be tagged more than once on a single application? → A: No — each framework can be tagged on a given application at most once; this is an enforced uniqueness rule, not merely a UI convenience.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: today `regulatory_tags` is arbitrary free text with no relationship to any canonical record; this feature makes it a reference to the governed `RegulatoryFramework` records already tracked in the Compliance domain, so an application's regulatory exposure is derived from the single source of truth instead of a duplicated string.
- **ART-XI** — Traceability End to End: this feature exists specifically to repair a broken traceability gap — an application's regulatory tag currently cannot be traced to any real framework record at all.
- **ART-XIII** — Typed Contracts Everywhere: `regulatory_tags` changes from an unvalidated `list[str]` to a typed, validated list of real framework identifiers.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Application risk & compliance data, already a sensitive category gated by `READ_APPLICATION_RISK`/`WRITE_APPLICATION_RISK`; and the integrity of regulatory framework references used in compliance reporting and audits.

**Trust boundaries crossed**: Browser → API only (existing boundary). No new external integration and no new trust boundary is introduced.

**Abuse cases**:
- A user without `WRITE_APPLICATION_RISK` attempts to tag an application with a framework → blocked by the existing, unchanged permission gate on the risk record.
- A user tags an application with a framework id that does not exist (typo, stale client state, deleted framework) → the system rejects the write rather than silently persisting an unresolvable reference, since a dangling tag would misstate the application's actual regulatory exposure in compliance reporting.
- A regulatory framework is deleted from the Compliance registry while still tagged on one or more applications → without cleanup, those applications would display a broken/unresolvable tag indefinitely → the system removes the now-invalid reference automatically when the framework is deleted.

**Residual risk**: None beyond what the existing Application Risk sensitive-data category already accepts. This feature changes the shape and validity of data within an already-gated record; it introduces no new read/write surface, no new external consumer, and no new permission.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tag an application with real regulatory frameworks (Priority: P1)

An architect or risk owner reviewing an application's Risk & Compliance tab wants to record which regulations apply to it. Instead of typing free text that might not correspond to anything real, they pick from the actual list of regulatory frameworks already tracked in Compliance (e.g. GDPR, the EU AI Act, DORA).

**Why this priority**: This is the entire point of the feature — without it, the field remains ungoverned free text with no traceability value. It is the minimum slice that delivers the feature's value.

**Independent Test**: Open an application's Risk & Compliance tab, open the framework picker, select one or more frameworks from the governed list, save, reload the page, and confirm the same frameworks are still shown as selected.

**Acceptance Scenarios**:

1. **Given** an application with no regulatory framework tags, **When** a user with write access selects two frameworks from the picker and saves, **Then** both frameworks are persisted and shown as selected the next time the tab is opened.
2. **Given** an application already tagged with one framework, **When** a user removes that framework and adds a different one, **Then** only the newly selected framework remains tagged after saving.
3. **Given** a user without write access to the application's risk record, **When** they view the Risk & Compliance tab, **Then** they can see the tagged frameworks (if they have read access) but cannot modify the selection.

---

### User Story 2 - See which real regulation a tag refers to (Priority: P2)

A compliance or risk reviewer looking at an application's tagged frameworks wants to know, unambiguously, which specific regulation each tag means — not a string that could mean anything.

**Why this priority**: Builds directly on User Story 1; without it, a reviewer still cannot act on the tags with confidence even though they are now backed by real records.

**Independent Test**: View an application tagged with a known framework and confirm the framework's real name (and, where two frameworks share a name, its distinguishing details) is shown — not a raw identifier or free-text string.

**Acceptance Scenarios**:

1. **Given** an application tagged with a specific regulatory framework, **When** a reviewer opens the Risk & Compliance tab, **Then** the framework's real name is displayed (not an internal identifier).
2. **Given** two tracked frameworks that happen to share the same display name, **When** both are shown as tags (on the same or different applications), **Then** enough distinguishing detail (e.g. jurisdiction or version) is shown that a reviewer can tell them apart.

---

### User Story 3 - A deleted framework never leaves a broken tag behind (Priority: P3)

An administrator removes a regulatory framework from the Compliance registry (e.g. it was added by mistake, or a jurisdiction's regulation is retired). Any application that had tagged it should not be left showing a reference to something that no longer exists.

**Why this priority**: A correctness and data-integrity safeguard rather than a day-one usage flow; it matters, but no user is blocked by its absence while building the core experience.

**Independent Test**: Tag an application with a framework, delete that framework from the Compliance registry, then reopen the application's Risk & Compliance tab and confirm the removed framework no longer appears as a tag (and nothing is broken or unresolvable).

**Acceptance Scenarios**:

1. **Given** an application tagged with a framework, **When** an administrator deletes that framework from the Compliance registry, **Then** the tag is automatically removed from the application — no broken reference remains.

---

### Edge Cases

- What happens when the Compliance framework registry has zero frameworks tracked yet? The picker shows an empty, clearly-labeled state (e.g. "No regulatory frameworks have been added yet") rather than an error.
- What happens to an application's regulatory tags when the one framework it was tagged with is deleted, leaving it tagged with nothing? It reverts to having zero tags — the same as an application that was never tagged.
- What happens to applications that already have free-text regulatory tags recorded today (e.g. "SOX", "GDPR", "HIPAA" typed before this feature existed)? They are discarded outright (FR-006) — every application starts with zero regulatory framework tags under the new model.
- What happens when a user without read access to the application's risk record views the Risk & Compliance tab? They see the existing "no permission" state (unchanged) — the tagged frameworks are not exposed.
- What happens to an application already tagged with a framework that later transitions to `repealed` or `not_yet_applicable`? The existing tag is left in place as a historical record — FR-001's status filter only governs what is newly *selectable*, it does not retroactively remove a tag that was valid when it was made. Only an actual framework deletion triggers removal (FR-005).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Risk & Compliance view MUST let a user select zero or more regulatory frameworks from the governed list of frameworks already tracked in the Compliance domain, in place of the current free-text tag input. Only frameworks whose status is `in_force` or `amended` are offered for selection; `repealed` and `not_yet_applicable` frameworks are excluded from the picker.
- **FR-002**: The system MUST reject any attempt to save a framework selection that includes a framework identifier not present in the governed Compliance framework registry.
- **FR-003**: Each selected framework MUST be displayed using its real name, with enough additional detail (e.g. jurisdiction and/or version) to distinguish it from any other tracked framework sharing the same name.
- **FR-004**: Reading and writing an application's regulatory framework tags MUST continue to be governed by the existing read/write permissions on that application's risk & compliance record — no new permission is introduced, and no existing permission is loosened.
- **FR-005**: When a regulatory framework is deleted from the Compliance registry, the system MUST automatically remove that framework from every application that had it tagged, so no application is ever left displaying a reference to a framework that no longer exists.
- **FR-006**: The system MUST discard every application's pre-existing free-text regulatory tag value when this feature ships — no best-effort matching or legacy read-only display. Every application starts with zero regulatory framework tags under the new model; a person re-tags it from the governed list going forward if the framework still applies.
- **FR-007**: An application MUST be able to have zero regulatory framework tags, exactly as it can today.
- **FR-008**: This feature MUST NOT alter, replace, or remove the existing per-control Regulatory Compliance mappings shown on the application's separate "Regulatory Compliance" tab — the two mechanisms coexist.
- **FR-009**: The system MUST enforce that a given regulatory framework can be tagged on a given application at most once — a duplicate tag is structurally impossible, not merely discouraged by the UI.

### Key Entities *(include if feature involves data)*

- **Application Regulatory Framework Tag**: Records that one regulatory framework is understood to apply to one application. A lightweight "applies here" relationship — it carries no assessed compliance status of its own, and is distinct from (and does not replace) a Control Mapping's assessed `compliance_status`. At most one tag exists per (application, framework) pair (FR-009).
- **Regulatory Framework**: The existing governed record (name, jurisdiction, version, authority) already tracked in the Compliance domain. This feature references it; it does not duplicate or modify it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user tagging an application's applicable regulations selects from a list of real, named frameworks, with zero free-text typing required.
- **SC-002**: 100% of an application's displayed regulatory tags resolve to a currently-existing, named framework record — no raw or unresolvable tag text is ever shown.
- **SC-003**: Deleting a regulatory framework from the Compliance registry never leaves any application displaying a broken or unresolvable tag.
- **SC-004**: Reviewers evaluating an application's regulatory tags can always identify the specific regulation each tag refers to, eliminating the ambiguity of today's free-text tags.

## Assumptions

- Reading the list of available regulatory frameworks to populate the picker uses the existing, already-open framework listing in Compliance; no new permission is introduced for that read.
- Reading and writing an application's regulatory framework tags continues to require the existing application-risk read/write permissions unchanged (FR-004) — this feature does not introduce a dependency on holding separate Compliance-write access.
- A reverse-lookup view (which applications are tagged with a given framework, surfaced from the framework's own screen) is valuable but out of scope for this pass, consistent with how a comparable recent linkage feature (theme↔framework tagging) deferred its own reverse-lookup UI as a separate follow-on. It can be filed as a follow-on if wanted.
- Deleting a regulatory framework automatically removes it from any application's tags (FR-005), matching the cascade-delete behavior already established by every other Compliance linkage in this codebase.
- Any existing system that reads an application's regulatory tags in their current free-text shape (e.g. the application architecture file export) will be updated to reflect the new shape so it stays in sync; this is an implementation detail, not a new requirement surface for users.
- This feature does not change the existing "Regulatory Compliance" tab's per-control Control Mapping assessed-status mechanism in any way (FR-008).
