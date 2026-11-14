# Feature Specification: EA Pattern Registry, Lifecycle & Patterns Screen (PATTERN-02 + PATTERN-04 part)

**Feature Branch**: `935-pattern-registry`
**Created**: 2026-11-14
**Status**: Draft
**Input**: User description: "ADP-mmm.2. Spec 2 of 4 in the EA Patterns-as-Code epic (ADP-mmm): pattern registry with versions and lifecycle, YAML import/export, knowledge-base projection, structure/catalog/traceability views, and the first Patterns UI."

## Background and Resolved Decisions

Spec 934 (merged in PR #134) delivered `adp.patterns`, a pure library: a typed pattern definition, a hardened YAML parser, validation rules and a canonical form with a stable digest. Nothing in it is persisted or visible to a user.

This spec makes patterns **governed artifacts inside ADP**:
- versioned, and immutable once proposed;
- with exactly one `current` version per pattern;
- imported and exported as YAML;
- visible in the knowledge base that ADP's AI agents already read;
- rendered as diagrams;
- authored and governed from a new Patterns screen.

It implements `docs/PATTERN-02-registry-and-lifecycle.md`, plus the structure, catalog and traceability views from `docs/PATTERN-04-mermaid-views.md`, as amended by the addendum in `docs/PATTERN-00-bundle-overview.md`. Evaluating patterns against the estate (adoptions, conformance, transition progress) is spec 936. CALM export is spec 937.

Epic decisions confirmed by the user on 2026-11-14. These are inputs, not open questions:
1. The ADP database is canonical. YAML comes in through the API and goes out through the existing export tree.
2. Each pattern family is projected into the knowledge base as one item.
3. Each spec ships its own UI.

Ground-truth corrections to `docs/PATTERN-02`/`04`, checked against the code at migration head `043`. Addendum items G7–G11 and G14 apply; these are the ones specific to this spec:

| # | Bundle says / assumes | Reality | This spec |
|---|---|---|---|
| GT-1 | Permissions v1.8.0 → 1.9.0, `PATTERN_WRITE`/`PATTERN_GOVERN` | `PERMISSIONS_VERSION` is `1.10.0` (`src/adp/authz/permissions.py:70`); actions are named verb-first | v1.10.0 → **1.11.0**, `WRITE_PATTERN` and `GOVERN_PATTERN` |
| GT-2 | `POST /render` is a "read-only allowlist entry" | No such allowlist exists. Every non-GET route maps to an action (`src/adp/authz/enforcement.py:40`) | Dry-run validate/render routes are mapped explicitly to `WRITE_PATTERN` |
| GT-3 | Writes produce "audit entries" | `audit_entries` is design-scoped. Domain packages log actor-attributed lines (`src/adp/agentic/router.py:187`) | Structured log lines, plus a persisted **lifecycle history** (needed for the confirmation decision below) |
| GT-4 | `ea_pattern_control_link` join table | `control_pattern_mapping` (migration 033) already maps controls to knowledge items, but accepts only kind `pattern` (`src/adp/compliance/store.py:794`) | No new control table. Controls reach patterns through the knowledge projection, and the mapping is widened to also accept `reference_architecture` (Clarification Q2) |
| GT-5 | Knowledge projection gives "chat retrieval for free" | Chat retrieval reads only the `adp.search` index, never `knowledge_items` (`src/adp/chat/retrieval.py:3-5`). The recommendation engine (`src/adp/recommendation/steps.py:203`) and the pattern-fit critic (`src/adp/validation/critics.py:262`) **do** read `knowledge_items` | The projection reaches the recommendation and validation agents and the Knowledge screen. Chat/global-search indexing of patterns is a follow-on |
| GT-6 | Knowledge items can be written freely | The nightly knowledge indexer deactivates every active item it did not see in its own sources (`src/adp/knowledge/indexer.py:132-136`) | Projected pattern items MUST be exempt from that sweep, or they would vanish overnight |
| GT-7 | Export files `patterns/<key>@<version>.yaml` via the shared helpers | The shared safe-filename rule allows only `[A-Za-z0-9_-]` (`src/adp/export/common.py:33`); pattern keys contain dots | Pattern export validates filenames against the pattern key and version grammar instead |
| GT-8 | Views are Mermaid, validated with `mermaid-cli` | ADP renders with the vendored diagram-core flowchart dialect (`web/src/diagrams/core/dsl/flowchart-parser.ts`). It keeps quote characters inside labels, has no `.-x` / `--x` arrowheads, accepts subgraph titles only as `subgraph id [Title]`, ignores trailing `%%`, and rejects the **whole** diagram on any unrecognised line | Views target this dialect exactly. "Prohibited edge" is shown with a dotted edge and a marked label. Every rendered view must parse in this dialect with zero errors |
| GT-9 | A read-only diagram viewer exists | The only canvas component is the interactive editor. A read-only route exists: parse → auto-layout → SVG renderer (`web/src/diagrams/editor/ExportAction.tsx:34`) | The Patterns screen shows views read-only through that route |
| GT-10 | YAML editing in "Monaco" | No code-editor package is in `web/package.json`; ADP uses monospace `<textarea>` (`web/src/knowledge/KnowledgePage.tsx:78`) | Monospace textarea; no new editor dependency |
| GT-11 | Lifecycle uses "the ADP vocabulary" | The design lifecycle has `complete` and allows reset-to-draft from any state (`src/adp/api/routers/lifecycle.py:27`) | The 5-state machine below deliberately differs, because versions are immutable once proposed |

## Clarifications

### Session 2026-11-14

- Q: Who may import and edit draft pattern versions (PATTERN-02 OQ-3)? → A: **Enterprise Architects only** (and Platform Admin, which holds every action). Both `WRITE_PATTERN` and `GOVERN_PATTERN` go only to those roles. Solution and Technical Architect authoring can come later.
- Q: How are pattern kinds projected into the knowledge base, given that control mappings accept only kind `pattern`? → A: `reference-architecture` patterns are projected as knowledge kind `reference_architecture`; the other three pattern kinds are projected as `pattern`. The control mapping is **widened to also accept `reference_architecture`**, so every projected pattern can be mapped to controls.
- Q: What does a lifecycle transition require? → A: **A reason and a confirmation.** `GOVERN_PATTERN` joins the actions that require a per-action confirmation (ART-VIII). Every transition carries a non-empty confirmation id, which is stored in the lifecycle history alongside the reason and actor.
- Q: Auto-create a stub family for an unknown relation target (PATTERN-02 OQ-2)? → A (informed default): **No stubs.** A draft may carry unresolved references; each is reported as a warning. Promotion to `current` requires every reference to resolve.
- Q: Does rollback (`deprecated → current`) need its own reason (OQ-5)? → A (informed default): no separate mechanism. Every transition already requires a reason and a confirmation.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies). The lifecycle transition table, idempotency table and view goldens are written as failing tests before the implementation.
- **ART-II** — The Model is the Single Source of Truth: the registry stores the canonical definition from 934. The knowledge item is a derived projection, never edited directly.
- **ART-III** — Everything is Machine-Readable: YAML import, byte-identical YAML download and export, and JSON view responses.
- **ART-V** — Security by Design: in scope. Untrusted YAML crosses browser → API, and new write and governance permissions are added (see Threat Model).
- **ART-VII** — Grounded AI Only: indirectly. Projected patterns become citable knowledge for the recommendation and validation agents. Their text comes only from the governed `current` version.
- **ART-VIII** — Human Confirmation for Consequential Actions: every lifecycle transition requires a confirmation id.
- **ART-IX** — Auditability: actor-attributed log lines for every write, and a persisted lifecycle history.
- **ART-X** — Deterministic Validation Gating: import, promotion and rendering are deterministic for the same input.
- **ART-XIII** — Typed Contracts Everywhere: lifecycle states, import outcomes and view kinds are closed value sets.
- **ART-XV** — Schema Evolution is Governed: migration `044`, reversible.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**:
- the integrity of governed patterns, especially a `current` version that AI agents cite;
- the knowledge base, which the projection writes into;
- the control mappings attached to projected items;
- API availability when parsing untrusted YAML;
- the export tree on disk.

**Trust boundaries crossed**: browser → API (YAML upload, draft edits, lifecycle actions), API → database, and API → filesystem (export).

**Abuse cases**:
- **Unauthorised governance.** A non-EA promotes or deprecates a pattern → `GOVERN_PATTERN` is granted to EA/Platform Admin only, every transition needs a confirmation, and the authz completeness test covers every new route.
- **Rewriting an approved pattern.** An author edits a version after review → the definition and digest can change only in `draft`. Every other write is rejected and tested.
- **Hostile YAML** (alias bombs, oversized documents, tag construction) → the 934 parser's limits apply to every endpoint that takes YAML, including the dry runs. Request bodies over 256 KB are rejected before parsing.
- **Injecting text that AI agents will cite.** The projection's text comes only from a `current` version (reviewed and confirmed). Drafts never reach the knowledge base.
- **Hijacking the knowledge base.** An author tampers with a projected item through the general knowledge write routes → those routes reject changes to items owned by the pattern registry.
- **Path traversal in export.** A crafted key or version escapes the export root → filenames are built only from the validated key and semantic-version grammar, never from free text.
- **Markup injection in rendered views.** Labels are escaped and truncated, node ids are generated (never user text), and the client renders through the existing SVG renderer, which escapes text.

**Residual risk**:
- A confirmed EA can still promote a poorly worded pattern. That is governance, not security.
- Embedding the projection's text happens synchronously during promotion (the existing knowledge-route behaviour). This is acceptable at promotion frequency.

## User Scenarios & Testing *(mandatory)*

Actors:
- **Enterprise Architect (EA):** imports, edits, governs and reviews patterns.
- **Any authenticated user:** browses the catalog and views.
- **ADP's AI agents:** read projected patterns from the knowledge base.

### User Story 1 - Import a pattern and browse the catalog (Priority: P1)

An EA pastes or uploads a pattern YAML file on the new Patterns screen. If it is valid, it is stored as a `draft` version of its pattern family and appears in the catalog. If it is invalid, the screen lists every issue with its path, code and message, and nothing is stored. Any user can list patterns, filter by kind, lifecycle, tag or text, open a family to see its versions, open a version to see its summary, motivation, roles, relationships and constraints, and download its YAML.

**Why this priority**: without persistence and a catalog, nothing else in the epic has anything to govern, render or adopt.

**Independent Test**: import the 934 reference fixture through the API and the UI. It appears in the catalog as `draft`, the detail shows its content, and the downloaded YAML equals the canonical YAML. Importing an invalid fixture stores nothing and returns its issues.

**Acceptance Scenarios**:

1. **Given** a valid pattern YAML for a new key, **When** an EA imports it, **Then** a family and a `draft` version are created and the result is `created`.
2. **Given** the same YAML imported again, **When** it is re-imported, **Then** the result is `unchanged` and nothing new is stored.
3. **Given** a YAML with the same key and version but different content, **When** it is imported, **Then** it is `rejected`: "use update" if the existing version is a draft, "version immutable" otherwise.
4. **Given** a YAML whose kind differs from the family's existing kind, **When** it is imported, **Then** it is `rejected` with a kind-mismatch issue.
5. **Given** an invalid YAML (syntax, structure or expression errors), **When** it is imported, **Then** it is `rejected` with all issues and no family or version row exists afterwards.
6. **Given** a valid YAML that references an unknown principle, control, related pattern or application, **When** it is imported, **Then** it is `created` as a draft with one warning issue per unresolved reference.
7. **Given** a user without `WRITE_PATTERN`, **When** they attempt an import, **Then** it is refused (403). They can still browse and download.
8. **Given** several patterns, **When** a user filters by kind, lifecycle, tag or a text query on name/summary, **Then** only matching versions are listed.

---

### User Story 2 - Govern a pattern through its lifecycle (Priority: P1)

An EA moves a version through `draft → proposed → current → deprecated → decommissioned`. Each action needs a reason and an explicit confirmation. Promoting a version to `current` atomically demotes the previous current version of that family to `deprecated`. Promotion re-validates the definition and requires every reference to resolve. The version page shows the full lifecycle history: who, when, from → to, reason.

**Why this priority**: governed, immutable versions with a single current version are what make a pattern trustworthy enough for conformance (936) and for AI citation.

**Independent Test**: import v1.0.0, propose it, promote it to current. Import v1.1.0, propose it, promote it. v1.0.0 is now `deprecated` and v1.1.0 is `current`. The history shows four entries with reasons and confirmation ids, and an illegal transition returns 409.

**Acceptance Scenarios**:

1. **Given** a draft, **When** it is proposed, **Then** its definition becomes immutable, and edits or deletion are refused (409).
2. **Given** a proposed version, **When** it is sent back to draft, **Then** editing is possible again.
3. **Given** a family with a current v1 and a proposed v2, **When** v2 is promoted, **Then** in one transaction v2 becomes `current` and v1 becomes `deprecated`. There is never zero or two current versions.
4. **Given** a deprecated version, **When** it is promoted back to current (rollback), **Then** it becomes current and any other current version is deprecated.
5. **Given** a decommissioned version, **When** any transition is attempted, **Then** it is refused (409).
6. **Given** a proposed version whose referenced principle has since been deactivated, **When** promotion is attempted, **Then** it is refused, with an issue naming the unresolved reference.
7. **Given** a transition request without a reason or without a confirmation id, **When** it is submitted, **Then** it is rejected (422) and nothing changes.
8. **Given** two concurrent promotions within one family, **When** both commit, **Then** exactly one succeeds and the other gets 409.
9. **Given** a user without `GOVERN_PATTERN`, **When** they attempt a transition, **Then** it is refused (403).

---

### User Story 3 - Current patterns appear in the knowledge base (Priority: P2)

When a version becomes `current`, its family's single knowledge item is created or refreshed. The item has the pattern's name as its title, and its text is built from the summary, motivation and tags. Its kind is `reference_architecture` or `pattern`, according to the pattern kind. The recommendation engine and the validation critics can then retrieve and cite it, the Knowledge screen lists it with a "managed by Patterns" marker and a link, and compliance users can map controls to it. When a family has no current version any more, its knowledge item is hidden (deactivated), not deleted, so its control mappings survive.

**Why this priority**: it connects governed patterns to the parts of ADP that already consume patterns, without a second "where patterns live". It needs US1 and US2 first.

**Independent Test**: promote the reference fixture. A knowledge item with source reference `adp-pattern:<key>` exists, is active, and has kind `reference_architecture`. A control can be mapped to it. Running the nightly knowledge indexer leaves it active. Deprecating the only current version deactivates it, and the control mapping still exists.

**Acceptance Scenarios**:

1. **Given** a family's first promotion to current, **When** it commits, **Then** exactly one active knowledge item exists for that family, with the derived title, text, kind and source reference.
2. **Given** a later promotion within the same family, **When** it commits, **Then** the same knowledge item is updated in place (same id) to the new version's content, and its control mappings are untouched.
3. **Given** a family whose current version is deprecated with no replacement, **When** that commits, **Then** its knowledge item becomes inactive. Rolling back re-activates it.
4. **Given** a projected knowledge item, **When** the nightly knowledge indexer runs, **Then** the item is not deactivated.
5. **Given** a projected knowledge item, **When** someone tries to edit or delete it through the general knowledge routes, **Then** the change is refused with a message pointing to the Patterns registry.
6. **Given** a projected `reference_architecture` item, **When** a compliance user maps a control to it, **Then** the mapping is accepted. Knowledge items of other non-pattern kinds are still rejected.
7. **Given** a draft or proposed version, **When** it exists without ever being current, **Then** no knowledge item exists for it.

---

### User Story 4 - See a pattern as diagrams (Priority: P2)

On a version page, a user switches between three read-only diagram views:
- **Structure:** roles as nodes, labelled with stereotype and cardinality, plus relationships and render hints.
- **Catalog:** the pattern's neighbourhood over pattern-to-pattern relations, 1–3 hops.
- **Traceability:** the principles and controls that motivate the pattern → the pattern → its known implementations, with unresolved references shown as "unknown" rather than dropped.

Each view comes with its flowchart text, which can be copied, and a provenance header (key, version, view, digest prefix).

**Why this priority**: views make patterns understandable at a glance and are the visual basis for 936's conformance views. They aren't needed to govern.

**Independent Test**: render each view for each valid 934 fixture. The output is byte-identical to committed golden files, and every golden parses with zero errors in the in-app flowchart dialect.

**Acceptance Scenarios**:

1. **Given** the reference fixture, **When** the structure view is requested, **Then** the text matches its golden file and starts with the provenance header.
2. **Given** a pattern related to others, **When** the catalog view is requested at depth 1, 2 or 3, **Then** only patterns within that many hops appear, and each edge is labelled with its relation type. Deprecated versions carry a "(deprecated)" suffix; anti-patterns are styled as anti-patterns.
3. **Given** a pattern whose motivation cites a principle that does not exist, **When** the traceability view is requested, **Then** that principle appears styled as unknown.
4. **Given** names containing quotes, brackets, `<script>`, emoji or 200 characters, **When** any view is rendered, **Then** the output parses in the in-app dialect, labels are escaped or truncated with "…", and no user text is used as a node id.
5. **Given** the same pattern rendered repeatedly with shuffled non-semantic input order, **When** the outputs are compared, **Then** they are identical.
6. **Given** unsaved draft YAML in the editor, **When** an EA asks for a preview, **Then** the structure view is rendered from that text without storing anything.

---

### User Story 5 - Edit drafts and start new versions in the UI (Priority: P3)

An EA edits a draft's YAML in a monospace editor on the version page, validates it without saving (issues shown inline with their paths), and saves it, which replaces the draft's definition. From any version, "New version" opens the import form prefilled with that version's YAML so the EA can bump the version and change content. A draft can be deleted; deleting a family's last version removes the family.

**Why this priority**: it completes in-app authoring. Import-only (US1) is already usable, through an external editor plus the published schema from 934.

**Independent Test**: edit a draft so it breaks a rule. Validate shows the issue and Save is refused. Fix it, save, and the digest changes. "New version" on a current version produces a prefilled form, and importing it as 1.1.0 creates a new draft.

**Acceptance Scenarios**:

1. **Given** a draft, **When** its YAML is changed to an invalid document and validated, **Then** the issues are listed and nothing is saved.
2. **Given** a draft, **When** valid YAML with the same key, version and kind is saved, **Then** its definition, digest, name and summary are replaced.
3. **Given** a draft, **When** YAML with a different key or version is saved, **Then** it is refused (keys and versions are not renamed in place).
4. **Given** the only version of a family is a draft, **When** it is deleted, **Then** the family is gone too.

---

### User Story 6 - Patterns are exported with the rest of the architecture (Priority: P3)

When the export tree is enabled, every `current` version is written to `patterns/<key>@<version>.yaml`, byte-identical to the downloaded YAML. A file whose version is no longer current is removed on the next cycle.

**Why this priority**: it keeps patterns in the same version-controlled, file-based export as every other domain (OQ-B1), but nothing in-app depends on it.

**Independent Test**: with export enabled, promote a version. Its file appears and equals the download byte-for-byte. Promoting a newer version replaces the file, and an unchanged pattern's file is not rewritten.

**Acceptance Scenarios**:

1. **Given** export is enabled and a version is current, **When** a cycle runs, **Then** its YAML file exists and is byte-identical to the download.
2. **Given** a version that has stopped being current, **When** the next cycle runs, **Then** its file is removed.
3. **Given** export is disabled, **When** the platform runs, **Then** no pattern files are written.

---

### Edge Cases

- **Importing a newer version while a current one exists:** this creates a draft. Nothing changes for the current version until the new one is promoted.
- **A reference that resolves at import but is gone by promotion:** promotion fails with an unresolved-reference issue (the principle was deactivated, the control or related family deleted, or the application deleted).
- **Relations to a family that has no current version:** they resolve (the target is a family, not a version). The catalog shows the target's most relevant version: current, else the latest proposed, else the latest draft.
- **Deleting a family that other patterns relate to:** only possible when the family has nothing but drafts, which never project. Relations that target it become unresolved warnings on the referencing drafts and block their promotion.
- **Kind is fixed per family:** changing kind means a new key.
- **Version ordering:** "latest" uses semantic-version ordering, not text order (`1.10.0` comes after `1.9.0`).
- **Oversized bodies** (over 256 KB) are rejected before parsing, on every YAML-accepting endpoint.
- **Large catalogs:** the catalog view at depth 3 caps the node count and says so in the response rather than producing an unreadable diagram.
- **Projection when embedding fails:** promotion still succeeds and the item is stored with the existing fallback embedding, as knowledge routes do today. The failure is logged.
- **Deprecating the current version manually** (without promoting a replacement) leaves the family with no current version. That is allowed, and the projection is hidden.

## Requirements *(mandatory)*

### Functional Requirements

**Registry**
- **FR-001**: The system MUST persist pattern **families**, identified by pattern key with a fixed kind and owner role, and **versions**, identified by key + semantic version and holding the canonical definition, digest, name, summary and lifecycle state, with creation and last-lifecycle-change actor and time.
- **FR-002**: The system MUST import a pattern from YAML using the 934 parser and validation, with these outcomes:
  - **created:** a new key + version, stored as `draft`;
  - **unchanged:** same key + version and the same digest;
  - **rejected:** same key + version with a different digest ("use update" if it is a draft, "immutable" otherwise), a kind mismatch with the family, or any validation error.

  A rejected import MUST leave no stored rows.
- **FR-003**: On import and on draft update, the system MUST resolve these references and report each unresolved one as a warning issue with its path:
  - motivation principle ids → active knowledge items of kind `principle`;
  - motivation control ids → existing compliance controls;
  - relation targets → existing pattern families;
  - known implementations → existing applications.

  It MUST NOT auto-create stub families.
- **FR-004**: The system MUST store pattern-to-pattern relations (source version, target family, relation type, note) so that cross-pattern queries ("what relates to X") do not require parsing every definition.
- **FR-005**: Listing MUST support filters by kind, lifecycle, tag and a case-insensitive text query on name and summary. Family detail MUST list versions current-first, then in descending semantic-version order.
- **FR-006**: Any authenticated user MUST be able to download a version's canonical YAML, byte-identical to 934's canonical form.

**Lifecycle**
- **FR-007**: The lifecycle MUST be exactly:
  - `draft → proposed`
  - `proposed → current | draft`
  - `current → deprecated`
  - `deprecated → current | decommissioned`
  - `decommissioned` is terminal.

  Allowed transitions MUST be computed by a pure function. Every other transition is refused (409).
- **FR-008**: A version's definition and digest MUST change only while it is `draft`. Only drafts may be deleted, and deleting a family's last version MUST delete the family.
- **FR-009**: Promotion to `current` MUST, in one transaction:
  - re-run full validation;
  - require every reference in FR-003 to resolve;
  - demote any other current version of the family to `deprecated`;
  - refresh the knowledge projection (FR-013).

  At most one current version per family MUST be enforced by the database. A concurrent conflict returns 409.
- **FR-010**: Every transition MUST carry a reason (1–500 characters) and a non-empty confirmation id. Each MUST be recorded in a persisted lifecycle history (version, from, to, reason, confirmation id, actor, time). A demotion caused by a promotion is recorded as its own history entry that references the promotion.
- **FR-011**: The lifecycle history of a version MUST be viewable by any authenticated user.

**Authorization and audit**
- **FR-012**: The permission model MUST:
  - add `WRITE_PATTERN` (import, update draft, delete draft, dry-run validate and render) and `GOVERN_PATTERN` (lifecycle transitions);
  - grant both only to Enterprise Architect and Platform Admin;
  - add `GOVERN_PATTERN` to the actions that require confirmation;
  - bump `PERMISSIONS_VERSION` to `1.11.0`.

  Reads MUST stay open to all authenticated users. Every new non-GET route MUST map to one of the two actions, and the existing completeness test MUST pass. Every write MUST emit an actor-attributed log line that includes the digest before and after (and, for transitions, the reason and confirmation id).

**Knowledge projection**
- **FR-013**: While a family has a current version, the system MUST maintain exactly one knowledge item for it, with:
  - a stable id derived from the key;
  - source reference `adp-pattern:<key>`;
  - kind `reference_architecture` for reference-architecture patterns and `pattern` for the other kinds;
  - the current version's name as title;
  - text built from the summary, motivation (context, problem, forces, benefits, liabilities) and tags;
  - metadata naming the pattern key, version and kind.

  When the family has no current version, the item MUST be deactivated, not deleted. Draft and proposed content MUST never be projected.
- **FR-014**: The nightly knowledge indexer MUST NOT deactivate items owned by the pattern registry.
- **FR-015**: The general knowledge write routes MUST refuse to update or delete registry-owned items, with a message pointing to the Patterns registry.
- **FR-016**: Control-to-pattern compliance mappings MUST accept knowledge items of kind `pattern` or `reference_architecture`. Other kinds remain rejected.

**Views**
- **FR-017**: The system MUST render the **structure**, **catalog** (depth 1–3, default 1) and **traceability** views of a stored version as flowchart text in the in-app diagram dialect (GT-8). Each view MUST:
  - start with the header `%% adp-pattern <key>@<version> view=<view> digest=<12 chars>`;
  - be deterministic;
  - use generated node ids only;
  - escape and truncate labels (60 characters, "…");
  - style nodes with a fixed, named palette built from ADP's existing accessible theme colours;
  - parse with zero errors in that dialect.
- **FR-018**: The view response MUST include the view kind, flowchart text, digest, generation time and any truncation notes (for example, catalog node cap reached).
- **FR-019**: Users with `WRITE_PATTERN` MUST be able to validate and to render the structure view from unsaved YAML without anything being stored (dry runs).

**Export**
- **FR-020**: When the existing export tree is enabled, a background cycle MUST write every current version to `patterns/<key>@<version>.yaml`:
  - byte-identical to FR-006's download;
  - rewriting files only when their content changed;
  - removing files for versions that are no longer current;
  - building filenames only from the validated key and version grammar (GT-7).

**User interface**
- **FR-021**: A new **Patterns** screen in the Oversight navigation section MUST provide:
  - **catalog:** list with kind, lifecycle, tag and text filters;
  - **family detail:** versions with lifecycle badges;
  - **version detail:** summary, motivation, roles, relationships and constraints; a YAML tab with download; a Views tab (US4) rendered read-only through the existing SVG renderer; lifecycle history;
  - **import:** paste or file upload, with issues listed by path;
  - **lifecycle actions:** only the transitions allowed from the current state, each through a dialog that requires a reason and an explicit confirmation;
  - **draft editing:** monospace YAML editor with Validate, Preview (structure view) and Save, plus Delete draft;
  - **"New version":** prefilled import from any version.

  Write and governance controls MUST be hidden for users without the corresponding permission.
- **FR-022**: The Knowledge screen MUST mark registry-owned items as "managed by Patterns", link them to the pattern, and not offer edit or delete for them.

**Seed data**
- **FR-023**: The demo seed MUST import and promote four seed patterns derived from the 934 valid fixtures (backbone, mesh anti-pattern, mesh-to-backbone transition, one-system-of-record rule; not the longhand duplicate), so a fresh environment has a populated catalog with relations. The fixtures cite placeholder principle ids (`P-API-FIRST`, `P-NO-P2P`, `P-SINGLE-SOURCE`) that do not exist, and the seeded principles are `PRIN-001`…`PRIN-006` (`scripts/seed_knowledge.py:22-117`). The seed copies therefore cite real seeded principles (for example `PRIN-003` API First, `PRIN-004` Loose Coupling), so promotion resolves. The 934 unit fixtures stay unchanged.

### Key Entities

- **Pattern Family**: a stable pattern key with a fixed kind and owner role. It owns versions and at most one knowledge projection.
- **Pattern Version**: one immutable-once-proposed definition of a family, with semantic version, lifecycle state, digest and denormalised name and summary.
- **Pattern Relation**: a typed edge from a version to a target family (realizes, specializes, replaces, conflicts_with, requires, alternative_to), with an optional note.
- **Lifecycle History Entry**: one transition of one version (from, to, reason, confirmation id, actor, time, optional triggering promotion).
- **Pattern Knowledge Projection**: the single knowledge-base item derived from a family's current version. It is read-only outside the registry.
- **Pattern View**: a generated, deterministic flowchart rendering of a version (structure, catalog or traceability). It is never stored.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An EA can import the reference pattern, propose it and promote it to current from the Patterns screen in under 3 minutes, without touching an API directly.
- **SC-002**: 100% of the lifecycle transition matrix (every from/to pair) and every row of the import-outcome table are covered by automated tests, and they behave as specified.
- **SC-003**: Across any sequence of promotions, including concurrent ones, no family ever has more than one current version.
- **SC-004**: A promoted pattern is retrievable by the existing knowledge retrieval used by the recommendation and validation agents immediately after promotion, and it is still active after a nightly indexer run.
- **SC-005**: 100% of rendered views for the seeded patterns parse with zero errors in the in-app diagram dialect and match their committed golden files.
- **SC-006**: Exported pattern files are byte-identical to the in-app download for 100% of current versions.
- **SC-007**: Every new write or governance route is covered by the authorization completeness test, and a Reviewer, Solution Architect or Technical Architect is refused on each.

## Assumptions

- Pattern content is not sensitive: reads are open to every authenticated user, and no field-level gating applies.
- Lifecycle confirmation follows the established request-body confirmation-id convention (admin prompts and rubrics, agent suggestions). The UI generates the id when the user confirms the dialog.
- Synchronous embedding at promotion is acceptable, as it is for existing knowledge writes. Promotion is rare.
- Existing prose patterns in the knowledge base are left untouched. Converting them into registry patterns is a follow-on.

## Out of Scope

- Adoptions, conformance evaluation, transition progress, and the conformance and transition views (spec 936).
- "Save view as diagram" into the Diagrams library (spec 936).
- CALM export (spec 937).
- Git → database sync of pattern files.
- AI-drafted patterns.
- Diffing between versions.
- Pattern authoring by roles other than EA and Platform Admin.
- Indexing patterns into the global search and chat index.
- Reverse lookups such as "which patterns cite principle X" in the UI.
