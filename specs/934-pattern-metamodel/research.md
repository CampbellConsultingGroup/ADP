# Research: EA Pattern Metamodel & YAML Format (934)

## D1 — Expression engine: `cel-expr-python` (Google's CEL runtime), behind an adapter

**Decision**: Use `cel-expr-python==0.1.4`, pinned exactly. Wrap it in a `CelEngine` protocol (`adp.patterns.cel`) so the library can be swapped. The fallback is `common-expression-language==0.10.0`.

**Spike** (2026-11-14). All three candidates were installed in a throwaway venv on Python 3.12. The same expressions and the same criteria were run against each. The scripts were kept out of the repo.

| Criterion (spec Clarifications) | `cel-python` 0.5.0 (pure Python) | `common-expression-language` 0.10.0 (Rust) | `cel-expr-python` 0.1.4 (Google cel-cpp) |
|---|---|---|---|
| Custom functions `role(string)`, `bound(elem, string)` | ✔ (Python callables) | ✔ (Python callables in `Context`) | ✔ (typed `FunctionDecl`/`Overload`; `bound` must be declared as `map<string,dyn>, string`, because a `dyn` first parameter did not match a map argument at runtime) |
| Compile-time error position | ✔ line/column on `CELParseError` | ✔ `<input>:1:8` in the message | ✔ `<input>:1:8`, plus a caret excerpt |
| **Static check against declared variables** | ✘ An undeclared variable fails only at evaluation | ◑ No checker. `Program.references()` lists the variables and functions used, so undeclared names can be detected by hand | ✔ A real type checker. `undeclared_var` is rejected **at compile time** with its position. Overload mismatches (`1 + 'a'`, `role(1)`) are also rejected at compile time |
| **Enforce a boolean result at compile time** | ✘ | ✘ | ✔ `Expression.return_type()` (for example `'abc'` → `STRING`) |
| Missing map key detectable | ✔ `CELEvalError` caused by `KeyError` | ✔ raises `KeyError('missing')` | ✔ returns an `ERROR` value `NOT_FOUND: Key not found in map` (not an exception) |
| Per-expression cost limit | ✘ none; a 300×300 nested comprehension took **18.3 s** | ✘ none, but fast (300×300 in 0.03 s, 2000×2000 in 1.07 s) | ✔ **built-in iteration budget**: one comprehension may run more than 5,000 but fewer than 10,000 iterations, then `INTERNAL: Iteration budget exceeded`. Not configurable from Python in 0.1.4 |
| Python 3.11 wheel (manylinux x86_64) | ✔ pure | ✔ `cp311 manylinux2014` | ✔ `cp311 manylinux_2_28`; the image base `python:3.12-slim` (glibc 2.36) satisfies it |
| Licence / maintainer | Apache-2.0 / Cloud Custodian lineage | MIT-style / community | Apache-2.0 / Google, the reference C++ implementation |
| Runtime dependencies | `lark` and others | none | none (`protobuf` is only needed for message types, which we don't use) |

**Rationale**:
- `cel-expr-python` is the only candidate that meets FR-011 *natively*: compile-checking against a declared variable and function set, with positions. It also enforces FR-004's "expression must be boolean" statically.
- It has a built-in cost limit, which spec 936's `limit_exceeded` finding can map onto directly.
- It is Google's own runtime, so CEL semantics match the specification exactly.

**Risks and mitigations**:
- **The 0.x version could change its API.** Pin it exactly. All calls go through `adp.patterns.cel`, whose unit tests are an executable contract for any replacement.
- **The iteration budget isn't tunable.** It is per *evaluation*, and 936 evaluates per element (`for_each`), so budgets apply per element, not per estate. A global constraint ranging over more than about 5,000 elements becomes a `limit_exceeded` finding, which is the behaviour the bundle already specifies.
- **Native wheel.** It is only available for manylinux x86_64/aarch64 and macOS. That covers dev (WSL), CI (ubuntu) and the container image.

**Alternatives considered**:
- `common-expression-language` is the fallback. It is fast and has a clean API, but undeclared-name checking would have to be built on `references()`, and there is no type check or cost limit.
- `cel-python` was rejected: it is about 600× slower on the nested case, has no cost limit and no static check.

**Follow-up check.** Every reference-fixture expression compiles against the declared environment (`it: dyn`, `bindings`/`scope: map<string, list<dyn>>`, `role`, `bound`). Each has return type `BOOL`, with one exception:
- A bare field access such as `it.name` has type `DYN`, because `it` is `dyn`.
- So V7.not_bool fires only when the checked return type is **definitely not** bool (`STRING`, `INT`, `LIST`, …).
- A `DYN` result is accepted at compile time. 936 reports a non-bool value at evaluation time as `evaluation_error`.

## D2 — YAML loading: a custom SafeLoader subclass that rejects anchors and aliases

**Decision**:
- Subclass `yaml.SafeLoader` and override `compose_node`, raising an error on an `AliasEvent` and on any node event with a non-null `anchor`.
- Enforce the 256 KB limit on the raw bytes before parsing.
- Use `yaml.compose_all` to detect multi-document streams.

`pyyaml` is already a dependency (`pyproject.toml`).

**Rationale**: anchors are rejected at composition time, before any expansion, so an alias bomb cannot allocate. Safe loading constructs no arbitrary tags.

**Alternatives**: `ruamel.yaml` would be a new dependency and adds nothing over this.

## D3 — Models: Pydantic v2, frozen, `extra="forbid"`, insertion-ordered `roles`

**Decision**:
- Every model uses `ConfigDict(extra="forbid", frozen=True)`.
- `roles: dict[RoleKey, Role]`: Python dicts preserve insertion order, and Pydantic keeps it through `model_dump`.
- Cardinality shorthand is handled by a `BeforeValidator`.
- Cross-field rules V1–V9 live in a single `model_validator(mode="after")` that *collects* issues rather than raising on the first one.
- V7 (CEL compile) is **not** run inside the model validator. It runs in `validate_pattern()` after structural validation, so the model stays pure and engine-free, which makes it usable for schema generation.

**Rationale**: frozen models give hashable, immutable definitions (spec: "immutable"). Separating the CEL step keeps `PatternDefinition.model_json_schema()` free of engine imports.

## D4 — Issue reporting never raises

**Decision**:
- `parse_pattern_yaml(text) -> ParseResult{definition | None, issues: list[PatternIssue]}`.
- A Pydantic `ValidationError` is converted to issues: `loc` becomes the path (`constraints[1].expr`), `type` becomes a code (`schema.<type>`), plus the message.
- Model-validator rules emit their own stable codes `V1`–`V9`, with sub-codes such as `V2.unknown_role`.
- CEL compile errors are `V7.compile` (path plus engine position) and `V7.not_bool`.
- Parse failures are `P1.too_large`, `P2.alias`, `P3.multi_document`, `P4.not_mapping` and `P5.yaml_syntax` (line and column from the PyYAML mark).

**Rationale**: FR-012 and SC-003. One stable code namespace serves the UI (935) and the tests.

## D5 — Canonical JSON and digest

**Decision**:
- `to_canonical_json` = `json.dumps(defn.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
- `sort_keys` sorts *mapping keys only*. `roles` is a mapping, but its order is semantic, so it is dumped as an ordered **list of `[key, role]` pairs** inside the canonical form. All other lists keep their order.
- Digest = SHA-256 hex of the canonical form encoded as UTF-8.
- `lifecycle` doesn't exist in the authored model (spec GT-4), so the bundle's "exclude lifecycle" rule disappears.

**Rationale**: a plain `sort_keys=True` would silently sort role keys and break the spec's acceptance scenario US2-3 (reordering roles must change the digest). Encoding roles as pairs makes declared order part of the content identity. The pairs encoding is used only for digesting; canonical YAML keeps the `roles:` mapping.

## D6 — Canonical YAML

**Decision**: a dedicated emitter:
- build plain dicts in field-declaration order;
- write cardinality as shorthand when it is representable (`min/max/per` → `"1"`, `"0..1"`, `"2..*"`, `"1 per x"`), otherwise longhand;
- omit `None` and empty defaults;
- dump with `yaml.SafeDumper`, `sort_keys=False`, `default_flow_style=False`, `allow_unicode=True`, and a Dumper whose `ignore_aliases` returns `True`.

**Rationale**: FR-013 and the round-trip law. Omitting defaults keeps files hand-readable, and the round-trip test proves nothing is lost.

## D7 — Schema generation: extend the existing `adp-generate`

**Decision**:
- Add `generate_pattern_schema()` to `src/adp/generate.py`, mirroring `generate_theme_schema()`: sorted keys, `$schema` 2020-12, `$id`, title "ADP EA Pattern".
- Write it to `generated/pattern.schema.json` and add it to `check()` and `main()`.

**Rationale**: spec GT-5. It is the one sanctioned writer and drift gate (QG-02, QG-18).

## D8 — Package placement: a new sibling package `adp.patterns`

**Decision**: create `src/adp/patterns/` with:
- `__init__.py`;
- `models.py`;
- `parse.py` (parse, validate, canonical forms, digest);
- `cel.py` (protocol, adapter, declared environment);
- `cardinality.py` (shorthand grammar).

Tests go in `tests/unit/patterns/`, with fixtures in `tests/unit/patterns/fixtures/{valid,invalid}/`.

**Rationale**:
- The bundle names `adp.patterns`, and nothing else uses that name.
- `adp.knowledge` owns prose patterns, and spec 935 bridges the two by projection.
- ADP tests live under `tests/unit/<pkg>/`, not `tests/<pkg>/` as the bundle drafted.

## D9 — Reference fixture selectors use real ADP attributes

**Decision**:
- **Backbone role:** the selector is `it.application_type in ['custom', 'saas', 'cots']`. The fixture also documents that a backbone is normally *pinned* by an adoption (936), because ADP has no tag or technology-standard field to select one with.
- **Domain app role:** `it.time_classification in ['Invest', 'Tolerate']`. ADP uses title case for these values (`adp.application.models`, line 13).
- **Cross-domain integration:** `it.source.domain_ids.all(d, !(d in it.target.domain_ids))`. This uses 936's derived `domain_ids` lists (an application can belong to several domains). The CEL environment declares `it` as `dyn`, so this compiles now.

**Rationale**: spec FR-017 requires that selectors only reference attributes that exist in ADP. The exact attribute set is pinned in 936's snapshot contract. This spec only proves that the expressions compile.
