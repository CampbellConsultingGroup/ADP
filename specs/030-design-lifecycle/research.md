# Research: Design Lifecycle Management (ADP-SPEC-030)

## Key Findings

### Decision 1: Storage Architecture for Lifecycle Data

**Decision**: Dual storage — lifecycle fields on `ArchitectureDescription` Pydantic model (JSONB, source of truth) AND as indexed columns on the `designs` table (derived, for fast queries).

**Rationale**:
- ART-II requires lifecycle to be part of the canonical model so it travels with the design in exports. Adding lifecycle fields to `ArchitectureDescription` with `None` defaults is backward compatible (ART-XV).
- SC-002 requires sub-500ms filtering across the portfolio. The `designs` table has a row per design without parsing JSONB — an indexed `lifecycle_status TEXT` column there enables instant filtering. `DesignStore.list_all()` currently loads full JSONB for every design; with the indexed column we can filter on the `designs` table first, then only load matching JSONB rows.
- `DesignStore.save()` already writes to the `designs` table (updating `current_version`, `updated_at`). Adding lifecycle column updates to the same `save()` call costs nothing extra.

**Alternatives considered**:
- Lifecycle on `designs` table only (not in JSONB): lifecycle data would not travel with exports unless the exporter separately joins the `designs` table. Fragile and adds coupling to the export layer.
- Lifecycle in JSONB only: no indexed column means a GIN/JSON path scan for every portfolio filter query — slower than a B-tree column scan.

### Decision 2: Transition Endpoint — PATCH vs Dedicated Action Endpoint

**Decision**: `PATCH /api/v1/designs/{id}/lifecycle` with a structured body containing the new status, an optional note, and optional date overrides.

**Rationale**:
- PATCH is semantically appropriate — partial update of the design's lifecycle state.
- A single endpoint handles all transition types (no need for `/propose`, `/mark-current` etc. — the `status` field in the body drives the transition logic).
- The server enforces the transition graph (FR-004) — invalid transitions return 409 Conflict with a message listing valid next states.

**Alternatives considered**:
- Separate action endpoints per transition (`POST /lifecycle/propose`, etc.): more explicit but more endpoints to maintain; the transition graph check needs duplicating.

### Decision 3: Auto-Set Dates vs Explicit Dates

**Decision**: Server auto-sets the relevant date on transition if not already set AND if the architect has not supplied an override. If an override date is supplied in the request, it is used instead.

**Rationale**:
- FR-005 requires automatic recording. Most architects will not bother setting dates manually — auto-setting ensures the data is always present.
- Override support (via optional `proposed_date`, `current_since`, `retirement_date` fields in the request) handles the case where a transition is being recorded retroactively (e.g. "this system actually went live three months ago").
- `review_due` is never auto-set — it is a future-looking date that requires explicit architect input (no transition implies a specific review schedule).

### Decision 4: Transition Graph Enforcement

**Decision**: Enforce the transition graph in application code (the `PATCH /lifecycle` handler), not at the database level.

**Rationale**:
- The graph is simple enough to enforce in a small Python dict/set. A DB-level check constraint would require recreating the constraint when the graph changes.
- Storing the graph in application code makes it easy to test and document (QG-04 / ART-IV).

### Decision 5: `list_all()` Filter Implementation

**Decision**: Add an optional `status: str | None` parameter to `DesignStore.list_all()` and `count_all()`. When set, the SQL query adds `WHERE designs.lifecycle_status = :status` before loading JSONB rows.

**Rationale**:
- The `designs` table already has a join in the `list_all()` query. Adding a WHERE clause on the indexed `lifecycle_status` column is a minimal change that delivers SC-002.
- The `lifecycle_status` column has a B-tree index so the WHERE clause is O(log n).

### Decision 6: No New Python Packages

**Decision**: Zero new dependencies. Existing stack covers everything.
