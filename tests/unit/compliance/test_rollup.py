"""Unit tests for Compliance Rollup Reporting (COMPLY-04, specs/924-compliance-rollup-reporting/).

Tests `_bucket_entities_by_status()` (a pure, no-I/O helper) standalone first (Foundational),
mirroring test_compliance_status.py's own precedent for testing a derived-aggregation function in
isolation before any store/router work depends on it. `get_framework_coverage_rollup()` and
`get_compliance_summary()` (both async, DB-touching) are exercised via an in-memory SQLite fixture
mirroring test_compliance_status.py's own `_session` fixture and
tests/contract/test_compliance_mappings_api.py's `cstore._metadata.create_all()` pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.compliance import store as cstore
from adp.compliance.models import ComplianceStatus, EntityStatusCounts, MappingTargetType
from adp.compliance.store import (
    _bucket_entities_by_status,
    get_compliance_summary,
    get_framework_coverage_rollup,
)

# ── Foundational: _bucket_entities_by_status() (T004) ───────────────────────


def test_bucket_entities_empty_list_is_all_zero() -> None:
    counts = _bucket_entities_by_status([])
    assert counts == EntityStatusCounts(
        compliant_count=0, partial_count=0, non_compliant_count=0,
        not_assessed_count=0, not_applicable_count=0,
    )


def test_bucket_entities_groups_by_target_type_and_id() -> None:
    """Two rows for the same entity aggregate together (via compute_compliance_status());
    two different target_ids of the same target_type are kept as separate entities."""
    rows = [
        (MappingTargetType.APPLICATION, "app-1", ComplianceStatus.NON_COMPLIANT),
        (MappingTargetType.APPLICATION, "app-1", ComplianceStatus.COMPLIANT),  # same entity
        (MappingTargetType.APPLICATION, "app-2", ComplianceStatus.COMPLIANT),  # different entity
        (MappingTargetType.CAPABILITY, "app-1", ComplianceStatus.COMPLIANT),  # different type
    ]
    counts = _bucket_entities_by_status(rows)
    # app-1 (application) -> NON_COMPLIANT wins; app-2 (application) -> COMPLIANT;
    # app-1 (capability) -> COMPLIANT (its own, separate entity, single row)
    assert counts.non_compliant_count == 1
    assert counts.compliant_count == 2
    assert counts.partial_count == 0
    assert counts.not_assessed_count == 0
    assert counts.not_applicable_count == 0


def test_bucket_entities_covers_all_five_buckets() -> None:
    rows = [
        (MappingTargetType.APPLICATION, "e1", ComplianceStatus.COMPLIANT),
        (MappingTargetType.APPLICATION, "e2", ComplianceStatus.PARTIAL),
        (MappingTargetType.APPLICATION, "e3", ComplianceStatus.NON_COMPLIANT),
        (MappingTargetType.APPLICATION, "e4", ComplianceStatus.NOT_APPLICABLE),
        # e5 has no rows at all -- not part of this bucketing call, confirming an entity with
        # zero rows simply never appears (not_assessed comes from compute_compliance_status([])
        # only when a group's own list is truly empty, which _bucket_entities_by_status never
        # constructs for an entity with no rows -- there is no such group to iterate).
    ]
    counts = _bucket_entities_by_status(rows)
    assert counts.compliant_count == 1
    assert counts.partial_count == 1
    assert counts.non_compliant_count == 1
    assert counts.not_applicable_count == 1
    assert counts.not_assessed_count == 0


# ── SQLite fixture for the async store functions (US1/US2) ─────────────────


@pytest.fixture()
async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        await conn.run_sync(cstore._metadata.create_all)
        await conn.execute(cstore._capabilities_mirror.insert().values(id="cap-1"))
        await conn.execute(cstore._applications_mirror.insert().values(id="app-1"))
        await conn.execute(cstore._applications_mirror.insert().values(id="app-2"))
        await conn.execute(cstore._designs_mirror.insert().values(id="design-1"))
        await conn.execute(
            cstore._knowledge_items_mirror.insert().values(id="pattern-1", kind="pattern")
        )
        for fw_id in ("fw-1", "fw-2"):
            await conn.execute(
                cstore._frameworks.insert().values(
                    id=fw_id, name=f"Framework {fw_id}", jurisdiction="Global",
                    authority="Test Authority", version="1.0", effective_date=None,
                    source_url=None, created_at=now, updated_at=now,
                )
            )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _mk_control(session, control_id: str, framework_id: str) -> None:
    now = datetime.now(timezone.utc)
    await session.execute(
        cstore._controls.insert().values(
            id=control_id, framework_id=framework_id, parent_id=None, code=control_id,
            title=control_id, description="test", position=0, created_at=now, updated_at=now,
        )
    )


async def _mk_mapping(
    session, table, control_id: str, fk_column: str, entity_id: str, status: ComplianceStatus
) -> None:
    await session.execute(
        table.insert().values(
            **{
                "control_id": control_id,
                fk_column: entity_id,
                "compliance_status": status.value,
                "evidence_ref": None,
                "assessed_at": None,
                "assessed_by": None,
                "created_at": datetime.now(timezone.utc),
            }
        )
    )


# ── User Story 1 (P1): get_framework_coverage_rollup() (T006) ──────────────


async def test_framework_rollup_mixed_statuses(_session) -> None:
    """FR-001, FR-002, spec.md US1 AS1: five entities, a mix of statuses.

    Per COMPLY-03's own decision table (rule 3: any PARTIAL or NOT_ASSESSED present -> PARTIAL),
    a single NOT_ASSESSED-status mapping aggregates to PARTIAL for that entity, not NOT_ASSESSED
    -- not_assessed_count can only ever be nonzero for an entity with *zero* mapped controls,
    which by construction never appears as a row here at all (there is nothing to query). c4
    below (one NOT_ASSESSED mapping) therefore lands in partial_count alongside c3, confirmed
    explicitly rather than silently assumed."""
    await _mk_control(_session, "c1", "fw-1")
    await _mk_control(_session, "c2", "fw-1")
    await _mk_control(_session, "c3", "fw-1")
    await _mk_control(_session, "c4", "fw-1")
    await _mk_control(_session, "c5", "fw-1")
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c1", "application_id", "app-1",
        ComplianceStatus.COMPLIANT,
    )
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c2", "application_id", "app-2",
        ComplianceStatus.NON_COMPLIANT,
    )
    await _mk_mapping(
        _session, cstore._control_capability_mapping, "c3", "capability_id", "cap-1",
        ComplianceStatus.PARTIAL,
    )
    await _mk_mapping(
        _session, cstore._control_design_mapping, "c4", "design_id", "design-1",
        ComplianceStatus.NOT_ASSESSED,
    )
    await _mk_mapping(
        _session, cstore._control_pattern_mapping, "c5", "pattern_id", "pattern-1",
        ComplianceStatus.NOT_APPLICABLE,
    )
    await _session.commit()

    rollup = await get_framework_coverage_rollup("fw-1", include_application=True, session=_session)
    assert rollup is not None
    assert rollup.framework_id == "fw-1"
    assert rollup.entity_counts == EntityStatusCounts(
        compliant_count=1, non_compliant_count=1, partial_count=2,
        not_assessed_count=0, not_applicable_count=1,
    )
    assert rollup.organization_status is None


async def test_framework_rollup_not_assessed_bucket_is_structurally_unreachable(_session) -> None:
    """Explicit invariant test: not_assessed_count is always 0 in a coverage rollup, because an
    entity only ever appears as a row here when it has at least one mapping -- and any nonempty
    set of mapped-control statuses that includes NOT_ASSESSED resolves to PARTIAL, never
    NOT_ASSESSED, per compute_compliance_status()'s own rule. The only way to reach NOT_ASSESSED
    is zero mappings, which produces zero rows, not a row with that status."""
    await _mk_control(_session, "c1", "fw-1")
    await _mk_mapping(
        _session, cstore._control_capability_mapping, "c1", "capability_id", "cap-1",
        ComplianceStatus.NOT_ASSESSED,
    )
    await _session.commit()

    rollup = await get_framework_coverage_rollup("fw-1", include_application=True, session=_session)
    assert rollup.entity_counts.partial_count == 1
    assert rollup.entity_counts.not_assessed_count == 0


async def test_framework_rollup_scoped_per_framework_not_blended(_session) -> None:
    """FR-001, US1 AS2, quickstart.md Scenario 2: the same Application counts differently under
    two different frameworks -- never blended into one cross-framework status."""
    await _mk_control(_session, "c1", "fw-1")
    await _mk_control(_session, "c2", "fw-2")
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c1", "application_id", "app-1",
        ComplianceStatus.NON_COMPLIANT,
    )
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c2", "application_id", "app-1",
        ComplianceStatus.COMPLIANT,
    )
    await _session.commit()

    rollup_1 = await get_framework_coverage_rollup(
        "fw-1", include_application=True, session=_session
    )
    rollup_2 = await get_framework_coverage_rollup(
        "fw-2", include_application=True, session=_session
    )
    assert rollup_1.entity_counts.non_compliant_count == 1
    assert rollup_1.entity_counts.compliant_count == 0
    assert rollup_2.entity_counts.compliant_count == 1
    assert rollup_2.entity_counts.non_compliant_count == 0


async def test_framework_rollup_organization_status_is_separate_field(_session) -> None:
    """FR-003, US1 AS3: an estate-wide obligation is its own field, never counted as an entity."""
    await _mk_control(_session, "c1", "fw-1")
    await _session.execute(
        cstore._control_organization_mapping.insert().values(
            control_id="c1", compliance_status=ComplianceStatus.PARTIAL.value,
            evidence_ref=None, assessed_at=None, assessed_by=None,
            created_at=datetime.now(timezone.utc),
        )
    )
    await _session.commit()

    rollup = await get_framework_coverage_rollup("fw-1", include_application=True, session=_session)
    assert rollup.organization_status == ComplianceStatus.PARTIAL
    assert rollup.entity_counts == EntityStatusCounts(
        compliant_count=0, non_compliant_count=0, partial_count=0,
        not_assessed_count=0, not_applicable_count=0,
    )


async def test_framework_rollup_zero_mappings_is_all_zero(_session) -> None:
    """FR-008, Edge Cases: a framework with zero mapped controls rolls up to all zeros."""
    rollup = await get_framework_coverage_rollup("fw-1", include_application=True, session=_session)
    assert rollup is not None
    assert rollup.entity_counts == EntityStatusCounts(
        compliant_count=0, non_compliant_count=0, partial_count=0,
        not_assessed_count=0, not_applicable_count=0,
    )
    assert rollup.organization_status is None


async def test_framework_rollup_unknown_framework_returns_none(_session) -> None:
    rollup = await get_framework_coverage_rollup(
        "does-not-exist", include_application=True, session=_session
    )
    assert rollup is None


async def test_framework_rollup_excludes_application_when_not_permitted(_session) -> None:
    """FR-007: an Application-targeted entity is excluded from the counts when
    include_application is False."""
    await _mk_control(_session, "c1", "fw-1")
    await _mk_control(_session, "c2", "fw-1")
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c1", "application_id", "app-1",
        ComplianceStatus.NON_COMPLIANT,
    )
    await _mk_mapping(
        _session, cstore._control_capability_mapping, "c2", "capability_id", "cap-1",
        ComplianceStatus.COMPLIANT,
    )
    await _session.commit()

    with_app = await get_framework_coverage_rollup(
        "fw-1", include_application=True, session=_session
    )
    without_app = await get_framework_coverage_rollup(
        "fw-1", include_application=False, session=_session
    )
    assert with_app.entity_counts.non_compliant_count == 1
    assert with_app.entity_counts.compliant_count == 1
    assert without_app.entity_counts.non_compliant_count == 0
    assert without_app.entity_counts.compliant_count == 1


# ── User Story 2 (P2): get_compliance_summary() (T015) ─────────────────────


async def test_compliance_summary_framework_count(_session) -> None:
    """US2 AS1: framework_count matches the number of registered frameworks."""
    summary = await get_compliance_summary(include_application=True, session=_session)
    assert summary.framework_count == 2  # fw-1, fw-2 seeded by the fixture


async def test_compliance_summary_coverage_percent_and_at_risk(_session) -> None:
    """FR-004, US2 AS2/AS3: coverage_percent and at_risk_count over entities' *overall*
    (cross-framework) derived status."""
    await _mk_control(_session, "c1", "fw-1")
    await _mk_control(_session, "c2", "fw-1")
    await _mk_control(_session, "c3", "fw-2")
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c1", "application_id", "app-1",
        ComplianceStatus.COMPLIANT,
    )
    await _mk_mapping(
        _session, cstore._control_capability_mapping, "c2", "capability_id", "cap-1",
        ComplianceStatus.NON_COMPLIANT,
    )
    await _mk_mapping(
        _session, cstore._control_design_mapping, "c3", "design_id", "design-1",
        ComplianceStatus.PARTIAL,
    )
    await _session.commit()

    summary = await get_compliance_summary(include_application=True, session=_session)
    # 3 distinct entities total, 1 compliant -> 100 * 1/3
    assert summary.coverage_percent == pytest.approx(100 * 1 / 3)
    assert summary.at_risk_count == 2  # non_compliant + partial


async def test_compliance_summary_coverage_percent_none_when_no_data(_session) -> None:
    """FR-009, Edge Cases, quickstart.md Scenario 6: null, never a bare 0.0, when nothing is
    mapped anywhere in the estate."""
    summary = await get_compliance_summary(include_application=True, session=_session)
    assert summary.coverage_percent is None
    assert summary.at_risk_count == 0


async def test_compliance_summary_excludes_application_when_not_permitted(_session) -> None:
    """FR-007: an Application-targeted entity is excluded from framework-wide figures too."""
    await _mk_control(_session, "c1", "fw-1")
    await _mk_mapping(
        _session, cstore._control_application_mapping, "c1", "application_id", "app-1",
        ComplianceStatus.NON_COMPLIANT,
    )
    await _session.commit()

    with_app = await get_compliance_summary(include_application=True, session=_session)
    without_app = await get_compliance_summary(include_application=False, session=_session)
    assert with_app.at_risk_count == 1
    assert with_app.coverage_percent == 0.0
    assert without_app.at_risk_count == 0
    assert without_app.coverage_percent is None
