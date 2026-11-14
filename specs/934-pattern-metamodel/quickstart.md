# Quickstart: EA Pattern Metamodel (934)

This spec is a library, so you verify it from a Python shell and the test suite. There is no API or UI until spec 935.

```bash
pip install -e ".[dev]"          # pulls cel-expr-python==0.1.4
pytest tests/unit/patterns -q
adp-generate && adp-generate --check   # writes/drift-checks generated/pattern.schema.json
```

## 1. Validate the reference pattern

```python
from pathlib import Path
from adp.patterns import parse_pattern_yaml, compute_digest
r = parse_pattern_yaml(Path("tests/unit/patterns/fixtures/valid/ea.integration.domain-event-backbone@1.0.0.yaml").read_text())
assert r.ok and r.issues == []
print(r.definition.name, compute_digest(r.definition)[:12])
```

## 2. See precise issues

```python
bad = """
pattern: ea.x.demo
version: 1.0.0
kind: portfolio-rule
name: Demo
summary: Demo
owner_role: enterprise
motivation: {context: c, problem: p}
roles:
  app: {element_type: application, cardinality: "1..*"}
constraints:
  - {id: C1, rule: r, for_each: ghost, expr: "it.name =="}
"""
for i in parse_pattern_yaml(bad).issues:
    print(i.code, i.path, i.message)
# V2.unknown_role  constraints[0].for_each  …
# (V7 runs only once the structure is valid; fix for_each and V7.compile constraints[0].expr appears)
```

## 3. Hostile input is rejected, not expanded

```python
parse_pattern_yaml("a: &x [1]\nb: *x\n").issues[0].code   # 'P2.alias'
parse_pattern_yaml(b"\x00\xff" * 10).ok                    # False, no exception
```

## 4. Round-trip

```python
from adp.patterns import to_canonical_yaml
d = r.definition
assert parse_pattern_yaml(to_canonical_yaml(d)).definition == d
```
