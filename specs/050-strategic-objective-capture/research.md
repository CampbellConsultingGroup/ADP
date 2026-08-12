# Phase 0 Research: Capture Strategic Objectives

No `NEEDS CLARIFICATION` markers remain in spec.md's Technical Context — this feature's scope was
already thoroughly grounded during specification. The decisions below record the concrete
implementation facts confirmed by direct reads during planning.

## Decision 1: A new sibling package, `adp.strategy`, not an extension of `adp.business`

**Decision**: `StrategicTheme`/`StrategicObjective` CRUD lives in a new top-level package,
`src/adp/strategy/`, mirroring the `adp.diagrams`/`adp.chat` sibling-package convention already
established in this codebase — not added into `adp.business`'s existing `models.py`/`store.py`/
`router.py`.

**Rationale**: Directly measured: `adp.business`'s three core files are already 573 + 1104 + 1170 =
2,847 lines combined. Every recent addition to this codebase that represents a genuinely distinct
sub-domain (diagrams, chat) has gotten its own top-level package rather than growing an
already-large existing one, even when it's conceptually adjacent (e.g., `adp.diagrams` doesn't
import from `adp.business` at all, despite both being "business-adjacent"). `adp.strategy` follows
that same precedent, keeping `adp.business`'s files from growing further for a concept
(`StrategicObjective`) that is a distinct entity with its own lifecycle, not a variant of
capability/value-stream/domain.

**Alternatives considered**:
- Adding directly into `adp.business`'s existing files — rejected: would make three already-large
  files larger for no benefit, and this codebase's own recent history (diagrams, chat) shows the
  established response to "a new, related-but-distinct concept" is a new sibling package, not
  continued growth of an existing one.

## Decision 2: Cross-package validation reuses `adp.business.store`'s existing read functions directly

**Decision**: `adp.strategy.store`'s link-creation functions call `adp.business.store.get_capability(cap_id, session)`
and `adp.business.store.get_value_stream(vs_id, session)` directly (both confirmed to exist with
exactly this signature, returning `None` when not found) to validate a link target exists before
writing it — never a duplicated or bypassed check.

**Rationale**: This is the same cross-package pattern Agent Review already uses (`adp.business.agent_review`'s
`flag_capability_for_removal` acceptance calls `adp.business.store.delete_capability` directly) —
confirmed as an established, accepted pattern in this codebase for one domain module to call
another's already-public store functions for a specific, narrow purpose, rather than either
duplicating that logic or reaching into the other module's private internals.

**Alternatives considered**:
- A new capability/value-stream existence-check endpoint exposed by `adp.business` specifically for
  this feature to call over HTTP — rejected: unnecessary indirection; both packages already run in
  the same process against the same database, so a direct Python function call (already precedented)
  is simpler and doesn't introduce a new API surface for an internal validation need.
- Trusting the frontend's dropdown selection alone (client-side only, no server-side existence
  check) — rejected outright: violates spec.md's own FR-005/FR-006 ("chosen from ADP's real
  capability registry — never entered as free text") and SC-002's "zero...orphaned link values are
  ever possible to create" — that guarantee has to be server-enforced, not just a client-side
  convenience.

## Decision 3: Reuses the existing `WRITE_BUSINESS_ARCH` action — no new `ActionType`

**Decision**: All `adp.strategy` write endpoints (theme create, objective create/update/delete,
link create/delete) are gated by the same `ActionType.WRITE_BUSINESS_ARCH` check already used
throughout `adp.business`'s own router — confirmed via direct read of `_require_write_business_arch(user)`,
the exact helper pattern to mirror.

**Rationale**: Directly precedented: when `business_domains` (ADP-SPEC-035) was added — the closest
existing analog to `StrategicTheme` — it needed no new `ActionType` either, reusing
`WRITE_BUSINESS_ARCH` since it's conceptually the same "who can write business architecture data"
question. A `StrategicObjective` is architecturally the same category of data (a business-strategy
registry entity an Enterprise/Solution/Technical Architect can maintain), so introducing a new,
narrower `ActionType` here would fragment the permission model for no real access-control
distinction spec.md actually asks for.

**Alternatives considered**:
- A new `ActionType.WRITE_STRATEGY` — rejected: would require its own `PERMISSIONS_VERSION` bump
  and completeness-test updates (`tests/authz/test_permissions.py`) for a distinction the spec
  doesn't call for; `business_domains`'s own precedent already answered this the other way.

## Decision 4: The capability/value-stream link editors are near-verbatim mirrors of `DesignLinkEditor.tsx`

**Decision**: Two new components, `ObjectiveCapabilityLinkEditor.tsx` and
`ObjectiveValueStreamLinkEditor.tsx`, follow `DesignLinkEditor.tsx`'s exact structure (a filtered
`<select>` excluding already-linked items, a Link button, a per-row Remove button, backed by
dedicated `useLink*`/`useUnlink*` mutation hooks that invalidate a linked-items query on success) —
confirmed via direct read of both the component and its backing `useLinkDesignToCapability`/
`useUnlinkDesignFromCapability` hooks in `web/src/api/business.ts`.

**Rationale**: `DesignLinkEditor.tsx` already proves this exact interaction shape (search-and-add
against a real registry, never free text) at a comparable data scale (design counts, like
capability/value-stream counts, are small enough that a filtered dropdown needs no live-search).
Building a new, more complex typeahead component for this feature would contradict spec.md's own
Assumption (grounded in this same precedent) without adding real value at this scale.

**Alternatives considered**:
- A single generic, parameterized `LinkEditor` component covering all three link types (designs,
  capabilities, value streams) — considered, but left for a future refactor rather than done here:
  `DesignLinkEditor.tsx` is entity-type-parameterized already (`entityType: "capability" |
  "value-stream"`) for *its own* two directions, but generalizing it to also cover *objective* as a
  new source-entity type would touch an existing, working, tested component for this feature's
  sake alone — two new small sibling components carry less risk than modifying a proven one, and
  can be unified later if a third consumer emerges.
