# PATTERN-01 — Pattern metamodel & YAML format

**Bundle:** PATTERN · **Package:** `adp.patterns` · **Depends on:** — · **Status:** draft

## What

1. A Pydantic v2 metamodel, `PatternDefinition`, that is the canonical in-memory form of an EA pattern.
2. A YAML authoring format that parses into it, including cardinality shorthand.
3. Structural validation (cross-references, kind rules) plus **CEL compile checks** on every expression.
4. A deterministic canonical serialization (JSON for digesting, YAML for export) and a generated JSON Schema for editor autocomplete.

There is no persistence and no evaluation in this spec. Everything here is pure functions.

## Why

Every later spec consumes `PatternDefinition`. Fixing the shape first, and validating it in isolation against fixture patterns, keeps the registry (02), the engine (03) and the renderers (04, 05) from each inventing their own interpretation.

## Files

| File | Contents |
|---|---|
| `src/adp/patterns/models.py` | Boundary types below |
| `src/adp/patterns/parse.py` | `parse_pattern_yaml()`, `to_canonical_json()`, `to_canonical_yaml()`, `compute_digest()` |
| `src/adp/patterns/cel.py` | `CelEngine` protocol + adapter; `compile_check()` |
| `src/adp/patterns/schema/pattern.schema.json` | Generated from `PatternDefinition.model_json_schema()`; committed; CI fails if stale |
| `tests/patterns/fixtures/*.yaml` | Fixture patterns (valid and invalid) |

## Models

All models use `ConfigDict(extra="forbid", frozen=True)`.

### Enums

| Enum | Values |
|---|---|
| `PatternKind` | `reference-architecture`, `portfolio-rule`, `transition`, `anti-pattern` |
| `OwnerRole` | `business`, `enterprise`, `solution`, `technical`, `security`, `infrastructure`, `identity` (only `enterprise` accepted in this bundle — see validation V9) |
| `PatternLifecycle` | `draft`, `proposed`, `current`, `deprecated`, `decommissioned` (ADP vocabulary) |
| `ElementType` | `business_capability`, `value_stream`, `business_domain`, `application`, `integration`, `technical_capability`, `technology_standard` — **each must map to an existing ADP registry entity** (PATTERN-03 snapshot) |
| `RelationshipType` | `publishes`, `consumes`, `delivers`, `owns`, `realizes`, `serves`, `depends_on`, `integrates_with` |
| `Severity` | `error`, `warning`, `info` |
| `Polarity` | `require` (violation when expr is false), `detect` (match when expr is true) |
| `PatternRelationType` | `realizes`, `specializes`, `replaces`, `conflicts_with`, `requires`, `alternative_to` |
| `TransitionStrategy` | `strangler`, `phased-coexistence`, `parallel-run`, `big-bang` |
| `ViewKind` | `structure`, `conformance`, `transition`, `catalog`, `traceability` |

### Core types

| Type | Field | Type / rule |
|---|---|---|
| `PatternKey` | — | `str`, regex `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){1,4}$` e.g. `ea.integration.domain-event-backbone` |
| `RoleKey` | — | `str`, regex `^[a-z][a-z0-9_]{0,39}$` |
| `ConstraintId` | — | `str`, regex `^C[0-9]{1,3}$` |
| `SemVer` | — | `str`, strict `MAJOR.MINOR.PATCH`. Patterns are software-like artifacts, so semver is appropriate here (unlike regulatory frameworks — see COMPLY-01 addendum) |
| `CelExpr` | — | `str`, 1–2000 chars; compile-checked (V7) |

### `Cardinality`

| Field | Type | Notes |
|---|---|---|
| `min` | `int ≥ 0` | |
| `max` | `int ≥ 1 \| None` | `None` = unbounded |
| `per` | `RoleKey \| None` | "N of this role for each element bound to `per`". Requires a declared relationship between the two roles (V5) |

YAML shorthand, parsed by a `BeforeValidator`:

| Shorthand | Parses to |
|---|---|
| `"1"` | `min=1, max=1` |
| `"0..1"` | `min=0, max=1` |
| `"2..*"` | `min=2, max=None` |
| `"1 per capability"` | `min=1, max=1, per="capability"` |

The longhand mapping form is also accepted. Canonical export always writes the shorthand.

### `Role`

| Field | Type | Notes |
|---|---|---|
| `element_type` | `ElementType` | |
| `cardinality` | `Cardinality` | |
| `selector` | `CelExpr \| None` | Evaluated with `it` = candidate element; filters candidates in scope |
| `label` | `str` (≤ 60) | Render label; defaults to title-cased key |
| `stereotype` | `str \| None` (≤ 30) | Rendered as `«stereotype»` |
| `description` | `str \| None` | |

### `RoleRelationship`

| Field | Type | Notes |
|---|---|---|
| `id` | `str` regex `^R[0-9]{1,3}$` | |
| `source` | `RoleKey` | must exist (V2) |
| `target` | `RoleKey` | must exist (V2); `source == target` allowed (e.g. app→app) |
| `type` | `RelationshipType` | |
| `via` | `RoleKey \| None` | Mediating role, e.g. the backbone (V2) |
| `label` | `str \| None` (≤ 60) | |
| `required` | `bool = True` | Required relationships generate implicit constraints in PATTERN-03 |

### `RenderHint` (optional on a constraint)

Lets a constraint appear in diagrams without the renderer having to parse CEL.

| Field | Type |
|---|---|
| `kind` | `Literal["prohibited_edge", "required_edge", "note"]` |
| `source` | `RoleKey \| None` |
| `target` | `RoleKey \| None` |
| `label` | `str` (≤ 60) |

### `Constraint`

| Field | Type | Notes |
|---|---|---|
| `id` | `ConstraintId` | unique within pattern (V3) |
| `rule` | `str` (≤ 280) | Human-readable statement; shown in findings |
| `for_each` | `RoleKey \| None` | If set, `expr` is evaluated once per bound element with `it` bound; offenders become finding refs. If `None`, evaluated once globally |
| `expr` | `CelExpr` | Must evaluate to `bool` |
| `polarity` | `Polarity = require` | Must be `detect` for every constraint when `kind = anti-pattern`, and `require` otherwise (V6) |
| `severity` | `Severity = error` | |
| `render_hint` | `RenderHint \| None` | |

### `Motivation`

| Field | Type | Notes |
|---|---|---|
| `context` | `str` | |
| `problem` | `str` | |
| `forces` | `list[str]` | |
| `benefits` | `list[str]` | |
| `liabilities` | `list[str]` | |
| `principles` | `list[str]` | Knowledge-base principle identifiers; resolved to FKs in PATTERN-02 |
| `controls` | `list[str]` | COMPLY-01 control identifiers; resolved in PATTERN-02 |

### `Plateau` and `Transition`

| Type | Field | Type / rule |
|---|---|---|
| `Plateau` | `id` | `str` regex `^PL[0-9]{1,2}$` |
| | `name` | `str` (≤ 60) |
| | `description` | `str \| None` |
| | `exit_criteria` | `list[ConstraintId]`, non-empty; each must exist (V4) |
| `Transition` | `from_pattern` | `PatternKey` (normally an anti-pattern) |
| | `strategy` | `TransitionStrategy` |
| | `plateaus` | `list[Plateau]`, 1–10, **ordered**. Exit criteria must be cumulative: each plateau's set ⊇ the previous one's (V4) |

### `PatternRelation`

| Field | Type |
|---|---|
| `type` | `PatternRelationType` |
| `target` | `PatternKey` (≠ own key, V8) |
| `note` | `str \| None` |

### `PatternDefinition` (root)

| Field | Type | Notes |
|---|---|---|
| `pattern` | `PatternKey` | |
| `version` | `SemVer` | |
| `kind` | `PatternKind` | |
| `name` | `str` (≤ 120) | |
| `summary` | `str` (≤ 500) | |
| `owner_role` | `OwnerRole` | |
| `lifecycle` | `PatternLifecycle = draft` | **Informational on import.** The registry (02) owns lifecycle; an imported value other than `draft` is ignored with a warning |
| `tags` | `list[str]` (≤ 20) | |
| `motivation` | `Motivation` | |
| `roles` | `dict[RoleKey, Role]`, 1–25 | Declaration order is preserved and drives render order |
| `relationships` | `list[RoleRelationship]` | |
| `constraints` | `list[Constraint]` | |
| `transition` | `Transition \| None` | |
| `relations` | `list[PatternRelation]` | |
| `known_implementations` | `list[str]` | Application identifiers (exemplars); resolved in 03 |
| `views` | `list[ViewKind]` | Default: `[structure]` |

## Validation rules (`model_validator(mode="after")`)

| # | Rule |
|---|---|
| V1 | Role keys are unique (guaranteed by dict) and the reserved names `it`, `scope`, `bindings` are rejected |
| V2 | Every `source`, `target`, `via`, `for_each`, `per` and `render_hint` role reference exists in `roles` |
| V3 | Relationship ids are unique; constraint ids are unique |
| V4 | `transition` is required iff `kind = transition`. Every plateau's exit criteria exist and are cumulative |
| V5 | A role with `cardinality.per = X` must have at least one relationship connecting it with `X` (either direction) |
| V6 | `kind = anti-pattern` → all constraints `polarity = detect`, and no `transition` and no `replaces` relation. Other kinds → all `require` |
| V7 | Every `selector` and `expr` compiles under `CelEngine.compile_check()` with the declared variable set (see the CEL section). Errors carry the YAML path, e.g. `constraints[1].expr` |
| V8 | No relation targets its own `pattern` key; no duplicate `(type, target)` pairs |
| V9 | `owner_role` must be `enterprise` in this bundle (relaxed by a future spec) |

## CEL

- **Adapter boundary:** `CelEngine` is a `Protocol` with `compile_check(expr, variables) -> list[CelError]` and `evaluate(program, activation) -> Any`. The engine is chosen by a setting so the library can be swapped (OQ-1).
- **Declared variables** for the compile check: `it` (dyn), `bindings` (map<string, list<dyn>>), `scope` (map<string, list<dyn>>). Custom functions: `role(string) → list<string>` (ids bound to a role) and `bound(dyn, string) → bool`. Their semantics are defined in PATTERN-03; here they are only declared, so expressions compile.
- **Safety:** CEL is non-Turing-complete, so expressions are accepted from YAML without sandboxing beyond the PATTERN-03 cost limit.

## YAML parsing

- Use `yaml.safe_load` only. Reject documents over 256 KB. **Reject YAML aliases and anchors** (custom loader) to prevent alias expansion bombs.
- One pattern per file. The filename convention `<pattern>@<version>.yaml` is checked only by the repo lint (warning, not a parse error).
- Parse errors and validation errors are returned as one list of `PatternIssue{path, code, message, severity}`. Never raise past `parse_pattern_yaml()`.

## Canonical forms

| Function | Rule |
|---|---|
| `to_canonical_json(defn)` | `model_dump(mode="json", exclude_defaults=False)`, `sort_keys=True`, no whitespace, **but** `roles` and all lists keep declared order (order is semantic for rendering and plateaus) |
| `compute_digest(defn)` | `sha256` of the canonical JSON **excluding `lifecycle`** (lifecycle is registry state, not content) |
| `to_canonical_yaml(defn)` | Fixed key order matching the field order above; cardinality written as shorthand; block style; no aliases |

**Round-trip law:** `parse(to_canonical_yaml(parse(x))) == parse(x)`, and the digest is stable.

## Reference fixture — `ea.integration.domain-event-backbone@1.0.0.yaml`

```yaml
pattern: ea.integration.domain-event-backbone
version: 1.0.0
kind: reference-architecture
name: Domain Event Backbone
summary: Cross-domain data sharing goes through a governed event backbone; no direct cross-domain integration.
owner_role: enterprise
tags: [integration, event-driven]
motivation:
  context: Business domains need each other's data changes.
  problem: Point-to-point integrations create coupling and untraceable data lineage.
  forces: [Domain autonomy, Data consistency, Auditability]
  benefits: [Decoupled release cycles, Single lineage point]
  liabilities: [Eventual consistency, Backbone becomes critical platform]
  principles: [P-API-FIRST, P-NO-P2P]
  controls: []
roles:
  backbone:
    element_type: application
    cardinality: "1"
    stereotype: platform
    selector: "it.technology_standard_status == 'approved' && 'event-backbone' in it.tags"
  domain_app:
    element_type: application
    cardinality: "2..*"
    selector: "it.time_disposition in ['invest', 'tolerate']"
  cross_domain_integration:
    element_type: integration
    cardinality: "0..*"
    selector: "it.source.domain_id != it.target.domain_id"
relationships:
  - { id: R1, source: domain_app, target: backbone, type: publishes }
  - { id: R2, source: backbone, target: domain_app, type: delivers }
constraints:
  - id: C1
    rule: Cross-domain integrations must be mediated by the backbone.
    for_each: cross_domain_integration
    expr: "it.target.id in role('backbone') || it.source.id in role('backbone')"
    severity: error
    render_hint: { kind: prohibited_edge, source: domain_app, target: domain_app, label: "no direct cross-domain" }
  - id: C2
    rule: Applications marked Eliminate must not gain backbone subscriptions.
    for_each: domain_app
    expr: "it.time_disposition != 'eliminate'"
    severity: warning
relations:
  - { type: replaces, target: ea.integration.point-to-point-mesh }
  - { type: requires, target: ea.data.system-of-record-per-capability }
views: [structure, conformance, catalog]
```

## Tests

| Test | Asserts |
|---|---|
| `test_fixture_valid_parses` | Each `fixtures/valid/*.yaml` parses with zero `error` issues |
| `test_fixture_invalid_codes` | Each `fixtures/invalid/<code>.yaml` yields exactly the expected issue code (one fixture per V1–V9) |
| `test_cardinality_shorthand` | Table-driven: every shorthand row above, plus invalid forms (`"*..1"`, `"1 per"`, `"0"`) |
| `test_round_trip_stable` | Round-trip law plus digest equality for all valid fixtures |
| `test_digest_ignores_lifecycle` | Changing only `lifecycle` leaves the digest unchanged |
| `test_yaml_alias_rejected` | A document containing `&a`/`*a` is rejected |
| `test_cel_compile_errors_carry_path` | A broken `expr` reports `constraints[0].expr` |
| `test_schema_artifact_current` | The committed `pattern.schema.json` equals the freshly generated schema |

## Out of scope

Persistence, evaluation, rendering, variants/option groups, non-EA owner roles, multi-document YAML.

## Open questions

| # | Question |
|---|---|
| OQ-1 | **CEL library:** `cel-python` (pure Python, Cloud Custodian lineage), `common-expression-language` (Rust `cel-interpreter` wrapper), or Google's `cel-expr-python` (open-sourced March 2026). Spike all three against the fixture expressions, custom-function registration (`role()`, `bound()`), compile-time error positions, and cost limits before PATTERN-03. The adapter keeps the choice reversible. |
| OQ-2 | Should `ElementType` include `strategic_objective` and `control` so patterns can bind to Strategy and Compliance entities directly, or is linking them via `motivation` enough? |
| OQ-3 | Is a cap of 25 roles per pattern right, or should large reference architectures be composed through `specializes`/`requires` instead? |
