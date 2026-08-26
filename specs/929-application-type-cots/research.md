# Research: Application Type Grouping Dimension

## D1: Field shape mirrors `hosting_model` exactly

**Decision**: `application_type` is a nullable `TEXT` column with a `CHECK` constraint restricting
it to the four literal values, a `Literal["custom", "cots", "saas", "legacy"] | None = None`
Pydantic field, and a B-tree filter index — the identical shape migration `016` already gave
`hosting_model`.

**Rationale**: `hosting_model` is the closest existing sibling field on the exact same entity: a
single-select, small, fixed-enum, optional classification with no default. There is no reason to
invent a different shape (e.g. a separate lookup table, a boolean flag set, or a `NOT NULL WITH
DEFAULT` column like `lifecycle_status` uses) when an identical-shaped field already has a proven
migration/model/store/router/frontend pattern in this exact module.

**Alternatives considered**:
- A `NOT NULL DEFAULT 'custom'` column (matching `lifecycle_status`'s pattern instead) — rejected:
  defaulting every pre-existing and future-unclassified application to "custom" would be actively
  wrong/misleading data, unlike `lifecycle_status`'s "active" default which is a genuinely safe
  assumption for a newly created application.
- A free-text field (matching `owning_business_unit`) — rejected: the bead names a closed,
  four-value set explicitly ("COTS/custom/SaaS/legacy"), so a bounded enum is the correct shape,
  not a dynamic/free-text one.

## D2: Value naming — lowercase snake_case, matching `HostingModel`'s own convention

**Decision**: `custom`, `cots`, `saas`, `legacy` — lowercase, no punctuation, matching
`HostingModel`'s `on_prem`/`cloud`/`saas`/`hybrid` convention exactly (not `PaceLayer`'s
Title-Case convention, nor `TimeClassification`'s Title-Case convention).

**Rationale**: Both conventions coexist on this same model today (compare `PaceLayer`'s
`"Record"`/`"Differentiation"`/`"Innovation"` against `HostingModel`'s lowercase-snake values), so
neither is "the" house style — the deciding factor is picking the *nearer* sibling.
`application_type` and `hosting_model` are both build/deploy classification axes answering
adjacent questions about the same application (see Edge Cases in spec.md: an app can be
`custom`+`saas` simultaneously), so matching `hosting_model`'s exact casing convention keeps the
two visually and semantically paired in the API/UI.

**Alternatives considered**: Title-Case (`"Custom"`, `"COTS"`, `"SaaS"`, `"Legacy"`) matching
`PaceLayer`/`TimeClassification` instead — rejected only because `hosting_model` is the nearer
sibling by subject matter, not because Title-Case is wrong in general; this is a naming-consistency
call, not a functional one, and either would have worked.

## D3: Frontend dimension — fixed enum order, not dynamic/alphabetical

**Decision**: `groupByApplicationType` uses `bucketize()` with a fixed
`["custom", "cots", "saas", "legacy"]` order (labeled Custom-Built / COTS / SaaS / Legacy /
Mainframe), mirroring `groupByHostingModel`/`groupByPaceLayer`'s own fixed-order convention, not
`groupByBusinessUnit`'s dynamic/alphabetical one.

**Rationale**: The value set is a small, fixed, known enum (like hosting model or PACE layer), not
free text with an unbounded domain (like business unit) — `groupByBusinessUnit`'s dynamic-bucket
mechanism exists specifically to handle a field with no closed value set, which doesn't apply here.

## D4: No change to `ApplicationsHeatMap.tsx` (Insights dashboard)

**Decision**: This feature touches only the Application Portfolio screen
(`web/src/portfolio/groupApplications.ts`/`PortfolioPage.tsx`), not the separate Insights heat map
(`web/src/insights/ApplicationsHeatMap.tsx`, ADP-SPEC-019/919).

**Rationale**: The bead's own title scopes this to "Application Portfolio" specifically; the two
screens have independently-defined `Dimension` types (confirmed by direct read — they are not
shared) and independent precedent (ADP-6w4/ADP-9ye, this session's two prior Portfolio-dimension
features, both touched only the Portfolio screen, never the heat map). Extending the heat map too
is explicit future follow-on if ever wanted, not assumed in scope here.

## D5: `list_applications`/router filter parameter added for parity, not because the frontend needs it

**Decision**: `GET /api/v1/applications` gains an `application_type` query filter, mirroring
`hosting_model`'s existing one exactly (same `Optional[str] = Query(default=None)` shape, same
`stmt.where(...)` pattern in the store).

**Rationale**: The frontend's own Group By/Filter by mechanism (`groupApplications.ts`) works
entirely client-side over the full fetched list (confirmed: neither `hosting_model`'s own filter
param nor any of the 5 existing dimensions' values are ever passed as a query string by
`PortfolioPage.tsx` — it always calls the same unfiltered `useApplications()`). The server-side
filter parameter exists for API-direct consumers (scripts, other future callers) as an established
per-field convention on this exact list endpoint, not because this feature's own UI requires it.
Adding it keeps `application_type` a first-class sibling of `hosting_model` at every layer rather
than an inconsistent partial field that only works client-side.

## D6: Export module (`adp.export.application_arch`) inclusion is in-scope, not a separate follow-on

**Decision**: `_serialize_application()` gains an `"application_type": app.application_type` line
alongside its existing `hosting_model` line, in this same feature.

**Rationale**: That serializer is a field-by-field enumeration (confirmed by direct read — it does
not introspect the Pydantic model generically), so a new `Application` field is silently invisible
to file-based AI/tool consumers (ART-III) unless explicitly added. Deferring this to a later bead
would leave the export tree quietly out of sync with the API the moment this feature ships — a gap
of exactly the kind ADP-SPEC-044/045/928 have each been careful to close for their own new fields,
not introduce.
