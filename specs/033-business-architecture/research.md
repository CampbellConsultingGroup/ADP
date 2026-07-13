# Research: Business Architecture — Capability Model and Value Streams

**Feature**: 033-business-architecture
**Date**: 2026-07-10
**Status**: Complete — no NEEDS CLARIFICATION items in spec

## Decision 1: Tree Storage Pattern for Capability Hierarchy

**Decision**: Adjacency list (`parent_id` FK on the same table)

**Rationale**: The spec hard-caps hierarchy at 3 levels (FR-004). With a fixed depth of 3, there is no need for recursive CTEs, closure tables, or nested sets. The entire tree can be fetched in a single `SELECT * FROM business_capabilities` and assembled in application code in O(n). For the stated performance target of 500 nodes, a single query + in-memory assembly is both correct and fast. Adjacency list is also the simplest schema — one nullable `parent_id` column — and aligns with how `DesignElement` parent references already work in the codebase.

**Alternatives considered**:
- **Closure table**: More complex; justified only for arbitrary depth. Adds a second table and complicates inserts.
- **Nested set (Celko)**: Efficient for reads but expensive for writes. Hard cap at 3 levels makes its read advantage irrelevant.
- **Materialised path**: Good for unlimited depth but overcomplicated for 3 levels.

## Decision 2: Stage Ordering Mechanism

**Decision**: Integer `position` column with client-supplied reorder via a bulk `PUT /stages` (replaces the stages list entirely for a given value stream).

**Rationale**: Updating a `position` field is transparent, SQL-queryable, and already used in the codebase (`designs.position`, element ordering). A bulk-replace endpoint (`PUT /api/v1/business/value-streams/{id}/stages`) replaces all stages in one call, avoiding complex delta-merge logic. For v1 stage counts (typically 3–8), bulk replace is safe and simple. Individual add/edit/delete endpoints are kept for granular UI operations; reorder is a separate endpoint.

**Alternatives considered**:
- **Linked list (prev/next pointers)**: More complex to query and maintain; no advantage for small lists.
- **Drag-and-drop position float**: Fractional positions avoid resequencing but require periodic renormalisation. Overkill for v1.

## Decision 3: API Routing Structure

**Decision**: Flat resource routes under `/api/v1/business/` prefix.

```
/api/v1/business/capabilities          (collection)
/api/v1/business/capabilities/{id}     (item)
/api/v1/business/value-streams         (collection)
/api/v1/business/value-streams/{id}    (item + stages in response)
/api/v1/business/value-streams/{id}/stages/{stage_id}  (stage item)
```

**Rationale**: Consistent with existing ADP router conventions. The `/business/` prefix clearly namespaces the new domain without nesting under `/designs/` or `/knowledge/`. Capabilities are returned as a flat list with `parent_id`; tree assembly happens client-side, which is simpler than server-side recursive serialisation and easier to cache with TanStack Query.

**Alternatives considered**:
- **Nested routes (`/capabilities/{id}/children`)**: More REST-pure but complicates tree fetch (requires multiple requests or a non-standard `?include=children` query param).
- **GraphQL**: Not in the ADP stack; not warranted for this scope.

## Decision 4: Python Module Structure

**Decision**: New `src/adp/business/` module with sub-modules `models.py`, `store.py`, `router.py`.

**Rationale**: Mirrors the existing pattern used by `adp.knowledge`, `adp.calm`, `adp.audit`. Each domain gets its own package under `adp/`. The router is registered in `adp.api.app` alongside the 16 existing routers.

## Decision 5: Frontend Module Structure

**Decision**: New `web/src/business/` directory with a `BusinessPage.tsx` container, tabbed between Capabilities and Value Streams sub-views. New `web/src/api/business.ts` for all TanStack Query hooks.

**Rationale**: Mirrors the `web/src/knowledge/` and `web/src/intake/` patterns. The Business Architecture section is a new top-level nav destination (matches assumption in spec). Tabs avoid a second nav-bar level for v1.

## Decision 6: Navigation Placement

**Decision**: Add "Business" as a new item in the existing `NavBar` component, between "Knowledge" and any design-related items.

**Rationale**: Business architecture is a peer of Knowledge and Designs — not subordinate to either. The nav bar already supports multiple items; adding one more is a 2-line change to `shell.tsx`.

## Decision 7: ID Generation for Capabilities and Value Streams

**Decision**: Server-generated UUIDs (same as existing `DesignStore` entities). Slug-style human-readable IDs are not used here because capability names may contain arbitrary characters and are not unique.

**Rationale**: UUIDs are already used throughout the ADP backend. Consistency beats any marginal readability benefit of slugs for IDs that users never see.

## Decision 8: Audit Logging

**Decision**: Write an `AuditEntry` for create, update, and delete mutations on both `BusinessCapability` and `ValueStream`. Stage mutations (add/edit/delete) are logged at the parent value stream level (one entry per value stream mutation), not per-stage.

**Rationale**: The spec marks ART-IX as SHOULD, not MUST, for this feature. Implementing it is low-cost given the existing `AuditEntry` model and writer. Logging at the value stream level rather than per-stage keeps the audit log manageable.
