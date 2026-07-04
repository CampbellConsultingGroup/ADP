"""Typed audit record writer for ADP consequential actions (FR-005 / ART-IX).

write_audit_record is the single write path for audit entries. All callers
must use it — never construct and append AuditEntry directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from adp.authz.permissions import requires_confirmation
from adp.authz.roles import ActionType

if TYPE_CHECKING:
    from adp.models import ArchitectureDescription
    from adp.store import DesignStore

_AUD_ID_RE = re.compile(r"^AUD-(\d+)$")


def next_audit_id(design: Any) -> str:
    """Return the next AUD-NNN id by finding max(existing) + 1.

    Public utility for any module that needs to generate an audit entry ID
    without going through write_audit_record (ADP-SPEC-023 Move B).
    Uses max-based logic so it is safe when prior entries exist in the database.
    """
    max_n = 0
    for entry in (design.audit_log or []):
        m = _AUD_ID_RE.match(entry.id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"AUD-{(max_n + 1):03d}"


@dataclass
class AuditRecord:
    """Write-side record for a consequential action.

    Converted to AuditEntry (ADP-SPEC-001 model) by write_audit_record.
    """

    actor: str
    action: ActionType
    affected_entity: str
    summary: str
    origin: Literal["human", "ai"]
    confirmation_id: str | None = None


async def write_audit_record(
    record: AuditRecord,
    design: "ArchitectureDescription",
    store: "DesignStore",
) -> str:
    """Append an AuditEntry derived from record to design.audit_log and save atomically.

    Returns the generated audit_entry_id (AUD-NNN).

    Raises ValueError if:
      - action requires confirmation but confirmation_id is None
      - summary exceeds 240 characters
    """
    from adp.models import AuditEntry

    if len(record.summary) > 240:
        raise ValueError(
            f"summary must be ≤ 240 characters, got {len(record.summary)}"
        )

    if requires_confirmation(record.action) and record.confirmation_id is None:
        raise ValueError(
            f"action {record.action!r} requires a confirmation_id "
            "but none was provided (ART-VIII / FR-004)"
        )

    # Generate ID as max(existing AUD-NNN) + 1 to handle non-sequential pre-existing entries.
    max_n = 0
    for entry in design.audit_log:
        m = _AUD_ID_RE.match(entry.id)
        if m:
            max_n = max(max_n, int(m.group(1)))

    n = max_n + 1
    if n > 999:
        raise ValueError(
            "AuditEntry ID cap exceeded (AUD-999). "
            "Amend ADP-SPEC-001 to extend the AuditEntryId pattern."
        )

    audit_entry_id = f"AUD-{n:03d}"

    new_entry = AuditEntry(
        id=audit_entry_id,
        actor=record.actor,
        action=record.action.value,
        affected_entity=record.affected_entity,
        summary=record.summary,
        timestamp=datetime.now(timezone.utc),
        origin=record.origin,
    )

    design.audit_log.append(new_entry)
    await store.save(design, actor=record.actor)
    return audit_entry_id
