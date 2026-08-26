# Feature Specification: Hybrid Search Phase 2 Completion — Stages, Domain Org Unit, Backfill

**Feature Branch**: `930-hybrid-search-phase`
**Created**: 2026-08-26
**Status**: Draft
**Input**: Bead ADP-7bo — "Hybrid search phase 2/3: value streams, domains, other text fields."
Phase 1 (ADP-b6o) shipped the polymorphic `searchable_items` index + hybrid search over business
and technical capabilities.

## Ground-Truth Correction (found before writing requirements)

The bead's own description assumes phase 2 (value streams, business domains) is entirely unbuilt.
Direct code inspection shows this is **partially wrong**: `041-ai-chat-assistant` (already shipped,
confirmed via `adp.chat.retrieval.DEFAULT_ENTITY_TYPES` and its own inline comment — "applications/
value-streams/business-domains were wired up in `adp.application.store`/`adp.business.store`
alongside this change") already added `ENTITY_APPLICATION`/`ENTITY_VALUE_STREAM`/
`ENTITY_BUSINESS_DOMAIN` constants and `index_entity`/`unindex_entity` write hooks to
`create_value_stream`/`update_value_stream`/`delete_value_stream` and
`create_domain`/`update_domain`/`delete_domain`, as a side effect of building the Chat Assistant's
retrieval leg — not as a deliberate execution of this bead. This spec covers only the **real
remaining gaps**, found by direct inspection of `adp.business.store`/`adp.search.backfill`, not
guessed from the bead's original (now partly stale) text:

1. **`value_stream_stages` are not indexed at all** — no `ENTITY_VALUE_STREAM_STAGE` constant, no
   write hooks in `add_stage`/`update_stage`/`delete_stage`/`reorder_stages`.
2. **`business_domains`' indexed text omits `org_unit`** — `create_domain`/`update_domain` only
   index `name` + `scope_statement`, confirmed by direct read of both call sites.
3. **A latent cascade-unindex bug**: `delete_value_stream`'s own comment says "FK CASCADE handles
   stage deletion" — true at the DB level, but the Postgres FK cascade cannot invoke the Python
   `unindex_entity()` call a stage's own `delete_stage` path uses, so deleting a value stream today
   already silently orphans its stages' index rows (a bug that exists right now, invisible only
   because stages were never indexed in the first place — this spec's stage-indexing work makes it
   real and must fix it in the same change, not introduce it and defer the fix).
4. **`adp.search.backfill` covers only capabilities** — `reindex_capabilities()` never indexes
   applications, value streams, stages, or domains, even though write hooks for 4 of those 5 types
   already exist. The bead's own literal ask (`reindex_capabilities` → `reindex_all`) is still
   correct and unaddressed.
5. **The bead's phrase "scope in/out" does not match the actual data model** — `BusinessDomain` has
   one combined `scope_statement` field (already partly indexed, gap is `org_unit` only, per #2
   above), not separate scope-in/scope-out fields. No model change follows from this — it is a
   terminology correction only.
6. **Zero test coverage exists** for any of the write-hook wiring added by 041 (value
   stream/domain indexing), for stage indexing (new), or for backfill, confirmed by a direct grep
   across `tests/` for `ENTITY_VALUE_STREAM`/`ENTITY_BUSINESS_DOMAIN`/`ENTITY_APPLICATION`/
   `reindex_capabilities` — zero matches anywhere. This spec's test tasks close that gap for all of
   it, not just the new stage/backfill work.

No new migration is needed (confirmed: `searchable_items` is polymorphic, per phase 1's own
design) — matching the bead's own acceptance criteria.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies; this bead's text was stale enough (see
  Ground-Truth Correction) that writing a spec before coding was the only way to scope this
  correctly rather than duplicating 041's already-shipped work.
- **ART-IV** — Test-Driven Development: this feature's primary deliverable, arguably, *is* closing
  a test-coverage gap (correction #6) — every write-hook path (existing and new) gets a test.
- **ART-III** — AI/Tool Grounding: this is precisely what `adp.search`/`adp.chat.retrieval` exist
  for — completing it closes a real blind spot in the Chat Assistant's own retrieval coverage
  (`DEFAULT_ENTITY_TYPES` already lists `ENTITY_VALUE_STREAM`, so a stage's own text was already
  advertised as searchable to the chat assistant without actually being indexed).
- **ART-V** — not materially in scope. No new trust boundary — reuses phase 1's own established
  best-effort, swallow-errors write path (`index_entity`/`unindex_entity`), unchanged.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none new — the same searchable text (value stream stage names/descriptions,
already fully readable by any authenticated user via the existing stage CRUD endpoints) becomes
additionally indexed for search, at the identical sensitivity tier as its parent value stream.

**Trust boundaries crossed**: none new — writes flow through the existing, already-authorized
stage/domain/value-stream CRUD routes; this feature only adds a search-index side effect to
already-permitted writes.

**Abuse cases**: none new beyond phase 1's own accepted risk (a search-index write/read failure is
swallowed and logged, never blocking or exposing the primary registry operation).

**Residual risk**: identical to phase 1 — none beyond what's already accepted for capability/
application/value-stream/domain indexing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A value stream stage is discoverable in search the moment it's created (Priority: P1)

An architect creates or renames a value stream stage (e.g. "Quote", "Underwrite"); a subsequent
`GET /api/v1/search?q=quote&entity_types=value_stream_stage` finds it.

**Why this priority**: This is the one genuinely unbuilt piece of the bead's original scope — the
other two entity types (value streams, domains) already index on write via 041.

**Independent Test**: Create a stage, search for a distinctive word in its name, confirm a hit;
delete it (directly, or by deleting its parent value stream), confirm the hit disappears.

**Acceptance Scenarios**:

1. **Given** a new stage named "Fraud Triage" under an existing value stream, **When** searched for
   "triage" with `entity_types=value_stream_stage`, **Then** the stage appears in results.
2. **Given** an existing indexed stage, **When** its name is changed via `PATCH .../stages/{id}`,
   **Then** a search for its old name no longer matches it and a search for its new name does.
3. **Given** an indexed stage, **When** it is deleted directly (`DELETE .../stages/{id}`), **Then**
   it no longer appears in search results.
4. **Given** an indexed stage, **When** its *parent value stream* is deleted (not the stage
   directly), **Then** the stage's index row is also removed — the cascade-unindex fix (Ground-
   Truth Correction #3) is exercised, not just the direct-delete path.
5. **Given** a bulk `PUT .../value-streams/{id}/stages` reorder request that both drops one stage
   and renames another, **When** the reorder completes, **Then** the dropped stage's index row is
   gone and the renamed stage's index row reflects its new name.

---

### User Story 2 - A business domain's org unit is part of what makes it findable (Priority: P2)

A user searches by an organizational unit name (e.g. "Claims Operations") and finds the business
domain owned by that unit, not just domains whose free-text description happens to mention it.

**Why this priority**: A real, narrow indexing gap (Ground-Truth Correction #2) — lower priority
than User Story 1 because domain search already partly works (name + scope statement), this only
adds one more field to an already-functioning path.

**Independent Test**: Create a domain with a distinctive `org_unit` value and no matching text
anywhere else on the domain; confirm it's found by searching that org unit name.

**Acceptance Scenarios**:

1. **Given** a domain with `org_unit="Claims Operations"` and unrelated name/scope text, **When**
   searched for "Claims Operations", **Then** the domain appears in results.

---

### User Story 3 - An operator can (re)build the full search index from scratch (Priority: P2)

An operator runs the backfill script after a schema/embedding-model change (or to recover from a
gap) and every currently-indexable entity type — capabilities, applications, value streams, stages,
domains — is reindexed in one pass, not just capabilities.

**Why this priority**: The bead's own literal ask; independently valuable as a recovery/consistency
tool, but lower priority than the two live-write-path fixes above since a backfill only matters when
something has already drifted.

**Independent Test**: Seed one of each of the 5 entity types with no existing index rows; run the
backfill; confirm all 5 appear in search results afterward.

**Acceptance Scenarios**:

1. **Given** a database with existing capabilities, applications, value streams (with stages), and
   domains but an empty `searchable_items` table, **When** the backfill runs, **Then** every one of
   those entities is indexed and individually discoverable via search.
2. **Given** the backfill has already run once, **When** it runs again with no underlying data
   change, **Then** it completes without error (idempotent upsert, matching phase 1's own
   `ON CONFLICT DO UPDATE` semantics — unchanged, just exercised over more entity types).

### Edge Cases

- A stage with no `description` (nullable field) indexes on `name` alone (`build_text` already
  drops empty/`None` parts) — matches every other entity's own null-handling.
- Reordering stages via `PUT .../stages` can rename a stage as part of the same request (the store
  function already accepts `name`/`description` per item, not just position) — the reindex must
  reflect the *new* name, not the pre-reorder one.
- Deleting a value stream with zero stages is a no-op for the cascade-unindex fix (nothing to
  unindex) — must not raise or log spuriously for the common "no stages yet" case.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST index a value stream stage's `name` and `description` under a new
  `ENTITY_VALUE_STREAM_STAGE` entity-type discriminator on create.
- **FR-002**: System MUST re-index a stage on update (name/description change via `PATCH`).
- **FR-003**: System MUST remove a stage's index row on direct deletion (`DELETE .../stages/{id}`).
- **FR-004**: System MUST remove a stage's index row when its *parent value stream* is deleted
  (closing Ground-Truth Correction #3 — the FK-cascade-orphans-the-index-row bug).
- **FR-005**: System MUST correctly reindex or unindex every stage affected by a bulk reorder
  (`PUT .../value-streams/{id}/stages`): dropped stages unindexed, renamed stages reindexed under
  their new text.
- **FR-006**: System MUST include `org_unit` in a business domain's indexed text, alongside the
  existing `name`/`scope_statement`, on both create and update.
- **FR-007**: `adp.search.backfill` MUST provide a `reindex_all()` function that indexes every
  currently write-hooked entity type — business capabilities, technical capabilities, applications,
  value streams, value stream stages, and business domains — in one pass, superseding
  `reindex_capabilities()`'s capability-only scope as the script's `main()` entry point.
- **FR-008**: No API/router change is required for the `entity_types` search filter to accept the
  new `value_stream_stage` type — the filter already accepts any string equality match against
  `searchable_items.entity_type` (confirmed by direct read of
  `adp.api.routers.search.search()`); this spec's job is only to ensure the constant exists and gets
  written, not to change the filter mechanism itself.
- **FR-009**: Every write-hook path added or already existing (value stream, stage, domain — both
  new and pre-existing 041 wiring) MUST have test coverage, closing Ground-Truth Correction #6.

### Key Entities

- **`ValueStreamStage`** (existing, `adp.business.models`): no field change — gains a new
  `ENTITY_VALUE_STREAM_STAGE` search-index discriminator and write-hook wiring only.
- **`BusinessDomain`** (existing): no field change — its already-existing `org_unit` field is
  added to the text already being indexed for `name`/`scope_statement`.
- **`searchable_items`** (existing, `adp.search.index`, migration 011): no schema change — one more
  `entity_type` discriminator value written into the same polymorphic table.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A stage is discoverable via search within one write (no batch/backfill delay) from
  the moment it's created, renamed, or reordered, and disappears immediately on deletion (direct or
  cascaded via its parent value stream).
- **SC-002**: A business domain is discoverable by its organizational unit name alone, with no other
  matching text required.
- **SC-003**: `python -m adp.search.backfill` indexes all 5 entity types in one run, with a reported
  count broken down (or at minimum, a total inclusive of all 5) — not just capabilities.
- **SC-004**: Every write-hook path (new and pre-existing) has at least one test exercising it —
  zero write-hook code in `adp.business.store` related to search indexing is untested after this
  feature ships.

## Assumptions

- `ENTITY_APPLICATION` write hooks (already shipped via 041, in `adp.application.store`) are
  correct as-is and need no code change — only backfill coverage (FR-007) and, opportunistically,
  a test if one doesn't already exist (it doesn't — Ground-Truth Correction #6), since it's already
  fully wired and this spec's own FR-009 scope naturally includes verifying it.
- The `/api/v1/search` endpoint's default `entity_types` (capabilities only, when the query param is
  omitted) is unchanged by this feature — expanding the default is a separate, explicit UX decision
  not requested by this bead's acceptance criteria ("filterable by entity_type" is satisfied by the
  existing pass-through mechanism, confirmed in FR-008).
- No change to `adp.chat.retrieval.DEFAULT_ENTITY_TYPES` — it does not yet list
  `ENTITY_VALUE_STREAM_STAGE`; adding it is a one-line follow-on left to a future bead if wanted,
  since this spec's own scope is the indexing mechanism, not every consumer of it.
