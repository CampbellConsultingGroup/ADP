"""Regulatory Framework Legal Dates & Identity — COMPLY-01a.

Corrects RegulatoryFramework's single free-text `version` field, extending it (not replacing it)
with a regulation identity, four independent legal-event dates, a directly-set status, and two new
one-to-many concepts:

  - framework_application_phase — staged application dates for a framework (e.g. the EU AI Act's
    phased rollout: prohibited practices -> GPAI -> high-risk)
  - framework_amendment — later legal instruments that supplement a framework (e.g. DORA's growing
    stack of Regulatory Technical Standards)

Sourced from an addendum document (docs/compliance_update.md) authored outside this codebase. Its
own justification claimed the field being replaced is NUMERIC; it is actually VARCHAR(100) free
text, already holding real citation strings for the three currently-tracked frameworks (GDPR's
current value already crams two OJ citation dates into one string). Its draft schema used Integer
autoincrement PKs and a field, `official_title`, that doesn't exist -- corrected here to String(36)
UUID PKs (matching every other table in this codebase, no exception) and the real `name` field,
left untouched (spec.md Clarifications; research.md D1).

Every new column on regulatory_frameworks is additive: nullable, or NOT NULL with a server_default
that applies safely to the three existing rows with no backfill step (research.md D2). Zero existing
columns altered, renamed, or dropped -- name/jurisdiction/authority/version/effective_date/
source_url are completely untouched. regulation_number carries a UNIQUE constraint but stays
nullable; Postgres
does not treat multiple NULLs as a conflict under a unique constraint, so the three existing
frameworks (all currently unset) do not collide with each other or block this migration.

Both new tables use String(36) PKs and ON DELETE CASCADE back to their framework, matching
`controls`' own existing cascade-from-framework behavior (migration 032) exactly (research.md D6).

Revision ID: 035
Revises: 034
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── regulatory_frameworks: additive-only columns (research.md D2) ───────────
    op.add_column(
        "regulatory_frameworks", sa.Column("regulation_number", sa.String(100), nullable=True)
    )
    op.add_column(
        "regulatory_frameworks", sa.Column("celex_number", sa.String(50), nullable=True)
    )
    op.add_column("regulatory_frameworks", sa.Column("adoption_date", sa.Date(), nullable=True))
    op.add_column(
        "regulatory_frameworks", sa.Column("oj_publication_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "regulatory_frameworks", sa.Column("entry_into_force_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "regulatory_frameworks", sa.Column("consolidated_as_of", sa.Date(), nullable=True)
    )
    op.add_column(
        "regulatory_frameworks",
        sa.Column("status", sa.Text(), nullable=False, server_default="in_force"),
    )
    op.create_check_constraint(
        "ck_regulatory_frameworks_status",
        "regulatory_frameworks",
        "status IN ('in_force', 'amended', 'repealed', 'not_yet_applicable')",
    )
    # NULLs don't collide under a unique constraint -- safe against the three existing
    # frameworks, all currently unset (research.md D2).
    op.create_unique_constraint(
        "uq_regulatory_frameworks_regulation_number",
        "regulatory_frameworks",
        ["regulation_number"],
    )

    # ── framework_application_phase (research.md D1: String(36) PK, not Integer) ─
    op.create_table(
        "framework_application_phase",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase_label", sa.String(255), nullable=False),
        sa.Column("applies_from_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_framework_application_phase_framework_id",
        "framework_application_phase",
        ["framework_id"],
    )

    # ── framework_amendment ──────────────────────────────────────────────────────
    op.create_table(
        "framework_amendment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amending_celex", sa.String(50), nullable=True),
        sa.Column("amending_title", sa.String(255), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_framework_amendment_framework_id", "framework_amendment", ["framework_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_framework_amendment_framework_id", table_name="framework_amendment")
    op.drop_table("framework_amendment")
    op.drop_index(
        "ix_framework_application_phase_framework_id", table_name="framework_application_phase"
    )
    op.drop_table("framework_application_phase")
    op.drop_constraint(
        "uq_regulatory_frameworks_regulation_number", "regulatory_frameworks", type_="unique"
    )
    op.drop_constraint("ck_regulatory_frameworks_status", "regulatory_frameworks", type_="check")
    op.drop_column("regulatory_frameworks", "status")
    op.drop_column("regulatory_frameworks", "consolidated_as_of")
    op.drop_column("regulatory_frameworks", "entry_into_force_date")
    op.drop_column("regulatory_frameworks", "oj_publication_date")
    op.drop_column("regulatory_frameworks", "adoption_date")
    op.drop_column("regulatory_frameworks", "celex_number")
    op.drop_column("regulatory_frameworks", "regulation_number")
