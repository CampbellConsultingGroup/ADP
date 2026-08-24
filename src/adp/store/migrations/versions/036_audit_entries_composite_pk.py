"""Fix audit_entries.id collision across designs (ADP-a64).

next_audit_id(design) generates per-design-scoped ids (AUD-001, AUD-002, ...
first/second entry FOR THAT DESIGN), but audit_entries.id was a *global*
PRIMARY KEY (migration 001), and DesignStore.save() inserts with
ON CONFLICT DO NOTHING keyed on id alone. Once any design had an AUD-001,
every other design's own first audit entry (also id=AUD-001) silently failed
to insert -- confirmed live via psql before this fix: designs DSN-CHECKOUT,
DSN-INVENTORY, DSN-OMS (and others) each had exactly one AUD-001/AUD-002/...
row shared across all of them, not one set per design. The canonical
audit_log JSONB on design_versions.content was never affected (it's keyed
per-ArchitectureDescription, not a shared table) -- only this relational
mirror, used by governance.py's activity feed and /status reasoning-count
join, silently undercounted audit history for every design that wasn't
first to claim a given AUD-NNN id.

Fix: (design_id, id) composite primary key -- the id format itself
(AUD-NNN, ADP-SPEC-001's AuditEntryId pattern) is unchanged, it's just no
longer required to be globally unique, only unique per design (which is
exactly the scope next_audit_id already generates it at). DesignStore.save()
is updated in the same change to key its ON CONFLICT DO NOTHING on
(design_id, id).

This migration also backfills the audit_entries rows that were silently
dropped by the bug, reconstructed from the one place that still has them:
each design's own canonical audit_log on its latest design_versions.content
row (which -- unlike audit_entries -- was never missing anything). design_
version on backfilled rows is approximated as the design's current_version,
since audit_log entries don't record which version they were originally
written at and no read path (confirmed: governance.py's /status, /activity,
/activity/export queries) selects or displays design_version -- it only
feeds an index.

Revision ID: 036
Revises: 035
Create Date: 2026-08-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Replace the global single-column PK with a composite (design_id, id)
    #    PK -- id only needs to be unique within its own design, which is the
    #    scope next_audit_id() already generates it at.
    op.drop_constraint("audit_entries_pkey", "audit_entries", type_="primary")
    op.create_primary_key(
        "audit_entries_pkey", "audit_entries", ["design_id", "id"]
    )

    # 2. Backfill entries the collision silently dropped, reconstructed from
    #    each design's own canonical audit_log (design_versions.content at
    #    its current version -- audit_log is cumulative, so the latest
    #    version's copy holds the design's complete history).
    conn = op.get_bind()
    designs = conn.execute(
        sa.text("SELECT id, current_version FROM designs")
    ).fetchall()

    for design_id, current_version in designs:
        row = conn.execute(
            sa.text(
                "SELECT content FROM design_versions "
                "WHERE design_id = :design_id AND version_num = :version_num"
            ),
            {"design_id": design_id, "version_num": current_version},
        ).fetchone()
        if row is None:
            continue

        content = row[0]
        audit_log = content.get("audit_log") or []
        for entry in audit_log:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO audit_entries
                        (id, design_id, design_version, actor, action,
                         affected_entity, summary, timestamp, origin, created_at)
                    VALUES
                        (:id, :design_id, :design_version, :actor, :action,
                         :affected_entity, :summary, :timestamp, :origin, :timestamp)
                    ON CONFLICT (design_id, id) DO NOTHING
                    """
                ),
                {
                    "id": entry["id"],
                    "design_id": design_id,
                    "design_version": current_version,
                    "actor": entry["actor"],
                    "action": entry["action"],
                    "affected_entity": entry["affected_entity"],
                    "summary": entry["summary"],
                    "timestamp": entry["timestamp"],
                    "origin": entry["origin"],
                },
            )


def downgrade() -> None:
    # Lossy/best-effort: reverting to a single-column PK on id will fail if
    # real per-design id collisions now exist (the normal, intended state
    # once this fix has been live) -- that data isn't cleaned up here rather
    # than guessing which of two colliding designs' rows to discard.
    op.drop_constraint("audit_entries_pkey", "audit_entries", type_="primary")
    op.create_primary_key("audit_entries_pkey", "audit_entries", ["id"])
