# Research: Application Registry (ADP-SPEC-036)

All decisions are derived from the existing ADP stack (033/034/035). No external research required; the technology choices are already established.

---

## Decision 1: Module location — `adp.application`

**Decision**: New top-level module `src/adp/application/` (models.py, store.py, router.py), parallel to `src/adp/business/`.

**Rationale**: 035 (`adp.business`) follows the same three-file module pattern and serves as the template. Placing application data in its own module maintains clear separation of concerns and makes future ownership RBAC layering straightforward.

**Alternatives considered**: Adding to `adp.business` — rejected because business capabilities and technical capabilities are distinct taxonomies owned by different stakeholders; mixing them into one module would create a monolith.

---

## Decision 2: Alembic migration — 010, down_revision = "009"

**Decision**: Single migration file `010_application_registry.py` with `down_revision = "009"`.

**Rationale**: 035 used migration 009. Maintaining sequential ordering is required by ART-XV.

**Alternatives considered**: Splitting into multiple migrations — rejected because all tables land in the same feature and a single migration is easier to roll back atomically.

---

## Decision 3: ART-IX deviation — structured logging

**Decision**: Application mutations logged via `logger.info()` with structured fields (`actor`, `entity`, `id`, `action`). No `audit_entries` table row written.

**Rationale**: Same deviation as ADP-SPEC-033/034/035. Business and application entities have no `design_id` FK path to `audit_entries`. ART-IX is satisfied by ART-VI observability (structured logs). This is a consistent, pre-justified position across all business-architecture modules.

**Alternatives considered**: Writing to `audit_entries` with a null `design_id` — rejected as inconsistent with existing precedent and the constitution interpretation established in research.md Decision 7 of ADP-SPEC-035.

---

## Decision 4: Technical capability parent delete — RESTRICT (not CASCADE)

**Decision**: `technical_capabilities.parent_id` FK uses `ON DELETE RESTRICT`. Deleting a parent that has children is blocked at the DB level.

**Rationale**: FR-021 states the API should return 409 if a capability has children. RESTRICT at the DB level gives consistent enforcement even outside the API. This is safer than CASCADE (which would silently remove an L3 capability when an L2 is deleted).

**Alternatives considered**: CASCADE delete tree — rejected because an architect deleting an L2 node might not intend to delete all L3 children; 409 forces explicit cleanup.

---

## Decision 5: Fit score and health score enforcement — DB CHECK + Pydantic

**Decision**: Both `fit_score` (on `application_capability_links`) and `health_score` (on `applications`) have `CHECK (value BETWEEN 1 AND 5)` at the DB level and `Annotated[int, Field(ge=1, le=5)]` in Pydantic v2 models.

**Rationale**: Dual enforcement (Pydantic at API boundary + DB constraint) ensures scores are never out of range regardless of how the DB is accessed. Consistent with the pattern used for `level` (1–3) on technical capabilities.

---

## Decision 6: Application integration source≠target — DB CHECK + API validation

**Decision**: `application_integrations` table has `CHECK (source_app_id <> target_app_id)`. The API also validates this in the Pydantic model with a `model_validator`.

**Rationale**: Self-integration is semantically invalid (FR-038). DB-level CHECK provides a hard backstop; Pydantic validation provides a clean 422 response before the DB is reached.

---

## Decision 7: Design link FK — validate in application code

**Decision**: `application_design_links.design_id` references `designs(id) ON DELETE CASCADE`. The store function checks that the design exists before inserting the link (returns 404 if not found).

**Rationale**: FK at the DB level enforces referential integrity. The application-level existence check gives a proper 404 rather than a FK violation (which would be a 500).

---

## Decision 8: Router prefixes

**Decision**:
- Applications: `/api/v1/applications`
- Technical capabilities: `/api/v1/technical-capabilities`
- Application integrations: `/api/v1/integrations`

All sub-resources (links) are nested under `/api/v1/applications/{id}/...`

**Rationale**: Follows REST nesting conventions used in the existing business router (`/api/v1/business/...`). Integrations are at the top level (not nested under either app) because they are a first-class entity with their own UUID.

---

## Decision 9: Frontend — new `web/src/application/` directory

**Decision**: New `web/src/application/` directory with dedicated components; new "Applications" nav item added to NavBar.

**Rationale**: Mirrors the `web/src/business/` structure established in ADP-SPEC-033. Keeping application views in their own directory avoids polluting the business views directory.

---

## Decision 10: ApplicationDomainIntegration `integration_type` — free text

**Decision**: `integration_type` on `application_domain_integrations` is a free-text `VARCHAR(255)` with no enum check constraint.

**Rationale**: Spec assumption states free text is preferred in v1 to give architects flexibility before a controlled vocabulary emerges. Unlike `direction` (which has three clear values) or `integration_type` on `application_integrations` (which has six well-known values), domain integration types are organisation-specific.

---

## Decision 11: `usage_type` composite PK on application_tech_cap_links

**Decision**: Primary key on `application_tech_cap_links` is `(app_id, tech_cap_id, usage_type)`. A single application can have both a "provides" and a "consumes" link to the same technical capability.

**Rationale**: An application might both provide a REST API (provides) and also consume the same capability class internally (consumes). The composite PK with usage_type allows this; the 409 duplicate check applies only when the exact tuple already exists.
