# Research: Insights Dashboard — Non-Architect Applications Heat Map

No `[NEEDS CLARIFICATION]` markers remain in `spec.md` (both scope questions were resolved via a real
`AskUserQuestion` call before the spec was written). This document records the implementation-level decisions
made while translating the spec into a plan.

## Decision 1: Backend home for the new endpoint

**Decision**: Add `GET /api/v1/portfolio/applications-heatmap` to the existing `src/adp/api/routers/
portfolio.py` router.

**Rationale**: `adp.portfolio` is already ADP's established cross-domain, read-only, no-new-table aggregator
(`/technologies`, `/designs`, `/search`, `/summary`, all plain `sa.text()` reads with no ORM). This feature
adds exactly one more read endpoint of the same shape — extending an existing router with a proven pattern is
lower-risk and avoids package-count creep for what is not a new domain concept.

**Alternatives considered**:
- *New sibling package* (`adp.insights`, mirroring `adp.chat`'s justification for being a new top-level
  package): rejected — `adp.chat` was new because it needed streaming/multi-turn/tool-use plumbing;
  `adp.portfolio` already has everything this feature needs (session dependency, response-model conventions,
  raw-aggregate-query style) with zero new infrastructure required.
- *New endpoint inside `adp.application`*: rejected — the data crosses no new domain boundary that would
  justify living inside the application-registry package specifically, and `adp.portfolio` is the more
  discoverable home for a cross-cutting dashboard query, consistent with its own `/summary` endpoint already
  aggregating from `designs`.

## Decision 2: Gating the cost dimension

**Decision**: Check `is_permitted(user.role, ActionType.READ_APPLICATION_COST)` inline inside the new
endpoint handler (via the existing `get_current_user` dependency), and set the response's `cost` field to
`null` plus a top-level `cost_permitted: false` flag when the caller lacks that permission — rather than
gating the whole endpoint behind a static `Depends(require_action_dep(...))`.

**Rationale**: Three of the four candidate dimensions (health score, business criticality, TIME
classification) are open to every authenticated user today (`list_applications()` has no extra gate). Only
cost is sensitive. A route-level static dependency would either block all four dimensions for a cost-denied
user (wrong — FR-003 requires the other three stay available) or require a second, cost-only route (needless
complexity for one field). The existing precedent for exactly this shape — "mostly open response, one field
individually gated" — is `adp.chat.tools.get_application_cost` (ADP-SPEC-041), which checks
`is_permitted(role, ActionType.READ_APPLICATION_COST)` inline and returns `{"permitted": False}` rather than
raising. This feature follows the same inline-check shape, adapted to a `cost_permitted` boolean the frontend
uses to decide whether "cost" appears in the dimension selector at all (FR-004).

**Alternatives considered**:
- *Static route-level gate*: rejected (see above — would incorrectly block the three open dimensions too).
- *Omit the `cost` field entirely from the JSON when not permitted* (vs. explicit `null` + flag): rejected —
  Pydantic v2 models with `extra="forbid"` (ART-XIII) need a fixed, typed shape per response; an explicit
  `cost_permitted: bool` alongside a nullable `cost` field is simpler for the frontend to branch on than
  detecting field absence, and mirrors the existing `permitted: bool` convention `adp.chat.tools` already
  uses for the identical access-control shape.

## Decision 3: Response shape — all dimensions in one call, not one per dimension

**Decision**: The endpoint returns every application's values for all dimensions (health score, business
criticality, TIME classification, and cost/`cost_permitted`) in a single response. The frontend holds this in
one query and re-colors client-side when the user changes the selected dimension.

**Rationale**: Directly delivers SC-002 ("switching the coloring dimension updates every visible cell in under
1 second") by construction — no network round-trip on dimension switch. At demo scale (a small, fixed
application set per `scripts/seed_retail.py`), returning all fields at once has no meaningful payload-size
cost, unlike a hypothetical production-scale portfolio where a `dimension` query parameter might be
warranted.

**Alternatives considered**:
- *A `dimension` query parameter, one value returned per application*: rejected for v1 — adds a network
  round-trip to every dimension switch, working against SC-002, for no benefit at the confirmed demo scale
  (Ground-Truth Correction 6).

## Decision 4: The cost value itself

**Decision**: Use `ApplicationCost.tco` (the existing computed total-cost-of-ownership field, ADP-SPEC-038
US4 — `Σ(one_time) + Σ(annual) × horizon_years` across every cost bucket) as the single scalar for the cost
dimension, sourced via a join against the existing `application_cost` table. Applications with no cost record
render as "unclassified" (FR-005), exactly like applications with no `health_score`/`business_criticality`/
`time_classification` set.

**Rationale**: `tco` is already the one normalized, single-number summary of an application's cost that ADP
computes today (`adp.application.store.get_application_cost`) — no new aggregation logic needed, and it
matches what `adp.chat.tools.get_application_cost` already exposes as "the" cost figure for an application.

**Alternatives considered**:
- *Expose `run_total`/`change_total` as separate selectable sub-dimensions*: rejected as unnecessary
  complexity for v1 — the spec's resolved clarification names "cost" as one dimension, not a further-decomposed
  set; `tco` is the natural single figure.

## Decision 5: No domain/hierarchy grouping in the grid

**Decision**: The heat map is a flat grid, one cell per application, sorted by name — no grouping (e.g. by
business unit or hosting model).

**Rationale**: Unlike `ADP-3up.1`'s still-open question of whether to group its capability grid by business
domain (capabilities have a natural L1/L2/L3 hierarchy), applications have no equivalent single hierarchical
axis that every application participates in — `owning_business_unit` is optional/free-text, not a structured
tree. A flat, sortable grid is the simpler, unambiguous default for v1, consistent with FR-001's plain
"every application as one cell" requirement.

**Alternatives considered**:
- *Group by `owning_business_unit`*: deferred, not rejected outright — a reasonable fast-follow once the flat
  grid ships, but not required by any resolved requirement in this spec.
