# Research: Business Domain Registry and Stage-Capability Mapping (ADP-SPEC-035)

## Decision 1: Domain deletion cascade strategy

**Decision**: Use PostgreSQL `ON DELETE SET NULL` on the `domain_id` FK column in `business_capabilities`. When a domain is deleted the database automatically nulls the FK on all its L1 capabilities — no application-level loop required.

**Rationale**: `ON DELETE SET NULL` is the correct relational primitive for "soft disassociation" (FR-008). It is atomic, consistent under concurrent writes, and removes the need for application code to manually null-out `domain_id` values before or after the DELETE. It also prevents accidental FK constraint violations if the router issues the DELETE before the nulling loop completes.

**Alternatives considered**: Application-level loop (UPDATE capabilities SET domain_id = null WHERE domain_id = :id) before deleting the domain — functionally correct but requires two round-trips and introduces a window of inconsistency under concurrent reads. Rejected.

---

## Decision 2: TEXT[] storage for risk_flags in SQLAlchemy Core (no ORM)

**Decision**: Use `sa.ARRAY(sa.Text())` as the column type in the SA Core Table definition for `risk_flags`. PostgreSQL natively supports `TEXT[]`. Pydantic model uses `list[str]`. Filtering is applied at the Pydantic layer (reject blank entries; deduplicate via `list(dict.fromkeys(v))`).

**Rationale**: Consistent with the existing `store.py` pattern (SA Core, no ORM mapper). `sa.ARRAY` is the correct SQLAlchemy Core type for PostgreSQL arrays. No additional dependency needed.

**Alternatives considered**: JSONB array — more flexible for nested structures but adds query complexity for a flat string list. Normalized `domain_risk_flags` table — over-engineered for a free-text convention list. Both rejected.

---

## Decision 3: Classification stored as TEXT with Pydantic enum validation

**Decision**: Store `classification` as `TEXT` (not a PostgreSQL ENUM type) in the DB. Pydantic validates it as `Literal["strategic", "differentiating", "commodity"]`. A CHECK constraint is added at migration time as a safety net: `CHECK (classification IN ('strategic', 'differentiating', 'commodity'))`.

**Rationale**: PostgreSQL ENUM types are notoriously painful to extend (requires `ALTER TYPE … ADD VALUE` which cannot run inside a transaction). Since the spec explicitly states classification values may need extension via a spec amendment and migration, TEXT + CHECK is the right balance: the constraint prevents bad data, and extending it is a simple `ALTER TABLE … DROP CONSTRAINT … ADD CONSTRAINT` in a future migration — no ENUM ALTER needed.

**Alternatives considered**: PostgreSQL ENUM — adds schema complexity for no benefit given the known extension requirement. Pure Pydantic validation with no DB constraint — allows silent constraint bypass via direct SQL; rejected.

---

## Decision 4: Domain assignment endpoint design

**Decision**: A dedicated `PATCH /api/v1/business/capabilities/{cap_id}/domain` endpoint with body `{"domain_id": "<uuid>"}` to assign and `{"domain_id": null}` to clear. Returns the updated `BusinessCapability`.

**Rationale**: Domain assignment is a distinct operation from name/description/position updates. Mixing it into `BusinessCapabilityUpdate` creates a null-ambiguity problem: `domain_id: null` in PATCH cannot distinguish "not provided" from "explicitly clear." A dedicated endpoint with a minimal request body avoids this and is self-documenting. The endpoint also enforces the L1-only constraint with a clear 422 message.

**Alternatives considered**: Extend `BusinessCapabilityUpdate` with an optional `domain_id` field and a sentinel value — more complex Pydantic model with sentinel logic. Rejected for simplicity. `PUT`/`DELETE` on the same sub-resource — two endpoints instead of one PATCH, higher surface area. Rejected.

---

## Decision 5: Stage-capability join table name and PK

**Decision**: Table named `value_stream_stage_capabilities`. Composite PK `(stage_id, capability_id)`. Both FK legs use `ON DELETE CASCADE`: deleting a stage removes its capability links; deleting a capability removes its stage links. Index on `capability_id` for reverse lookup.

**Rationale**: Consistent with the 034 join table pattern (`capability_design_links`, `value_stream_design_links`). Composite PK enforces uniqueness at the DB layer (returns 409 from the unique constraint violation at the app layer, consistent with 034 pattern). Reverse index on `capability_id` enables efficient "which stages use capability X?" queries needed for future landing page analysis.

**Alternatives considered**: Surrogate PK with a UNIQUE constraint — unnecessary indirection. No index on `capability_id` — would make capability-centric queries a full table scan; rejected since the landing page spec will need this.

---

## Decision 6: Domain detail response includes L1 capabilities

**Decision**: `GET /api/v1/business/domains/{id}` returns a `DomainDetail` model that includes the domain fields plus a `capabilities: list[CapabilityRef]` field (id, name, level — matching the existing `CapabilityRef` model from 034). The list endpoint returns `DomainSummary` (all domain fields + `capability_count: int` but not the full capability list).

**Rationale**: The detail endpoint serves the "assign capabilities to domain" UI workflow. The list endpoint serves the domain index page and future aggregation. Keeping them separate avoids returning large capability lists in list responses.

**Alternatives considered**: Always returning full capability list in list response — O(n*m) data for m domains with n caps each; rejected. No capability list in detail — would require a separate GET for the assignment UI; rejected.

---

## Decision 7: ART-IX (audit) strategy — same as 033/034

**Decision**: Structured `logger.info()` for all domain and stage-capability link mutations. No `audit_entries` table writes. ART-IX is SHOULD; the business module does not have a `design_id` FK path to generate globally-unique `AUD-NNN` IDs.

**Rationale**: Identical justification to ADP-SPEC-033 and ADP-SPEC-034. The `audit_entries` table requires loading the full `ArchitectureDescription` JSONB to generate non-colliding IDs; forcing that path for business entity mutations would create spurious design versions.

---

## Decision 8: Updating the existing `_capabilities` SA Table definition

**Decision**: Add `domain_id` as a new nullable column to the existing `_capabilities` SA Table object in `store.py`. No second Table definition needed. The migration ALTER TABLE adds the column; the SA Table in `store.py` is updated to declare it.

**Rationale**: SA Core table objects are declarations, not schema owners. Extending the existing `_capabilities` Table to include `domain_id` keeps capability queries in a single SA Table reference and avoids mirroring the column in two places.

---

## Decision 9: BusinessPage navigation — Domains as a third tab

**Decision**: Add a "Domains" tab to the existing `BusinessPage` three-tab bar (alongside "Capabilities" and "Value Streams"). Domain list and detail views are rendered within this tab. No new top-level nav entry is needed.

**Rationale**: Domains are a business architecture concept, correctly housed within the Business page. Adding a third tab is minimal surface change. The future landing page spec will add a separate top-level view.

**Alternatives considered**: Sidebar panel within Capabilities tab — awkward for CRUD; rejected. New top-level nav entry — premature given scope; rejected.

---

## Decision 10: Stage-capability linking UI placement

**Decision**: Add a "Capabilities" subsection to the existing `ValueStreamStageEditor.tsx` per-stage editor. Each stage row expands to show linked capabilities and a capability picker (similar to `DesignLinkEditor` pattern from 034).

**Rationale**: The stage editor already handles per-stage CRUD. Adding capability linking inline keeps the interaction co-located with the stage it affects. A new `StageCapsEditor.tsx` reusable component (analogous to `DesignLinkEditor`) keeps the logic encapsulated.

---

## Decision 11: Zero new packages

**Decision**: No new Python or npm packages are required. `sa.ARRAY` is in the existing `sqlalchemy` dependency. All other constructs use the existing stack.
