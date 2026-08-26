# Feature Specification: Application Type (COTS/Custom/SaaS/Legacy) Grouping Dimension

**Feature Branch**: `929-application-type-cots`
**Created**: 2026-08-26
**Status**: Draft
**Input**: Bead ADP-3jj — "Application type (COTS/custom/SaaS/legacy) grouping dimension for
Application Portfolio". Follow-on from ADP-8xo (Application Portfolio pivot), deferred at that
time because no such field existed on `Application` at all (confirmed by the bead's own grep of
`src/adp/application/models.py`: `app_type`/`application_type`/`COTS`/`mainframe`/`is_custom`/
`build_vs_buy` all return zero matches). `hosting_model` (on_prem/cloud/saas/hybrid) is a partial,
insufficient proxy — it captures deployment location, not build-vs-buy/vendor-vs-custom/legacy
status.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this spec, per the project's own mandate that any
  not-yet-spec'd feature-sized bead goes through the full cycle (matches the precedent this
  session already set for 926/927/928).
- **ART-IV** — Test-Driven Development: unit tests (models/store), contract tests (router), and
  frontend unit tests (groupApplications.ts, ApplicationForm.tsx) all written before/alongside
  implementation.
- **ART-III** — AI/Tool Grounding: `application_type` is added to `adp.export.application_arch`'s
  existing `_serialize_application()` (ADP-SPEC-045) so it's visible to file-based AI/tool
  consumers, not just the interactive API — the same completeness bar every other Application
  field already meets.
- **ART-V** — not materially in scope. `application_type` is an unauthenticated-read, low-sensitivity
  classification field (identical sensitivity tier to `hosting_model`/`pace_layer`/`lifecycle_status`,
  none of which carry a `READ_APPLICATION_*` gate) written only by an already-authorized
  `WRITE_APPLICATION`-holding caller through the existing create/update endpoints.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none beyond what `hosting_model`/`pace_layer` already expose — a single bounded
classification string per application, world-readable to any authenticated platform user (no new
sensitive-category gate needed, matching the precedent those two fields already set).

**Trust boundaries crossed**: none new — writes flow through the existing `PUT/POST
/api/v1/applications` routes, already gated by `WRITE_APPLICATION` (a route-prefix rule in
`adp.authz.enforcement`, unchanged by this feature).

**Abuse cases**: a caller without `WRITE_APPLICATION` attempting to set `application_type` →
blocked by the existing route-level permission check (no new code path, no new risk).

**Residual risk**: none beyond the existing risk profile of every other Application scalar field.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An architect classifies an application's build-vs-buy type (Priority: P1)

An Enterprise/Solution Architect editing an application in the Application registry sets its type
(Custom-built, COTS, SaaS, or Legacy/Mainframe) alongside its other classification fields (TIME,
7R, PACE layer, hosting model).

**Why this priority**: Without a way to *set* the value, the grouping dimension in User Story 2
would have nothing to group by — every application would render as Unclassified.

**Independent Test**: Create or edit an application via `POST/PUT /api/v1/applications[/{id}]`
with `application_type: "cots"`, confirm the value round-trips on `GET`, and confirm the
`ApplicationForm.tsx` dropdown and `ApplicationDetail.tsx` read view both reflect it.

**Acceptance Scenarios**:

1. **Given** a new application being created, **When** the architect selects "SaaS" from the
   Application Type dropdown and saves, **Then** the created application's `application_type` is
   `"saas"`.
2. **Given** an existing application with no `application_type` set, **When** the architect views
   it, **Then** the dropdown shows "— none —" (matching every other optional classification
   field's own unset-state convention) and the detail view omits the line entirely (matching
   `pace_layer`'s own conditional-render convention).
3. **Given** an application with `application_type: "legacy"`, **When** a caller submits an
   `application_type` value outside the four allowed values, **Then** the API rejects the request
   with 422 (matching `hosting_model`'s own invalid-value rejection precedent).

---

### User Story 2 - A portfolio viewer groups applications by build-vs-buy type (Priority: P1)

On the Application Portfolio screen, a viewer picks "Application Type" from either "Group by"
dropdown to see the portfolio pivoted into Custom / COTS / SaaS / Legacy buckets (plus
Unclassified for anything not yet typed), exactly like the five existing dimensions.

**Why this priority**: This is the bead's own stated deliverable — the reason the field is being
added at all. Co-P1 with User Story 1 since neither is independently valuable without the other
(a settable-but-ungroupable field, or a groupable-but-unsettable one, both fail the bead's intent).

**Independent Test**: With a mix of typed and untyped applications, select "Application Type" in
either Group By dropdown and confirm four ordered buckets (Custom, COTS, SaaS, Legacy) plus a
trailing Unclassified bucket for untyped applications, matching every other dimension's own
rendering. Confirm it also composes correctly with the existing cross-tab (ADP-3wa) and Filter by
(ADP-9ye/ADP-6w4) mechanisms, since both are already dimension/field-agnostic.

**Acceptance Scenarios**:

1. **Given** a mix of Custom/COTS/SaaS/Legacy/untyped applications, **When** "Application Type" is
   selected as Group By, **Then** the four typed buckets render in Custom → COTS → SaaS → Legacy
   order, each showing only its own applications, plus Unclassified last for any untyped
   application.
2. **Given** "Application Type" selected as both Group By and Then By, **When** the cross-tab
   renders, **Then** it behaves identically to selecting the same dimension twice for any existing
   dimension (reverts to the flat single-axis view, per `PortfolioPage.tsx`'s own established
   same-dimension rule).
3. **Given** "Application Type" selected in the Filter by dropdown, **When** a specific type value
   is chosen, **Then** only applications of that type are shown, composing correctly with an active
   Group By/cross-tab exactly as every other Filter by field already does.

### Edge Cases

- An application created before this feature exists with no `application_type` column value
  (`NULL`) renders identically to one explicitly never set — both fall into Unclassified. No
  backfill/default value is applied (matches `hosting_model`'s own precedent: nullable, no
  server-side default).
- `application_type: "saas"` (this feature) and `hosting_model: "saas"` (ADP-SPEC-038) are
  independent fields answering different questions (who built it, vs. where it deploys) — an
  application can be `application_type: "custom"` and `hosting_model: "saas"` simultaneously (a
  custom app deployed to a SaaS-model hosting arrangement) with no conflict or validation coupling
  between the two.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist a new optional `application_type` field on `Application`, with
  exactly four allowed values: `custom`, `cots`, `saas`, `legacy`.
- **FR-002**: `application_type` MUST be nullable with no default value — an application with no
  type set is a normal, valid state (matches `hosting_model`'s own precedent, not
  `lifecycle_status`'s NOT-NULL-with-default one).
- **FR-003**: `POST /api/v1/applications` and `PUT /api/v1/applications/{id}` MUST accept an
  optional `application_type`; an update explicitly setting it to `null` MUST clear any existing
  value (matching every other nullable field's `model_fields_set`-based clear-vs-omit semantics in
  `update_application`).
- **FR-004**: The API MUST reject any `application_type` value outside the four allowed values with
  a 422 response (Pydantic `Literal` validation, matching `hosting_model`'s own precedent).
- **FR-005**: `GET /api/v1/applications` MUST accept an optional `application_type` query filter,
  mirroring `hosting_model`'s own existing filter parameter exactly (parity, not a new mechanism).
- **FR-006**: `ApplicationForm.tsx` MUST expose an "Application Type" dropdown (Custom-Built / COTS
  / SaaS / Legacy-Mainframe / — none —) alongside the existing Hosting Model dropdown.
- **FR-007**: `ApplicationDetail.tsx` MUST display the application's type when set, using the same
  conditional-render convention as `pace_layer`.
- **FR-008**: The Application Portfolio screen (`web/src/portfolio/`) MUST offer "Application Type"
  as a sixth Group By / Then By / Filter by dimension, with fixed bucket order Custom → COTS → SaaS
  → Legacy (mirroring the fixed-enum-order convention `groupByHostingModel`/`groupByPaceLayer`
  already use, not the dynamic/alphabetical convention `groupByBusinessUnit` uses for free text).
- **FR-009**: `adp.export.application_arch`'s existing `_serialize_application()` (ADP-SPEC-045)
  MUST include `application_type` in its exported JSON, so file-based AI/tool consumers see the
  same field API consumers do.

### Key Entities

- **Application** (existing, `adp.application.models`): gains one new optional field,
  `application_type: Literal["custom", "cots", "saas", "legacy"] | None`, alongside its existing
  `hosting_model`/`pace_layer`/`lifecycle_status` classification fields. No new entity, no new
  table, no new relationship.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can set, clear, and filter-reject an invalid `application_type` value
  entirely through the existing Application create/edit flow, with zero new screens.
- **SC-002**: The Application Portfolio screen's Group By/Then By/Filter by dropdowns each grow
  from 5/8/8 to 6/9/9 dimensions respectively (Filter by inherits Application Type automatically,
  since `ALL_FILTER_FIELDS` is defined as `[...ALL_DIMENSIONS, ...]`), with zero changes to any of
  the five pre-existing dimensions' own behavior.
- **SC-003**: Every existing Application-registry/export/APM test continues to pass unmodified,
  confirming this is a strictly additive field (no existing behavior depends on the new column's
  absence).

## Assumptions

- The four-value set (`custom`, `cots`, `saas`, `legacy`) is fixed as literally named in the bead
  title — no fifth "hybrid build" or "outsourced custom" value is in scope; a broader taxonomy is
  explicit future follow-on if ever needed.
- No UI changes to `web/src/insights/ApplicationsHeatMap.tsx` (a separate, non-architect-facing
  screen, ADP-SPEC-019/919) — the bead's own title scopes this to the Application Portfolio screen
  specifically, matching how ADP-6w4/ADP-9ye (this session's two prior Portfolio-dimension
  features) were also scoped to that one screen.
- No data backfill/migration of existing applications' `application_type` — every pre-existing row
  starts `NULL` (Unclassified), consistent with how `hosting_model` itself was introduced with no
  backfill.
