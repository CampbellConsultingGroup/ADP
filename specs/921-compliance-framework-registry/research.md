# Research & Decisions: Compliance Framework & Control Registry (COMPLY-01)

Phase 0 output. Each decision records the choice, rationale, and rejected alternatives.

## D1 — Package placement: new sibling package `adp.compliance`

**Decision**: A new top-level package `src/adp/compliance/` (`models.py`, `store.py`, `router.py`), a sibling
to `adp.business`, `adp.application`, `adp.strategy` — not folded into either existing package.

**Rationale**: The source doc flagged this as an explicit open question, to be resolved by measuring
`adp.business` and `adp.knowledge` against the ~2,800-line threshold that triggered `adp.strategy`'s
historical split from `adp.business`. Measured directly: `adp.business`'s core files (`models.py` 583 +
`router.py` 1181 + `store.py` 1156 = **2,920 lines**, excluding `agent_review.py`) are *already past* that
threshold — folding a new domain in would make an already-oversized package larger still. `adp.knowledge`
is well under the threshold (813 lines total) but is the wrong conceptual fit regardless of size: the
source doc itself draws the line between "content you look up" (`knowledge`, free-text + vector search) and
"content you formally link against with a typed, evidenced relationship" (registries like Business
Capabilities) — a Framework/Control registry with FK-enforced hierarchy and DB-level uniqueness is
unambiguously the second kind.

**Rejected**: Folding into `adp.business` — already over the package's own historical size trigger, and
Compliance is explicitly framed as a *cross-cutting* domain in the source bundle's own header (reads from
Business, Application, Solution, Strategy), not a sub-concern of Business Architecture. Folding into
`adp.knowledge` — wrong conceptual category (free-text lookup vs. typed FK-enforced registry).

## D2 — Delete semantics: DB-level cascade, not an application-layer block

**Decision**: Both `controls.framework_id` and `controls.parent_id` are foreign keys with `ON DELETE
CASCADE`. Deleting a framework removes every control beneath it (all levels); deleting a control removes
every descendant control beneath it. Postgres's native FK cascade handles the self-referencing multi-level
case correctly — no recursive application code needed.

**Rationale**: Spec FR-005/FR-013 explicitly require this shape ("deleting a framework/control MUST also
remove every control/child recorded under it... at every hierarchy level"), and the source doc explicitly
states `ON DELETE CASCADE` for `Control.framework_id`. This is a deliberate divergence from
`business_capabilities`' own precedent (`delete_capability` *rejects* deletion via `ChildCapabilitiesExist`
when children exist, rather than cascading) — worth calling out explicitly since it's the opposite behavior
of the closest existing analog, not an oversight.

**Rejected**: Mirroring Business Capability's reject-on-children behavior — would contradict FR-005/FR-013,
which the spec (already through `/speckit.clarify`) fixed as cascade-with-disclosure, not block-and-force-
manual-cleanup.

## D3 — Scope-before-delete disclosure is a frontend concern, not a new endpoint

**Decision**: The "user MUST be shown the scope of what will be removed before the deletion is confirmed"
requirement (FR-005/FR-013, SC-006) is satisfied client-side: the full control tree is already fetched for
display (FR-011), so the frontend computes the descendant count from that already-in-memory tree and shows
it in a confirmation dialog before calling `DELETE`. No dedicated "preview delete" backend endpoint.

**Rationale**: The data needed for the disclosure is already on the client by the time a delete is
initiated (a user deletes from a view that's already rendering the tree). Adding a server round-trip to
recompute what the client can already derive is redundant surface area for zero additional correctness.

**Rejected**: A `GET .../{id}?dry_run=delete`-style preview endpoint — adds an endpoint and a contract for
data the client already has in hand.

## D4 — Authorization: dedicated `ActionType.WRITE_COMPLIANCE`

**Decision**: New `ActionType.WRITE_COMPLIANCE`, granted to `SOLUTION_ARCHITECT` and `TECHNICAL_ARCHITECT`
explicitly (Enterprise Architect and Platform Admin receive it automatically via their existing wildcard
grants — no change needed to either entry). `PERMISSIONS_VERSION` bumps `1.8.0` → `1.9.0`. New route-prefix
rule `("/api/v1/compliance/", ActionType.WRITE_COMPLIANCE)` in `enforcement.py`'s prefix table, exactly the
shape of the existing `/api/v1/business/` → `WRITE_BUSINESS_ARCH` and `/api/v1/applications` →
`WRITE_APPLICATION` rules. Reads are ungated — confirmed directly against `enforcement.py`: neither
Business nor Application has a `READ_*` action at all, only their write path is gated.

**Rationale**: Resolved in `/speckit.clarify` (Clarification Session 2026-08-17, Q1) — a new dedicated
permission was chosen over reusing `WRITE_BUSINESS_ARCH`, mirroring `WRITE_APPLICATION`'s precedent (each
new top-level domain gets its own write action) rather than Strategy's precedent (reused
`WRITE_BUSINESS_ARCH` because Strategy is governance-adjacent to Business Architecture specifically).
Compliance is framed as its own cross-cutting domain, not a Business Architecture sub-concern, so the
`WRITE_APPLICATION`-style precedent is the better fit.

## D5 — Hierarchy validation (no-cycle, same-framework) is application-layer, not DB-level

**Decision**: FR-008's "reject a cycle or cross-framework parent" is enforced in `create_control`/
`update_control` by walking up from the proposed parent toward the root before the write, rejecting if the
control being created/updated is encountered, or if the walk reaches a control belonging to a different
framework. Not expressible as a DB constraint.

**Rationale**: Postgres cannot express "no cycles in a self-referencing FK" or "parent must share my
`framework_id`" as a `CHECK` constraint. This mirrors the exact precedent already set by
`create_capability`, which validates `parent.level == data.level - 1` in the store function for the
identical reason (also un-expressible as a DB constraint) — same shape of problem, same shape of fix.

## D6 — Code uniqueness: DB-level composite `UNIQUE(framework_id, code)`

**Decision**: A composite unique constraint at the DB level, not just an application-layer pre-check.

**Rationale**: FR-009 plus the platform's stated NFR that cross-entity/uniqueness integrity is enforced at
the database level, not just application-layer checks (the same NFR the source doc invoked when
recommending four join tables over one polymorphic table for COMPLY-02). A `sa.UniqueConstraint` on
`(framework_id, code)`, migration-owned per the existing "migration owns constraints, store `Table()` is
DML-only" convention. The router catches the resulting `IntegrityError` and translates it into a clean
validation error (409), the same pattern `DuplicateLinkError`/`DuplicateStageCapError` already establish
elsewhere in `adp.business`.

## D7 — Migration number: `032`, chained off the real current head

**Decision**: New migration `032_compliance_framework_registry.py`, `down_revision = "031"`.

**Rationale**: Read the actual on-disk migration chain directly rather than trusting `CLAUDE.md`'s Recent
Changes narrative (which lags the repo's real state) — the true head is `031_ai_process_capture.py`,
confirmed by walking every file's `revision`/`down_revision` pair.

## D8 — No `level` column; depth is derived, not stored

**Decision**: Unlike `business_capabilities` (which stores `level IN (1,2,3)`), `controls` has no depth
column. Depth is computed at read time (recursive tree assembly in the store layer, same shape as
`BusinessCapabilityNode`'s tree assembly) rather than persisted.

**Rationale**: Spec Assumption: nesting depth is unbounded, and (per the source doc's GDPR walkthrough)
varies clause-by-clause within the same framework — there is no fixed depth enum to store, unlike Business
Capability's fixed 3-level scheme.

## Open items for `/speckit.tasks`

- Confirm the exact nav placement for a new "Compliance" screen in `web/src/shell/` (sibling top-level
  entry vs. nested under an existing section) — a UI-only detail, not blocking backend task breakdown.
- `ControlUpdate`'s `code`/`parent_id` fields (reparenting/recoding after creation) re-run the same D5/D6
  validation as create; confirm test coverage includes the update path for both, not just create.
