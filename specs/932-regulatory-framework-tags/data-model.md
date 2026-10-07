# Data Model: Regulatory Framework Tags for Application Risk & Compliance

## Entities

### ApplicationFrameworkTag (new)

The persisted form of the spec's "Application Regulatory Framework Tag" key entity. A bare,
unassessed link — no `compliance_status`, no `evidence_ref`, unlike a `ControlMapping`.

| Field | Type | Notes |
|---|---|---|
| `application_id` | `String(36)` | FK → `applications.id`, `ON DELETE CASCADE`. Part of composite PK. |
| `framework_id` | `String(36)` | FK → `regulatory_frameworks.id`, `ON DELETE CASCADE`. Part of composite PK. |
| `created_at` | `DateTime(timezone=True)` | `server_default=now()`. |

**Constraints**:
- Composite primary key `(application_id, framework_id)` — enforces FR-009 (at most one tag per
  pair) at the database level.
- Index on `framework_id` alone (`ix_aft_framework_id`) — the non-leading composite-PK column,
  mirroring `ix_tfl_framework_id`'s identical purpose on `theme_framework_links`; kept for any
  future reverse-lookup query even though none is built in this pass (research.md D7).
- Both FK legs `ON DELETE CASCADE`: deleting an `Application` or a `RegulatoryFramework` removes
  the tag automatically (FR-005; Assumptions — matches every sibling Compliance link table).

**Relationships**: Many-to-many between `Application` and `RegulatoryFramework`, realized as this
join table. No ORM-level cardinality limit beyond the composite PK; an application may have zero
tags (FR-007) or many; a framework may be tagged by zero or many applications.

### RegulatoryFramework (existing — referenced, not modified)

No changes to the canonical `regulatory_frameworks` table or its Pydantic model (`adp.compliance.
models.RegulatoryFramework`, COMPLY-01/01a). This feature reads it via a narrow read-only mirror,
exactly as `adp.strategy.store._regulatory_frameworks` already does.

**New read-only mirror** (`adp.application.store`, written nowhere, existence/validation reads
only):

| Column | Type | Purpose |
|---|---|---|
| `id` | `String(36)`, PK | Existence check (FR-002). |
| `name` | `Text` | Not strictly required for validation, but carried per the `_designs`/`_applications` mirror idiom (research.md D1) in case a future error message wants it. |
| `status` | `Text` | Status-gate check for newly-added tags (research.md D4; FR-001). |

### ApplicationRisk (existing — modified)

`regulatory_tags: list[str]` changes meaning (not wire type — still `list[str]`, research.md D3)
from "arbitrary free text" to "the set of `ApplicationFrameworkTag.framework_id` values currently
linked to this application." Computed on read via a `JOIN`/subquery against the new table rather
than stored inline; no longer a column on `application_risk` (research.md D6 drops it).

All other `ApplicationRisk`/`ApplicationRiskUpdate` fields (`security_posture`,
`vulnerability_status`, `data_classification`, `dr_bc_status`, `end_of_life_date`,
`end_of_support_date`) are untouched by this feature.

## Validation Rules (maps to Functional Requirements)

| Rule | FR | Where enforced |
|---|---|---|
| A submitted `regulatory_tags` id not present in `regulatory_frameworks` is rejected (whole write fails, 422) | FR-002 | `adp.application.store.upsert_application_risk`, against the new mirror |
| A **newly-added** id (not already linked) whose mirrored `status` is not `in_force`/`amended` is rejected | FR-001, FR-002 | same function — diff-then-validate (research.md D4) |
| An id that was **already** linked is never re-validated against current `status` on an unrelated save | Edge Case (status change after tagging) | same function — the diff only validates the newly-added subset |
| `(application_id, framework_id)` pairs are never duplicated | FR-009 | composite PK + Python-side de-duplication of the submitted list before diffing |
| Deleting a `RegulatoryFramework` removes every tag referencing it | FR-005 | `ON DELETE CASCADE` on `framework_id` |
| Deleting an `Application` removes every tag for it | (implied — existing cascade precedent for application-scoped sensitive data) | `ON DELETE CASCADE` on `application_id` |
| Read/write of tags requires `READ_APPLICATION_RISK`/`WRITE_APPLICATION_RISK` respectively, unchanged | FR-004 | existing `require_action_dep` dependencies already on `GET`/`PUT .../risk`, untouched |
| An application may have zero tags | FR-007 | no `NOT NULL`/min-count constraint; absence of rows *is* the zero-tag state |

## State / Lifecycle

No state machine. A tag exists or it doesn't (created on link, removed on unlink or cascade). The
one lifecycle-adjacent nuance is the Edge Case already captured above: a tag's continued existence
is independent of its framework's `status` changing after the tag was made — only an actual
framework *deletion* removes it.
