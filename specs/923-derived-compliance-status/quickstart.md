# Quickstart / Integration Scenarios: Derived Compliance Status — COMPLY-03

**Feature**: 923-derived-compliance-status
**Date**: 2026-08-18

This feature adds no HTTP endpoint (research.md D1), so there is no `curl` walkthrough the way
COMPLY-01/COMPLY-02's quickstarts have. These scenarios instead drive the unit test matrix
(`tests/unit/compliance/test_compliance_status.py`) and double as a manual verification script — run
directly with `python3` against an editable install (`pip install -e ".[dev]"`), no database or
running server required for the pure-function scenarios (1–6); scenario 7 needs a running Postgres
with at least one `ControlMapping` row, matching COMPLY-02's own dev setup.

---

## Scenario 1: One non-compliant control among many compliant ones still wins (US1, AS1/AS2)

**Goal**: Verify FR-002, SC-002.

```python
from adp.compliance.models import ComplianceStatus
from adp.compliance.store import compute_compliance_status

statuses = [ComplianceStatus.NON_COMPLIANT] + [ComplianceStatus.COMPLIANT] * 20
assert compute_compliance_status(statuses) == ComplianceStatus.NON_COMPLIANT

assert compute_compliance_status([ComplianceStatus.NON_COMPLIANT]) == ComplianceStatus.NON_COMPLIANT
print("OK: a single Non-Compliant control is never masked")
```

## Scenario 2: Partial or unassessed work reads as Partial, not Compliant (US2, AS1/AS2)

**Goal**: Verify FR-003.

```python
assert compute_compliance_status(
    [ComplianceStatus.PARTIAL, ComplianceStatus.NOT_ASSESSED]
) == ComplianceStatus.PARTIAL

# A freshly-mapped, not-yet-assessed control downgrades an otherwise fully compliant entity.
assert compute_compliance_status(
    [ComplianceStatus.COMPLIANT, ComplianceStatus.COMPLIANT, ComplianceStatus.NOT_ASSESSED]
) == ComplianceStatus.PARTIAL
print("OK: partial/not-assessed correctly downgrades from Compliant")
```

## Scenario 3: Full compliance requires at least one actually-compliant control (US3, AS1/AS2)

**Goal**: Verify FR-004.

```python
assert compute_compliance_status(
    [ComplianceStatus.COMPLIANT, ComplianceStatus.COMPLIANT]
) == ComplianceStatus.COMPLIANT

assert compute_compliance_status(
    [ComplianceStatus.COMPLIANT, ComplianceStatus.NOT_APPLICABLE]
) == ComplianceStatus.COMPLIANT
print("OK: Compliant is only reached when actually earned")
```

## Scenario 4: An entity with no mapped controls derives to Not Assessed

**Goal**: Verify FR-005.

```python
assert compute_compliance_status([]) == ComplianceStatus.NOT_ASSESSED
print("OK: empty mapping set is Not Assessed, not a crash or a false Compliant")
```

## Scenario 5: Every mapped control Not Applicable, none Compliant → Not Applicable (US3, AS3)

**Goal**: Verify FR-006 (Q1 resolution).

```python
assert compute_compliance_status(
    [ComplianceStatus.NOT_APPLICABLE, ComplianceStatus.NOT_APPLICABLE]
) == ComplianceStatus.NOT_APPLICABLE
print("OK: all-Not-Applicable is its own distinct outcome, not folded into Not Assessed")
```

## Scenario 6: Determinism — same input, same output, every time

**Goal**: Verify FR-007, SC-004.

```python
import random

statuses = [ComplianceStatus.PARTIAL, ComplianceStatus.COMPLIANT, ComplianceStatus.NOT_APPLICABLE]
results = set()
for _ in range(50):
    shuffled = statuses[:]
    random.shuffle(shuffled)
    results.add(compute_compliance_status(shuffled))
assert results == {ComplianceStatus.PARTIAL}
print("OK: result depends only on the multiset of statuses, never on order")
```

## Scenario 7: End-to-end dispatch against a real Application's mappings (requires Postgres)

**Goal**: Verify FR-001, SC-003 for the async lookup path.

```bash
export ADP_DATABASE_URL="postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
```

```python
import asyncio
from adp.compliance.models import MappingTargetType
from adp.compliance.store import get_session, get_entity_compliance_status

async def main():
    async with get_session() as session:
        status = await get_entity_compliance_status(
            MappingTargetType.APPLICATION, "$APP_ID", session
        )
        print(f"Derived status for $APP_ID: {status}")

asyncio.run(main())
```

```python
# Passing the unsupported ORGANIZATION scope raises, rather than silently returning a status
# (research.md D4):
try:
    asyncio.run(main_with(MappingTargetType.ORGANIZATION, "irrelevant"))
except ValueError:
    print("OK: ORGANIZATION scope correctly rejected, not silently handled")
```
