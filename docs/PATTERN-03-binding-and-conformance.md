# PATTERN-03 — Binding & conformance engine

**Bundle:** PATTERN · **Package:** `adp.patterns` · **Depends on:** PATTERN-01, PATTERN-02 · **Status:** draft

## What

1. **Adoption:** an EA declares that a pattern applies to a scope (a business domain, an explicit set of applications, or the whole portfolio), optionally pinning specific elements to roles.
2. **Snapshot:** a read-only `PortfolioSnapshot` built from the existing registries.
3. **Pure engine:** resolve role bindings, evaluate the implicit and declared constraints, and produce a `ConformanceReport`.
4. **Derived status:** conformance status and transition plateau come from pure functions. **Computed on read, never stored.**
5. **Discovery:** evaluate anti-patterns across the portfolio without an adoption.

## Why

This turns patterns from documentation into a governance signal: "Claims domain is non-conformant with Domain Event Backbone: 3 direct cross-domain integrations." It follows the same derived-over-stored principle as `compute_compliance_status()` and `compute_evolution_stage()`.

> **Naming:** "adoption", not "application", to avoid colliding with ADP's Application registry entity.

## Migration — `NNNN_ea_pattern_adoption.py`

### `ea_pattern_adoption`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `pattern_key` | `TEXT NOT NULL` FK → `ea_pattern` `ON DELETE CASCADE` | |
| `pinned_version_id` | `UUID NULL` FK → `ea_pattern_version` `ON DELETE RESTRICT` | `NULL` = follow the family's `current` version |
| `scope_type` | `TEXT NOT NULL` | `business_domain`, `application_set`, `portfolio` |
| `scope_ref` | `UUID NULL` | Business domain id when `scope_type = business_domain` |
| `name` | `TEXT NOT NULL` | |
| `created_at` / `created_by` | | |

CHECKs: `ck_ea_pattern_adoption_scope_type`; `ck_ea_pattern_adoption_scope_ref` (`scope_ref IS NOT NULL` iff `scope_type = 'business_domain'`).
Unique: `uq_ea_pattern_adoption_scope` on (`pattern_key`, `scope_type`, `COALESCE(scope_ref, '00000000-…')`) — one adoption per pattern per scope.

### `ea_pattern_adoption_member` (for `application_set`)

Composite PK (`adoption_id`, `application_id`). FKs → adoption and the application registry, both `ON DELETE CASCADE`.

### `ea_pattern_adoption_binding` (explicit pins)

| Column | Notes |
|---|---|
| `adoption_id` | FK → adoption, `ON DELETE CASCADE` |
| `role_key` | `TEXT` |
| `element_type` | `TEXT` + CHECK on the `ElementType` values |
| `element_id` | `UUID` — **polymorphic, no FK** |

Composite PK (`adoption_id`, `role_key`, `element_id`).

> **Cardinality / FK decision is explicit:** the binding target is polymorphic across `ElementType`. That is the same trade-off as COMPLY-02's typed-join-tables-vs-polymorphic decision. **This spec defers to whatever COMPLY-02 decides.** Until then: polymorphic, plus a store-level existence check, plus a dangling-pin finding at evaluation time (`B3` below). See OQ-1.

## Snapshot — `PortfolioSnapshot`

Built by `store.build_snapshot(scope, caller_permissions)`. It is the **only** input the engine sees besides the definition and the pins. Elements are plain dicts, so CEL can address them.

| ElementType | Attributes exposed to CEL | Source (**verify each field name against the current registry**) |
|---|---|---|
| `application` | `id, name, domain_id, lifecycle, time_disposition, r7_disposition, tags, technology_standard_status` + gated `risk_rating, annual_cost` | `adp.application` registry |
| `integration` | `id, source{id, domain_id}, target{id, domain_id}, protocol, style, mediator_id?` | `adp.application` integrations |
| `business_capability` | `id, name, level, parent_id, strategic_relevance, maturity` | `adp.business` |
| `value_stream` | `id, name, stage_ids` | `adp.business` |
| `business_domain` | `id, name, risk_classification` | `adp.business` |
| `technical_capability` | `id, name` | `adp.application` |
| `technology_standard` | `id, name, status` | technical standards |

Plus `edges: list[Edge{source_id, target_id, kind}]`: the registry relationships available as evidence for role relationships (table below).

**Sensitivity:** gated attributes (risk, cost, governance) are **omitted** from the snapshot unless the caller holds the existing sensitive-read permission. Expressions that touch an omitted field produce a `field_unavailable` finding rather than a false pass or fail.

### Relationship evidence

| `RelationshipType` | Evidence in the snapshot | If no evidence source exists |
|---|---|---|
| `publishes`, `consumes`, `delivers`, `integrates_with` | `integration` records between the bound applications (direction-aware for publishes/consumes/delivers) | — |
| `realizes` | application → technical capability link | `unverifiable` info finding |
| `serves`, `owns` | application → business capability link (**verify that one exists**) | `unverifiable` info finding |
| `depends_on` | Integration in either direction | — |

## Engine — `adp/patterns/engine.py` (pure)

```python
def resolve_bindings(defn: PatternDefinition, snap: PortfolioSnapshot,
                     pins: list[Pin], cel: CelEngine) -> BindingResult: ...
def evaluate_constraints(defn: PatternDefinition, bindings: BindingResult,
                         snap: PortfolioSnapshot, cel: CelEngine,
                         limits: EvalLimits) -> list[Finding]: ...
def compute_conformance_status(findings: list[Finding],
                               bindings: BindingResult) -> ConformanceStatus: ...
def compute_transition_plateau(defn: PatternDefinition,
                               findings: list[Finding]) -> PlateauState | None: ...
def discover(defn: PatternDefinition, snap: PortfolioSnapshot,
             cel: CelEngine, limits: EvalLimits) -> DiscoveryReport: ...
```

### Binding resolution

For each role, in declared order:
1. **Candidates** = snapshot elements of `role.element_type` within scope. For a domain scope, an integration counts as in scope if either endpoint is in the domain.
2. **Selector filter:** keep the candidates where `selector` evaluates to `true` with `it = candidate`. If there is no selector, keep all candidates.
3. **Pins:** add the pinned elements. A pin that fails the selector is kept, with finding `B2 pin_fails_selector` (warning). A pin whose element is absent from the snapshot produces `B3 dangling_pin` (error).
4. Result: `bindings: dict[RoleKey, list[ElementRef]]`, ordered by element `name`, then `id`, for determinism.

### Implicit constraints (generated, evaluated before declared ones)

| Id | Check | Severity |
|---|---|---|
| `K:<role>` | Bound count is within `cardinality.min..max` | error |
| `K:<role>/<per>` | For each element bound to `per`: the number of related elements bound to `role` (via snapshot edges for the declared relationship) is within `min..max` | error |
| `E:<rel_id>` | For a `required` relationship: every source-role element has ≥ 1 evidence edge to a target-role element (through the `via` element if set) | error, or `unverifiable` info if there is no evidence source |

### CEL activation

| Variable / function | Meaning |
|---|---|
| `it` | Current element (selector, or a `for_each` constraint) |
| `bindings` | `map<RoleKey, list<element>>` |
| `scope` | `{applications, integrations, capabilities, …}` lists in scope |
| `role(k)` | `list<string>` of the element ids bound to role `k` |
| `bound(e, k)` | `true` if element `e` is bound to role `k` |

**Semantics:**

| Polarity | `for_each` set | Result |
|---|---|---|
| `require` | yes | Each element where `expr == false` is a violation (one finding, all offenders listed in `element_refs`) |
| `require` | no | `expr == false` → one violation |
| `detect` | yes | Each element where `expr == true` is a match |
| `detect` | no | `expr == true` → one match |

A non-bool result → `evaluation_error`. A missing key → `field_unavailable` when the field is gated, otherwise `evaluation_error`.

**Limits (`EvalLimits`):** max 50 000 element evaluations per report and a per-expression cost/time limit supported by the chosen CEL library (PATTERN-01 OQ-1). When a limit is exceeded, the report includes finding `L1 limit_exceeded` (error) and evaluation stops for that constraint only.

### Finding

| Field | Type |
|---|---|
| `code` | `str` (`C1`, `K:domain_app`, `E:R1`, `B2`, `L1`, …) |
| `kind` | `violation`, `match`, `binding`, `evaluation_error`, `field_unavailable`, `unverifiable`, `limit` |
| `severity` | `Severity` |
| `rule` | `str` (constraint `rule` text, or a generated message) |
| `element_refs` | `list[ElementRef{type, id, name}]` (capped at 100, with `truncated: bool`) |

### `compute_conformance_status` — minimum aggregation (first match wins)

| Order | Condition | Status |
|---|---|---|
| 1 | No role has ≥ 1 binding | `not_applicable` |
| 2 | Any `error`-severity `violation`, `binding` or `limit` finding | `non_conformant` |
| 3 | Any `evaluation_error`, or `field_unavailable` on an `error`-severity constraint | `indeterminate` |
| 4 | Any `warning`-severity violation | `conformant_with_warnings` |
| 5 | Otherwise | `conformant` |

`unverifiable` and `info` findings never lower the status.

### `compute_transition_plateau`

Only for `kind = transition`. Walk the plateaus in order. A plateau is **reached** if none of its `exit_criteria` constraint ids has a violation, evaluation error, or field-unavailable finding. Return the highest consecutive reached plateau (`PlateauState{reached: PlateauId | None, next: PlateauId | None, blocking: list[ConstraintId]}`). Because the criteria are cumulative (PATTERN-01 V4), "consecutive" and "highest" agree. The walk stops at the first unreached plateau.

### `discover` (anti-patterns)

Only for `kind = anti-pattern`. Scope = portfolio. Bindings come from selectors (no pins). Returns `DiscoveryReport{matches: list[Finding], match_count, evaluated_at}`. There is no status; a match is information to act on, not a verdict.

## Models (additions)

`PatternAdoptionCreate`, `PatternAdoption`, `Pin`, `BindingResult`, `Finding`, `ElementRef`, `ConformanceStatus` (enum above), `PlateauState`, `ConformanceReport{adoption_id, pattern_key, version, digest, evaluated_at, bindings_summary: dict[RoleKey, int], findings, status, plateau}`, `DiscoveryReport`, `EvalLimits`. All `extra="forbid"`.

## Store

| Function | Notes |
|---|---|
| `create_adoption`, `delete_adoption`, `set_members`, `set_pins` | Pins validated: the role exists in the resolved version, `element_type` matches the role, and the element exists (polymorphic existence check, dispatched by type) |
| `resolve_adoption_version(adoption)` | Pinned version, otherwise the family's `current` version. If neither exists, the report returns `not_applicable` with finding `B1 no_current_version` |
| `build_snapshot(scope, perms)` | One read query per element type in scope (no N+1) |

## Router — prefix `/api/v1/patterns`

| Method & path | Action | Notes |
|---|---|---|
| `POST /adoptions` | `PATTERN_GOVERN` | |
| `GET /adoptions?pattern_key=&scope_type=` | read | |
| `PUT /adoptions/{id}/members` · `PUT /adoptions/{id}/pins` | `PATTERN_GOVERN` | |
| `DELETE /adoptions/{id}` | `PATTERN_GOVERN` | |
| `GET /adoptions/{id}/conformance` | read | Computed on request |
| `POST /evaluate` | read (POST, no mutation) | Body: `{yaml \| version_id, scope}`. Dry-run for authoring; works on unsaved drafts. **Add an explicit allowlist entry** so the mutating-route completeness test treats it as read-only |
| `GET /{key}/discover?version=` | read | Anti-pattern kinds only; otherwise `422` |

## Tests

Engine tests run against **in-memory snapshot fixtures only** (no DB). These are the validation-before-delivery gate.

| Test | Asserts |
|---|---|
| `test_bindings_selector_filter` | Selector keeps/drops as expected; deterministic order |
| `test_pin_fails_selector_and_dangling` | `B2` warning, `B3` error |
| `test_cardinality_implicit` | min/max/unbounded/`per`, table-driven |
| `test_required_relationship_evidence` | With and without integration evidence; the `via` path; `unverifiable` for `serves` when no link source exists |
| `test_polarity_matrix` | All four rows of the semantics table |
| `test_status_aggregation_order` | Each row of the status table, plus precedence when several conditions hold |
| `test_field_unavailable_gated` | A caller without the sensitive permission → `indeterminate`, not `non_conformant`/`conformant` |
| `test_plateau_progression` | 0, 1, all plateaus reached; `blocking` lists the right constraint ids |
| `test_limits` | `L1` raised; other constraints still evaluated |
| `test_reference_fixture_conformance` | PATTERN-01 fixture vs. a snapshot with one direct cross-domain integration → `non_conformant`, `C1` refs that integration |
| `test_discover_point_to_point_mesh` | Anti-pattern fixture finds the expected matches |
| `test_adoption_scope_unique` / `test_pin_type_mismatch_rejected` | Store-level |
| `test_conformance_not_persisted` | No table stores status (schema introspection guard) |

## Out of scope

Scheduled or continuous evaluation, conformance history/trends, notifications, auto-remediation suggestions, AI explanations of findings, rollup into the Governance dashboard (follow-on, akin to COMPLY-04).

## Open questions

| # | Question |
|---|---|
| OQ-1 | Typed binding tables per `ElementType` vs. the polymorphic `element_id` — align with the COMPLY-02 outcome. |
| OQ-2 | (= OQ-B3) Should conformance be allowed without an adoption (implicit portfolio-wide evaluation of every `current` pattern), or does that produce noise EAs won't act on? |
| OQ-3 | Should an adoption that follows `current` warn when the current version changes and the status flips? This needs history, which is out of scope. |
| OQ-4 | Does ADP have an application → business capability link to serve as evidence for `serves`/`owns`? If not, should these relationship types be dropped from `RelationshipType` until it does? |
| OQ-5 | Is the 50 000-evaluation default right for the estate size? Measure against the seeded dataset before fixing. |
| OQ-6 | Should conformance reports be rolled up into the Governance & Standards "at risk" tile? (Would make this a COMPLY-04-style read-side spec.) |
