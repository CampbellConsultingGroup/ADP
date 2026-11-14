# Contract: `adp.patterns` public Python API (934)

This is the stable surface that specs 935 (registry), 936 (engine) and 937 (CALM export) build on. Everything else in the package is private.

```python
from adp.patterns import (
    # models
    PatternDefinition, Role, Cardinality, RoleRelationship, Constraint, Motivation,
    Transition, Plateau, PatternRelation, RenderHint, PatternIssue, ParseResult,
    PatternKind, ElementType, RelationshipType, Severity, Polarity,
    PatternRelationType, TransitionStrategy, ViewKind, OwnerRole,
    # functions
    parse_pattern_yaml, validate_pattern, to_canonical_json, to_canonical_yaml, compute_digest,
    # expression engine
    CelEngine, CelError, default_engine, PATTERN_CEL_VARIABLES,
)
```

## Functions

| Signature | Behaviour |
|---|---|
| `parse_pattern_yaml(text: str \| bytes, engine: CelEngine \| None = None) -> ParseResult` | Size guard, then safe load with no aliases, then a single-mapping check, then `PatternDefinition` construction, then (if construction succeeded) `validate_pattern`. **Never raises.** `engine=None` uses `default_engine()` |
| `validate_pattern(defn: PatternDefinition, engine: CelEngine) -> list[PatternIssue]` | V7: compiles every `roles.*.selector` and `constraints[*].expr`. Returns issues; never raises |
| `to_canonical_json(defn) -> str` | Sorted mapping keys, compact separators, UTF-8. `roles` is encoded as an ordered list of `[key, role]` pairs |
| `compute_digest(defn) -> str` | 64-character lowercase hex SHA-256 of `to_canonical_json(defn)` |
| `to_canonical_yaml(defn) -> str` | Field-declaration key order, cardinality shorthand, defaults omitted, block style, no aliases. `parse_pattern_yaml(to_canonical_yaml(d)).definition == d` |

## Expression engine

```python
@dataclass(frozen=True)
class CelError:
    message: str
    line: int | None      # position within the expression
    column: int | None
    code: Literal["compile", "not_bool"]

class CelEngine(Protocol):
    def compile_check(self, expr: str) -> list[CelError]: ...
    def compile(self, expr: str) -> object: ...            # opaque program handle
    def evaluate(self, program: object, activation: Mapping[str, Any],
                 functions: Mapping[str, Callable[..., Any]]) -> CelResult: ...

@dataclass(frozen=True)
class CelResult:              # evaluation outcome without exceptions; 936 maps these to findings
    value: Any | None
    error: Literal[None, "missing_key", "budget_exceeded", "type_error", "other"]
    message: str | None
```

- `PATTERN_CEL_VARIABLES` declares `it: dyn`, `bindings: map<string, list<dyn>>` and `scope: map<string, list<dyn>>`. The functions are `role(string) → list<string>` and `bound(map<string,dyn>, string) → bool`.
- `default_engine()` returns a process-wide cached `GoogleCelEngine` (`cel-expr-python`).
- `evaluate` is included now so the adapter contract is complete and tested once. 936 is its first production caller.

## Guarantees (tested)

1. No input to `parse_pattern_yaml` raises (fuzzed with random bytes, truncated documents, and binary data).
2. Round-trip law and digest stability for every valid fixture.
3. Digest is invariant under mapping-key reordering and cardinality notation. It changes under role, plateau, constraint or relationship reordering, and under any value change.
4. `models.py` imports nothing from `cel.py`, so `PatternDefinition.model_json_schema()` is engine-free.
