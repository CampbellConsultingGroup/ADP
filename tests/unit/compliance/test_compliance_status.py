"""Unit tests for Derived Compliance Status (COMPLY-03, specs/923-derived-compliance-status/).

Tests `compute_compliance_status()` (a pure, no-I/O aggregation function) standalone, before any
store or router wiring depends on it -- mirrors tests/unit/strategy/test_objective_status.py's own
precedent for testing a derived-status pure function in isolation (research.md D6).

`get_entity_compliance_status()`'s async dispatch wrapper is exercised separately, at the end of
this module, using an in-memory SQLite fixture that mirrors
tests/contract/test_compliance_mappings_api.py's `cstore._metadata.create_all()` pattern -- no
Docker/testcontainers required.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import store as cstore
from adp.compliance.models import ComplianceStatus, MappingTargetType
from adp.compliance.store import compute_compliance_status, get_entity_compliance_status

# pytest-asyncio's asyncio_mode = "auto" (pyproject.toml) picks up `async def test_*` functions
# automatically -- no module-level pytestmark needed, and none is used here since this module also
# has plain synchronous tests for the pure function.


# ── Foundational: guard clauses (T002, T003) ────────────────────────────────


def test_empty_statuses_is_not_assessed() -> None:
    """FR-005: an entity with no mapped controls at all derives to Not Assessed."""
    assert compute_compliance_status([]) == ComplianceStatus.NOT_ASSESSED


async def test_organization_scope_raises_value_error() -> None:
    """research.md D4: ORGANIZATION has no per-entity lookup -- get_entity_compliance_status()
    must reject it explicitly rather than silently returning a status."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        with pytest.raises(ValueError):
            await get_entity_compliance_status(
                MappingTargetType.ORGANIZATION, "irrelevant", session
            )

    await engine.dispose()


async def test_unsupported_entity_type_raises_value_error() -> None:
    """Any entity_type outside the four supported types is rejected the same way."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        with pytest.raises(ValueError):
            await get_entity_compliance_status("not-a-real-type", "irrelevant", session)  # type: ignore[arg-type]

    await engine.dispose()


# ── User Story 1 (P1): a Non-Compliant control is never masked (T006) ──────


def test_single_non_compliant_among_many_compliant_wins() -> None:
    """FR-002, SC-002: one Non-Compliant among twenty Compliant still yields Non-Compliant."""
    statuses = [ComplianceStatus.NON_COMPLIANT] + [ComplianceStatus.COMPLIANT] * 20
    assert compute_compliance_status(statuses) == ComplianceStatus.NON_COMPLIANT


def test_single_non_compliant_alone_wins() -> None:
    assert (
        compute_compliance_status([ComplianceStatus.NON_COMPLIANT])
        == ComplianceStatus.NON_COMPLIANT
    )


# ── User Story 2 (P2): Partial/Not Assessed distinct from Compliant (T008) ─


def test_partial_and_not_assessed_mix_is_partial() -> None:
    """FR-003: no Non-Compliant present, but at least one Partial or Not Assessed -> Partial."""
    statuses = [ComplianceStatus.PARTIAL, ComplianceStatus.NOT_ASSESSED]
    assert compute_compliance_status(statuses) == ComplianceStatus.PARTIAL


def test_new_not_assessed_mapping_downgrades_otherwise_compliant_entity() -> None:
    """A freshly-mapped, not-yet-assessed control correctly downgrades an otherwise fully
    compliant entity to Partial, not Compliant (spec.md US2 AS2)."""
    statuses = [
        ComplianceStatus.COMPLIANT,
        ComplianceStatus.COMPLIANT,
        ComplianceStatus.NOT_ASSESSED,
    ]
    assert compute_compliance_status(statuses) == ComplianceStatus.PARTIAL


# ── User Story 3 (P3): Compliant only when earned; Q1's all-N/A resolution (T010) ─


def test_all_compliant_is_compliant() -> None:
    """FR-004."""
    statuses = [ComplianceStatus.COMPLIANT, ComplianceStatus.COMPLIANT]
    assert compute_compliance_status(statuses) == ComplianceStatus.COMPLIANT


def test_compliant_and_not_applicable_mix_is_compliant() -> None:
    """FR-004: at least one Compliant among Compliant/Not-Applicable-only -> Compliant."""
    statuses = [ComplianceStatus.COMPLIANT, ComplianceStatus.NOT_APPLICABLE]
    assert compute_compliance_status(statuses) == ComplianceStatus.COMPLIANT


def test_all_not_applicable_with_none_compliant_is_not_applicable() -> None:
    """FR-006 (Q1, resolved by user): every mapped control Not Applicable, none Compliant, is
    its own distinct outcome -- NOT folded into Not Assessed."""
    statuses = [ComplianceStatus.NOT_APPLICABLE, ComplianceStatus.NOT_APPLICABLE]
    assert compute_compliance_status(statuses) == ComplianceStatus.NOT_APPLICABLE


# ── Polish: determinism / order-independence (T013) ─────────────────────────


def test_result_is_independent_of_input_order() -> None:
    """FR-007, SC-004: the result depends only on the multiset of statuses, never on order."""
    statuses = [
        ComplianceStatus.PARTIAL,
        ComplianceStatus.COMPLIANT,
        ComplianceStatus.NOT_APPLICABLE,
    ]
    results = set()
    for _ in range(50):
        shuffled = statuses[:]
        random.shuffle(shuffled)
        results.add(compute_compliance_status(shuffled))
    assert results == {ComplianceStatus.PARTIAL}


# ── User Story 3 (P3): end-to-end async dispatch across all four entity types (T012) ─


@pytest.fixture()
async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        await conn.execute(cstore._capabilities_mirror.insert().values(id="cap-1"))
        await conn.execute(cstore._applications_mirror.insert().values(id="app-1"))
        await conn.execute(cstore._designs_mirror.insert().values(id="design-1"))
        await conn.execute(
            cstore._knowledge_items_mirror.insert().values(id="pattern-1", kind="pattern")
        )
        await conn.execute(
            cstore._frameworks.insert().values(
                id="fw-1",
                name="Test Framework",
                jurisdiction="Global",
                authority="Test Authority",
                version="1.0",
                effective_date=None,
                source_url=None,
                created_at=now,
                updated_at=now,
            )
        )
        for i in range(1, 4):
            await conn.execute(
                cstore._controls.insert().values(
                    id=f"ctrl-{i}",
                    framework_id="fw-1",
                    parent_id=None,
                    code=f"C-{i}",
                    title=f"Control {i}",
                    description="test",
                    position=i,
                    created_at=now,
                    updated_at=now,
                )
            )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.parametrize(
    ("target_type", "entity_id", "mirror_table", "mapping_table", "fk_column"),
    [
        (
            MappingTargetType.CAPABILITY,
            "cap-1",
            "_capabilities_mirror",
            "_control_capability_mapping",
            "capability_id",
        ),
        (
            MappingTargetType.APPLICATION,
            "app-1",
            "_applications_mirror",
            "_control_application_mapping",
            "application_id",
        ),
        (
            MappingTargetType.DESIGN,
            "design-1",
            "_designs_mirror",
            "_control_design_mapping",
            "design_id",
        ),
        (
            MappingTargetType.PATTERN,
            "pattern-1",
            "_knowledge_items_mirror",
            "_control_pattern_mapping",
            "pattern_id",
        ),
    ],
)
async def test_get_entity_compliance_status_dispatches_per_type(
    _session, target_type, entity_id, mirror_table, mapping_table, fk_column
) -> None:
    """SC-003: the same aggregation rule produces correct results for all four supported entity
    types, with no type-specific special-casing -- one Non-Compliant + one Compliant yields
    Non-Compliant for every type, exercised through the real async dispatch wrapper (not the pure
    function directly)."""
    table = getattr(cstore, mapping_table)
    await _session.execute(
        table.insert().values(
            **{
                "control_id": "ctrl-1",
                fk_column: entity_id,
                "compliance_status": ComplianceStatus.NON_COMPLIANT.value,
                "evidence_ref": None,
                "assessed_at": None,
                "assessed_by": None,
                "created_at": datetime.now(timezone.utc),
            }
        )
    )
    await _session.execute(
        table.insert().values(
            **{
                "control_id": "ctrl-2",
                fk_column: entity_id,
                "compliance_status": ComplianceStatus.COMPLIANT.value,
                "evidence_ref": None,
                "assessed_at": None,
                "assessed_by": None,
                "created_at": datetime.now(timezone.utc),
            }
        )
    )
    await _session.commit()

    status = await get_entity_compliance_status(target_type, entity_id, _session)
    assert status == ComplianceStatus.NON_COMPLIANT


async def test_get_entity_compliance_status_no_mappings_is_not_assessed(_session) -> None:
    """An entity with zero ControlMapping rows derives to Not Assessed via the async wrapper too
    (FR-005), same as the pure function's own empty-list case."""
    status = await get_entity_compliance_status(MappingTargetType.APPLICATION, "app-1", _session)
    assert status == ComplianceStatus.NOT_ASSESSED
