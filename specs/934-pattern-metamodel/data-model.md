# Data Model: EA Pattern Metamodel (934)

All models live in `adp.patterns.models` and use `ConfigDict(extra="forbid", frozen=True)`. Nothing here is persisted; this spec has no tables. The registry in spec 935 stores the canonical JSON in a JSONB column.

## Constrained string types

| Type | Rule | Example |
|---|---|---|
| `PatternKey` | `^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){1,4}$` | `ea.integration.domain-event-backbone` |
| `RoleKey` | `^[a-z][a-z0-9_]{0,39}$`; `it`, `scope` and `bindings` are reserved (V1) | `domain_app` |
| `RelationshipId` | `^R[0-9]{1,3}$` | `R1` |
| `ConstraintId` | `^C[0-9]{1,3}$` | `C1` |
| `PlateauId` | `^PL[0-9]{1,2}$` | `PL1` |
| `SemVer` | `^(0\|[1-9]\d*)\.(0\|[1-9]\d*)\.(0\|[1-9]\d*)$` | `1.0.0` |
| `CelExpr` | `str`, 1–2000 characters; compile-checked (V7) | |

## Enums (closed value sets)

| Enum | Values | Note |
|---|---|---|
| `PatternKind` | `reference-architecture`, `portfolio-rule`, `transition`, `anti-pattern` | |
| `OwnerRole` | `business`, `enterprise`, `solution`, `technical`, `security`, `infrastructure`, `identity` | Only `enterprise` is accepted (V9) |
| `ElementType` | `business_capability`, `value_stream`, `business_domain`, `application`, `integration`, `technical_capability`, `agent` | GT-1 removes `technology_standard`; GT-2 adds `agent` |
| `RelationshipType` | `publishes`, `consumes`, `delivers`, `serves`, `realizes`, `depends_on`, `integrates_with` | GT-3 removes `owns` |
| `Severity` | `error`, `warning`, `info` | |
| `Polarity` | `require`, `detect` | |
| `PatternRelationType` | `realizes`, `specializes`, `replaces`, `conflicts_with`, `requires`, `alternative_to` | |
| `TransitionStrategy` | `strangler`, `phased-coexistence`, `parallel-run`, `big-bang` | |
| `ViewKind` | `structure`, `conformance`, `transition`, `catalog`, `traceability` | |
| `RenderHintKind` | `prohibited_edge`, `required_edge`, `note` | |

## Models

### `Cardinality`
| Field | Type | Rule |
|---|---|---|
| `min` | `int` | ≥ 0 |
| `max` | `int \| None` | ≥ 1 and ≥ `min`; `None` means unbounded |
| `per` | `RoleKey \| None` | must reference a role (V2) linked by a relationship (V5) |

Input is either the shorthand string (or a bare integer) or the mapping; the published schema accepts both forms. Grammar (`cardinality.py`):
- `N`
- `N..M`
- `N..*`
- `N per <role>`
- `N..M per <role>`

N and M are non-negative integers, with M ≥ max(N, 1). `"0"` alone is rejected because its max would be 0. Output is the shorthand.

### `Role`
`element_type: ElementType`, `cardinality: Cardinality`, `selector: CelExpr | None`, `label: str ≤ 60 | None` (rendered as the title-cased key when absent), `stereotype: str ≤ 30 | None`, `description: str | None`.

### `RoleRelationship`
`id: RelationshipId`, `source: RoleKey`, `target: RoleKey`, `type: RelationshipType`, `via: RoleKey | None`, `label: str ≤ 60 | None`, `required: bool = True`.

### `RenderHint`
`kind: RenderHintKind`, `source: RoleKey | None`, `target: RoleKey | None`, `label: str ≤ 60`.

### `Constraint`
`id: ConstraintId`, `rule: str ≤ 280`, `for_each: RoleKey | None`, `expr: CelExpr`, `polarity: Polarity = require`, `severity: Severity = error`, `render_hint: RenderHint | None`.

### `Motivation`
`context: str`, `problem: str`, `forces / benefits / liabilities: list[str]`, `principles: list[str]`, `controls: list[str]`. The identifiers are unresolved here; 935 resolves them.

### `Plateau` / `Transition`
- `Plateau`: `id: PlateauId`, `name: str ≤ 60`, `description: str | None`, `exit_criteria: list[ConstraintId]` (min 1).
- `Transition`: `from_pattern: PatternKey`, `strategy: TransitionStrategy`, `plateaus: list[Plateau]` (1–10, ordered).

### `PatternRelation`
`type: PatternRelationType`, `target: PatternKey`, `note: str | None`.

### `PatternDefinition` (root)
| Field | Type | Default |
|---|---|---|
| `pattern` | `PatternKey` | required |
| `version` | `SemVer` | required |
| `kind` | `PatternKind` | required |
| `name` | `str ≤ 120` | required |
| `summary` | `str ≤ 500` | required |
| `owner_role` | `OwnerRole` | required |
| `tags` | `list[str]` (≤ 20 items, each ≤ 40) | `[]` |
| `motivation` | `Motivation` | required |
| `roles` | `dict[RoleKey, Role]`, 1–25, ordered | required |
| `relationships` | `list[RoleRelationship]` | `[]` |
| `constraints` | `list[Constraint]` | `[]` |
| `transition` | `Transition \| None` | `None` |
| `relations` | `list[PatternRelation]` | `[]` |
| `known_implementations` | `list[str]` | `[]` |
| `views` | `list[ViewKind]` | `[structure]` |

There is **no `lifecycle` field** (GT-4). Supplying one is rejected as `schema.extra_forbidden`.

### `PatternIssue`
`path: str` (for example `constraints[1].expr`, or `""` for the whole document), `code: str`, `message: str`, `severity: Severity`, `line: int | None`, `column: int | None`. `line`/`column` are filled for YAML syntax errors (YAML position) and CEL errors (position inside the expression).

### `ParseResult`
`definition: PatternDefinition | None`, `issues: list[PatternIssue]`; property `ok = not any(i.severity == error)`.

## Validation rules → issue codes

| Code | Rule | Typical path |
|---|---|---|
| `P0.internal` | Unexpected internal error (last line of defence for FR-012; should never occur) | `""` |
| `P1.too_large` | Raw document > 256 KB (262,144 bytes) | `""` |
| `P2.alias` | Anchor or alias present | `""` (line/col) |
| `P3.multi_document` | More than one YAML document | `""` |
| `P4.not_mapping` | Root is not a mapping | `""` |
| `P5.yaml_syntax` | YAML parse error | `""` (line/col) |
| `schema.<pydantic type>` | Type, enum, regex, length, unknown field (`schema.extra_forbidden`) | Pydantic loc |
| `V1.reserved_role` | Role key `it`/`scope`/`bindings` | `roles.<key>` |
| `V2.unknown_role` | `source`/`target`/`via`/`for_each`/`per`/`render_hint.*` references an undeclared role | e.g. `relationships[0].target` |
| `V3.duplicate_id` | Duplicate relationship, constraint or plateau id | `constraints[2].id` |
| `V4.transition_required` / `V4.transition_forbidden` | Transition present iff kind = transition | `transition` |
| `V4.unknown_criterion` / `V4.not_cumulative` | Plateau criteria exist and are cumulative | `transition.plateaus[1].exit_criteria` |
| `V5.per_unlinked` | `per` role not connected by any relationship | `roles.<key>.cardinality.per` |
| `V6.polarity` / `V6.antipattern_replaces` | Polarity must match kind (`detect` for anti-patterns, `require` otherwise); an anti-pattern cannot `replace` another pattern. (An anti-pattern with a transition is reported as `V4.transition_forbidden`.) | `constraints[0].polarity`, `relations[0]` |
| `V7.compile` / `V7.not_bool` | CEL compile failure / definite non-bool type | `constraints[0].expr`, `roles.<key>.selector` |
| `V8.self_relation` / `V8.duplicate_relation` | Relation targets its own key / duplicate (type, target) | `relations[0]` |
| `V9.owner_role` | `owner_role` ≠ `enterprise` | `owner_role` |

All codes above are `error` severity. Severity `warning` is reserved for 935's import-time notes.
