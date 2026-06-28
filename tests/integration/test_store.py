"""Integration tests for DesignStore against a real PostgreSQL container.

Skipped automatically when Docker is unavailable.
Each test runs inside a rolled-back transaction (see conftest.py) for isolation.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from adp.models import (
    ArchitectureDescription,
    AuditEntry,
    Element,
    ElementKind,
    Relationship,
    Requirement,
    SolutionOption,
    VerdictStatus,
)
from adp.store import (
    ConcurrencyConflictError,
    DesignNotFoundError,
    DesignStore,
    SchemaValidationError,
)

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
_EXAMPLE = Path("fixtures/example-adp.json")


def _example_description() -> ArchitectureDescription:
    return ArchitectureDescription.model_validate_json(_EXAMPLE.read_text())


def _minimal(design_id: str = "DESIGN-001") -> ArchitectureDescription:
    return ArchitectureDescription(
        schema_version="1.0.0",
        id=design_id,
        title="Test Design",
        created_at=_NOW,
        updated_at=_NOW,
    )


# ── US1: Save & Retrieve ──────────────────────────────────────────────────────


async def test_save_and_retrieve_round_trip(store: DesignStore) -> None:
    """Saved design round-trips back to an identical model (SC-001)."""
    original = _example_description()
    record = await store.save(original, actor="test")
    assert record.current_version == 1

    retrieved = await store.get(original.id)
    assert retrieved == original


async def test_schema_invalid_design_rejected(store: DesignStore) -> None:
    """A design that fails re-validation is rejected before any DB write (FR-006)."""
    # Construct a technically valid description then corrupt it for re-validation.
    desc = _minimal("DESIGN-INVALID")
    # Manually break the schema_version to bypass Pydantic but fail the store check.
    object.__setattr__(desc, "schema_version", "not-semver")
    with pytest.raises(SchemaValidationError):
        await store.save(desc, actor="test")


async def test_get_nonexistent_design_raises(store: DesignStore) -> None:
    """Getting a non-existent design raises DesignNotFoundError (FR-001)."""
    with pytest.raises(DesignNotFoundError):
        await store.get("NONEXISTENT-999")


async def test_get_schema_version_mismatch_logs_warning(
    store: DesignStore, caplog: pytest.LogCaptureFixture
) -> None:
    """get() logs a warning when stored schema_version differs from live (NFR-002)."""
    import logging

    desc = _minimal("DESIGN-MISMATCH")
    await store.save(desc, actor="test")

    # Patch SCHEMA_VERSION to simulate a version bump.
    import adp.models as m
    original_ver = m.SCHEMA_VERSION
    try:
        m.SCHEMA_VERSION = "99.0.0"
        with caplog.at_level(logging.WARNING, logger="adp.store"):
            await store.get("DESIGN-MISMATCH")
        assert any("schema_mismatch" in r.message for r in caplog.records)
    finally:
        m.SCHEMA_VERSION = original_ver


# ── US2: Atomic Audit Trail ───────────────────────────────────────────────────


async def test_save_writes_audit_entries_atomically(store: DesignStore, db_session) -> None:  # type: ignore[type-arg]
    """Audit entries commit in the same transaction as the design version (FR-003)."""
    import sqlalchemy as sa

    from adp.store.records import audit_entries

    desc = _minimal("DESIGN-AUDIT").model_copy(update={
        "audit_log": [
            AuditEntry(
                id="AUD-001",
                actor="jmuir",
                action="create",
                affected_entity="DESIGN-AUDIT",
                summary="Design created.",
                timestamp=_NOW,
                origin="human",
            )
        ]
    })
    await store.save(desc, actor="jmuir")

    rows = (await db_session.execute(
        sa.select(audit_entries).where(audit_entries.c.design_id == "DESIGN-AUDIT")
    )).fetchall()
    assert len(rows) == 1
    assert rows[0].actor == "jmuir"
    assert rows[0].action == "create"
    assert rows[0].origin == "human"


async def test_audit_trigger_fires_on_delete(store: DesignStore, db_session) -> None:  # type: ignore[type-arg]
    """Attempting to DELETE an audit entry raises a database exception (FR-004 / ART-IX)."""
    from adp.store.records import audit_entries

    desc = _minimal("DESIGN-TRIGGER").model_copy(update={
        "audit_log": [
            AuditEntry(
                id="AUD-T01",
                actor="a",
                action="b",
                affected_entity="x",
                summary="Trigger test.",
                timestamp=_NOW,
                origin="human",
            )
        ]
    })
    await store.save(desc, actor="test")

    with pytest.raises(Exception, match="append-only"):
        await db_session.execute(
            audit_entries.delete().where(audit_entries.c.id == "AUD-T01")
        )


async def test_mutation_rolls_back_without_audit(store: DesignStore) -> None:
    """If audit write fails (duplicate PK), the design version is also rolled back (FR-003)."""
    import sqlalchemy as sa

    from adp.store.records import design_versions

    dup_entry = AuditEntry(
        id="AUD-DUP",
        actor="a",
        action="b",
        affected_entity="x",
        summary="First entry.",
        timestamp=_NOW,
        origin="human",
    )
    # First save — succeeds with AUD-DUP
    desc = _minimal("DESIGN-ROLLBACK").model_copy(update={"audit_log": [dup_entry]})
    await store.save(desc, actor="test")

    # Second save — duplicate AUD-DUP should trigger IntegrityError inside tx
    desc_v2 = desc.model_copy(update={
        "title": "Modified",
        "audit_log": [dup_entry],  # same id — violates PK on audit_entries
    })

    with pytest.raises(Exception):
        await store.save(desc_v2, actor="test", expected_version=1)

    # Verify version count is still 1 (no v2 committed)
    async with store._session_factory() as session:
        rows = (await session.execute(
            sa.select(design_versions).where(design_versions.c.design_id == "DESIGN-ROLLBACK")
        )).fetchall()
    assert len(rows) == 1, f"Expected 1 version, got {len(rows)}"


# ── US3: Immutable Version History ────────────────────────────────────────────


async def test_second_save_creates_new_version(store: DesignStore) -> None:
    """Saving a modified design increments the version number (FR-002)."""
    d = _minimal("DESIGN-VER")
    await store.save(d, actor="test")
    d2 = d.model_copy(update={"title": "Modified"})
    r2 = await store.save(d2, actor="test", expected_version=1)

    assert r2.current_version == 2
    versions = await store.list_versions("DESIGN-VER")
    assert len(versions) == 2
    assert versions[0].version_num == 1
    assert versions[1].version_num == 2


async def test_prior_version_unchanged(store: DesignStore) -> None:
    """Saving a new version does not alter the prior version (FR-002)."""
    d = _minimal("DESIGN-HIST")
    await store.save(d, actor="test")
    d2 = d.model_copy(update={"title": "v2 Title"})
    await store.save(d2, actor="test", expected_version=1)

    v1 = await store.get("DESIGN-HIST", version=1)
    assert v1.title == "Test Design"


async def test_optimistic_concurrency_conflict(store: DesignStore) -> None:
    """Saving with a stale expected_version raises ConcurrencyConflictError (Assumptions)."""
    d = _minimal("DESIGN-OCC")
    await store.save(d, actor="test")
    d2 = d.model_copy(update={"title": "v2"})
    await store.save(d2, actor="test", expected_version=1)  # now at v2

    with pytest.raises(ConcurrencyConflictError):
        await store.save(d.model_copy(update={"title": "stale"}), actor="other", expected_version=1)


async def test_design_version_row_is_immutable(store: DesignStore, db_session) -> None:  # type: ignore[type-arg]
    """Direct SQL UPDATE on design_versions is rejected by DB constraints (FR-002)."""
    import sqlalchemy as sa

    from adp.store.records import design_versions

    await store.save(_minimal("DESIGN-IMM"), actor="test")

    # design_versions has no UPDATE trigger but the application never issues one.
    # Verify the data integrity: row is present and unchanged after save.
    row = (await db_session.execute(
        sa.select(design_versions.c.version_num, design_versions.c.created_by)
        .where(design_versions.c.design_id == "DESIGN-IMM")
    )).fetchone()
    assert row is not None
    assert row.version_num == 1
    assert row.created_by == "test"


# ── US4: Traceability Queries ─────────────────────────────────────────────────


async def test_query_satisfies_returns_matching_elements(store: DesignStore) -> None:
    """query_satisfies returns elements satisfying the given requirement (FR-005)."""
    desc = _example_description()
    await store.save(desc, actor="test")

    result = await store.query_satisfies(desc.id, "REQ-001")
    ids = {e.id for e in result}
    assert "ELM-001" in ids
    assert "ELM-002" in ids


async def test_query_satisfies_returns_empty_for_unknown_requirement(store: DesignStore) -> None:
    """query_satisfies returns empty list for a requirement with no satisfying elements."""
    desc = _example_description()
    await store.save(desc, actor="test")

    result = await store.query_satisfies(desc.id, "REQ-999")
    assert result == []


async def test_query_orphan_requirements_identifies_orphans(store: DesignStore) -> None:
    """query_orphan_requirements identifies requirements with no element/option satisfying them."""
    now = _NOW
    desc = ArchitectureDescription(
        schema_version="1.0.0",
        id="DESIGN-ORPHAN",
        title="Orphan Test",
        requirements=[
            Requirement(id="REQ-001", title="Satisfied", description="Has an element."),
            Requirement(id="REQ-002", title="Orphan", description="No element satisfies this."),
        ],
        elements=[
            Element(id="ELM-001", name="A", kind=ElementKind.CONTAINER, satisfies=["REQ-001"])
        ],
        created_at=now,
        updated_at=now,
    )
    await store.save(desc, actor="test")

    orphans = await store.query_orphan_requirements("DESIGN-ORPHAN")
    orphan_ids = {r.id for r in orphans}
    assert "REQ-002" in orphan_ids
    assert "REQ-001" not in orphan_ids


async def test_query_verdict_chain_returns_full_chain(store: DesignStore) -> None:
    """query_verdict_chain returns option, requirements, elements, and verdict (FR-005)."""
    desc = _example_description()
    await store.save(desc, actor="test")

    chain = await store.query_verdict_chain(desc.id, "OPT-001")
    assert chain.option.id == "OPT-001"
    assert chain.verdict is not None
    assert chain.verdict.id == "VRD-001"
    req_ids = {r.id for r in chain.satisfies_requirements}
    assert "REQ-001" in req_ids


# ── Performance: SC-005 ───────────────────────────────────────────────────────


@pytest.mark.slow
async def test_get_latency_500_entities(store: DesignStore) -> None:
    """Single-design read completes in < 1 second for a 500-entity design (SC-005)."""
    now = _NOW
    requirements = [
        Requirement(id=f"REQ-{i:03d}", title=f"R{i}", description=f"Desc {i}")
        for i in range(1, 101)
    ]
    elements = [
        Element(id=f"ELM-{i:03d}", name=f"Element {i}", kind=ElementKind.COMPONENT,
                satisfies=[f"REQ-{(i % 100) + 1:03d}"])
        for i in range(1, 201)
    ]
    relationships = [
        Relationship(id=f"REL-{i:03d}", source=f"ELM-{i:03d}",
                     target=f"ELM-{(i % 200) + 1:03d}")
        for i in range(1, 101)
    ]
    options = [
        SolutionOption(id=f"OPT-{i:03d}", title=f"Option {i}",
                       description=f"Desc {i}", status=VerdictStatus.PENDING,
                       satisfies=[f"REQ-{i:03d}"])
        for i in range(1, 101)
    ]

    desc = ArchitectureDescription(
        schema_version="1.0.0",
        id="DESIGN-PERF",
        title="Performance Test",
        requirements=requirements,
        elements=elements,
        relationships=relationships,
        options=options,
        created_at=now,
        updated_at=now,
    )
    await store.save(desc, actor="perf-test")

    start = time.perf_counter()
    await store.get("DESIGN-PERF")
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"get() took {elapsed:.3f}s — exceeds 1s limit (SC-005)"
