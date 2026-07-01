"""Tests for AuditRecord and write_audit_record (US4 / FR-005 / SC-004)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from adp.audit import AuditRecord, write_audit_record
from adp.authz.roles import ActionType
from adp.models import ArchitectureDescription

_NOW = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


def _minimal_design(design_id: str = "DESIGN-001") -> ArchitectureDescription:
    return ArchitectureDescription(
        schema_version="1.0.0",
        id=design_id,
        title="Test Design",
        created_at=_NOW,
        updated_at=_NOW,
    )


@pytest.fixture()
def mock_store() -> AsyncMock:
    store = AsyncMock()
    # save() returns a DesignRecord-like object; stub it
    from adp.store.records import DesignRecord
    store.save.return_value = DesignRecord(
        design_id="DESIGN-001",
        current_version=2,
        title="Test Design",
        created_at=_NOW,
        updated_at=_NOW,
    )
    return store


# ── Test: record is appended and store is called ──────────────────────────────


@pytest.mark.asyncio
async def test_write_audit_record_appends_entry(mock_store: AsyncMock) -> None:
    """Audit entry is appended to design.audit_log and store.save is called (FR-005)."""
    design = _minimal_design()
    record = AuditRecord(
        actor="sub:architect-123",
        action=ActionType.WRITE_DESIGN,
        affected_entity="DESIGN-001",
        summary="Added API Gateway element.",
        origin="human",
    )

    await write_audit_record(record, design, mock_store)

    mock_store.save.assert_called_once()
    saved_description = mock_store.save.call_args[0][0]
    assert len(saved_description.audit_log) == 1

    entry = saved_description.audit_log[0]
    assert entry.actor == "sub:architect-123"
    assert entry.action == "write_design"
    assert entry.affected_entity == "DESIGN-001"
    assert entry.summary == "Added API Gateway element."
    assert entry.origin == "human"


@pytest.mark.asyncio
async def test_write_audit_record_passes_actor_to_store(mock_store: AsyncMock) -> None:
    """store.save is called with actor=record.actor (ART-IX — no caller-supplied override)."""
    design = _minimal_design()
    record = AuditRecord(
        actor="sub:architect-123",
        action=ActionType.WRITE_DESIGN,
        affected_entity="DESIGN-001",
        summary="Created design.",
        origin="human",
    )

    await write_audit_record(record, design, mock_store)

    _, kwargs = mock_store.save.call_args
    assert kwargs.get("actor") == "sub:architect-123"


# ── Test: confirmation_id required for consequential actions ─────────────────


@pytest.mark.asyncio
async def test_write_audit_record_rejects_missing_confirmation_id(
    mock_store: AsyncMock,
) -> None:
    """Consequential action without confirmation_id raises ValueError; store not called."""
    design = _minimal_design()
    record = AuditRecord(
        actor="sub:architect-123",
        action=ActionType.CONFIRM_RECOMMENDATION,
        affected_entity="OPT-001",
        summary="Accepted recommendation.",
        origin="human",
        confirmation_id=None,  # missing — should fail
    )

    with pytest.raises(ValueError, match="confirmation_id"):
        await write_audit_record(record, design, mock_store)

    mock_store.save.assert_not_called()


@pytest.mark.asyncio
async def test_write_audit_record_accepts_confirmation_id(mock_store: AsyncMock) -> None:
    """Consequential action with confirmation_id proceeds normally."""
    design = _minimal_design()
    record = AuditRecord(
        actor="sub:architect-123",
        action=ActionType.CONFIRM_RECOMMENDATION,
        affected_entity="OPT-001",
        summary="Accepted recommendation.",
        origin="human",
        confirmation_id="op-uuid-here",
    )

    await write_audit_record(record, design, mock_store)
    mock_store.save.assert_called_once()


# ── Test: summary length validation ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_audit_record_rejects_long_summary(mock_store: AsyncMock) -> None:
    """Summary exceeding 240 characters raises ValueError; store not called."""
    design = _minimal_design()
    record = AuditRecord(
        actor="a",
        action=ActionType.WRITE_DESIGN,
        affected_entity="DESIGN-001",
        summary="x" * 241,
        origin="human",
    )

    with pytest.raises(ValueError, match="summary"):
        await write_audit_record(record, design, mock_store)

    mock_store.save.assert_not_called()


# ── Test: returned audit_entry_id format ─────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_entry_id_is_returned(mock_store: AsyncMock) -> None:
    """write_audit_record returns a non-empty AUD-NNN format string."""
    design = _minimal_design()
    record = AuditRecord(
        actor="sub:architect-123",
        action=ActionType.WRITE_DESIGN,
        affected_entity="DESIGN-001",
        summary="Created design.",
        origin="human",
    )

    audit_entry_id = await write_audit_record(record, design, mock_store)

    assert re.match(r"^AUD-\d{3}$", audit_entry_id), (
        f"Expected AUD-NNN format, got {audit_entry_id!r}"
    )


@pytest.mark.asyncio
async def test_audit_entry_id_increments_from_existing(mock_store: AsyncMock) -> None:
    """ID is max(existing) + 1, not len(audit_log) + 1."""
    from adp.models import AuditEntry

    design = _minimal_design()
    # Pre-populate with AUD-005 to test max-based increment
    design.audit_log.append(
        AuditEntry(
            id="AUD-005",
            actor="a",
            action="write_design",
            affected_entity="DESIGN-001",
            summary="Prior entry.",
            timestamp=_NOW,
            origin="human",
        )
    )

    record = AuditRecord(
        actor="b",
        action=ActionType.ADD_FINDING,
        affected_entity="DESIGN-001",
        summary="New finding.",
        origin="human",
    )
    entry_id = await write_audit_record(record, design, mock_store)
    assert entry_id == "AUD-006", f"Expected AUD-006 but got {entry_id}"
