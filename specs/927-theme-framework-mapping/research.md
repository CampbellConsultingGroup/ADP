# Phase 0 Research: Theme–Framework Mapping

**Feature**: 927-theme-framework-mapping
**Date**: 2026-08-26

No `[NEEDS CLARIFICATION]` markers remained in spec.md going into this phase (the one open question —
UI scope — was resolved during `/speckit.specify`: data-model-and-API-only). The decisions below resolve
implementation-level ambiguity the spec deliberately left to plan.md, each by direct analogy to an
already-shipped precedent rather than inventing a new pattern.

---

## D1 — Package placement: `adp.strategy` owns the link, `adp.compliance.router` gets the reverse lookup

**Decision**: The new `theme_framework_links` table, its store functions, and the write/forward-read
routes all live in `adp.strategy` (extending `store.py`/`router.py`, alongside the existing
`_themes`/theme CRUD functions) — not in `adp.compliance`. The reverse lookup ("given a Framework, which
Themes") lives on `adp.compliance.router`, importing `adp.strategy.store` through the `_get_strategy_session()`
dependency `adp.compliance.router` already has (added for `925-strategy-compliance-linkage`'s own
`GET /controls/{control_id}/objectives` — reused here verbatim, no new dependency code).

**Rationale**: Directly analogous to `925-strategy-compliance-linkage`'s own D2: a Strategy entity
(`StrategicTheme`) gaining a traceability link into another domain's already-registry-owned entity
(`RegulatoryFramework`). `adp.strategy` is already the domain that reaches into other domains (Business,
Application, Design, and now Compliance via `objective_control_links`) through its own read-only mirror
tables, and other domains' *routers* (not their store packages) reach back into `adp.strategy.store` for
reverse lookups. Following the identical shape here — a fourth application of the same asymmetry — means
this feature introduces no new architectural pattern.

`adp.strategy.store` gains a narrow, read-only mirror of `regulatory_frameworks` (`id` + `name` only,
matching the existing `_designs`/`_applications`/`_controls_mirror` idiom exactly) for the existence check
on link creation. No new cross-package Python import is introduced beyond what `925-strategy-compliance-linkage`
already established for the identical class of reverse lookup.

**Alternatives considered**: Own the table in `adp.compliance` instead, on the theory that
`RegulatoryFramework` is the more heavyweight/authoritative side. Rejected — unlike `ControlMapping`
(which is fundamentally *about* the Control, COMPLY-02's own placement rationale), a Theme–Framework tag
is not more naturally "about" the framework than the theme; it is symmetric coarse grouping. Given no
strong directional pull either way, matching the already-established `adp.strategy`-reaches-out asymmetry
is the lower-risk, more consistent choice over introducing a second direction of cross-package reach.

## D2 — Response shape: `framework_ids: list[str]` on `StrategicTheme`, full summaries on the reverse lookup

**Decision**: `StrategicTheme` gains `framework_ids: list[str] = []`, populated live on every read
(`_row_to_theme`, `create_theme`, `update_theme`) — a plain list of ids, exactly mirroring
`StrategicObjective.control_ids: list[str] = []` (925). `RegulatoryFramework`'s own model is **not**
touched. The reverse lookup, `GET /api/v1/compliance/frameworks/{framework_id}/themes`, returns a full
`StrategicThemeListResponse` (the existing list-response model, reused unmodified) — mirroring
`list_objectives_for_control`'s own precedent of returning full summaries on the reverse side rather than
a bare id list.

**Rationale**: This asymmetry (forward = id list embedded on the owning side's model; reverse = full
summaries via a dedicated endpoint) is not a new design choice — it is the exact shape 925 already
established for `ObjectiveControlMapping`, reused verbatim rather than re-litigated.

**Alternatives considered**: Embed `theme_ids: list[str]` on `RegulatoryFramework` symmetrically.
Rejected — `Control` did not gain an `objective_ids` field in 925 either; the reverse side stays a
dedicated endpoint, not a model addition, keeping `RegulatoryFramework`'s already-widely-used read model
untouched by a feature that only lightly relates to it.

## D3 — Duplicate-link and not-found handling

**Decision**: Reuse `adp.strategy.store`'s existing `DuplicateLinkError` (→ HTTP 409) and
`LinkNotFoundError` (→ HTTP 404) exactly as `link_objective_control`/`unlink_objective_control` already
do — no new exception type, no `INSERT ... ON CONFLICT` upsert.

**Rationale**: A Theme–Framework tag carries no fields beyond the two FK columns and `created_at` — there
is nothing to update in place on a re-link attempt, the same reasoning 925's own D5 already established
for `ObjectiveControlMapping`/`InitiativeControlMapping`. A plain `INSERT` with a caught unique-violation
is the correct match, not COMPLY-02's richer-payload upsert (which exists because `ControlMapping` *does*
carry a mutable `compliance_status` payload that a re-post might legitimately be updating — this link has
no such payload).

## D4 — No new permission, no new migration column elsewhere

**Decision**: All writes go through the existing `("/api/v1/strategy/", ActionType.WRITE_BUSINESS_ARCH)`
prefix rule already registered in `enforcement.py` — zero `enforcement.py` change, zero new `ActionType`,
zero `PERMISSIONS_VERSION` bump. The reverse-lookup route is ungated beyond general platform read access,
matching `GET /controls/{control_id}/objectives`'s own precedent ("an abstract Control carries no
target-entity sensitivity of its own") — a `RegulatoryFramework` carries none either; framework reads are
already open to any authenticated user (COMPLY-01).

**Rationale**: Both sides of this link (`StrategicTheme`, `RegulatoryFramework`) are already writable by
the identical persona set (the three architect personas plus Platform Admin hold both
`WRITE_BUSINESS_ARCH` and `WRITE_COMPLIANCE`) — introducing a link between them creates no new,
weaker write path, so no new gate is warranted.
