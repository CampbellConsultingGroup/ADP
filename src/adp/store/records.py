"""SQLAlchemy ORM table definitions and store return-type dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from adp.models import Element, Requirement, SolutionOption, Verdict

metadata = MetaData()

designs = Table(
    "designs",
    metadata,
    Column("id", String, primary_key=True),
    Column("current_version", Integer, nullable=False),
    Column("title", Text, nullable=False),
    Column("schema_version_at_creation", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    # ADP-SPEC-030: Design lifecycle columns (added by migration 006)
    Column("lifecycle_status", Text, nullable=False, server_default="draft"),
    Column("proposed_date", DateTime(timezone=True), nullable=True),
    Column("current_since", DateTime(timezone=True), nullable=True),
    Column("review_due", DateTime(timezone=True), nullable=True),
    Column("retirement_date", DateTime(timezone=True), nullable=True),
)

design_versions = Table(
    "design_versions",
    metadata,
    Column("design_id", String, nullable=False),
    Column("version_num", Integer, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("content", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", Text, nullable=False),
)

# Composite primary key expressed as a constraint in the migration;
# SQLAlchemy Core doesn't require it on the Table object for queries.

audit_entries = Table(
    "audit_entries",
    metadata,
    Column("id", Text, primary_key=True),
    Column("design_id", String, nullable=False),
    Column("design_version", Integer, nullable=False),
    Column("actor", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("affected_entity", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("origin", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_audit_entries_design", "design_id", "design_version"),
)


# ── Store return types ─────────────────────────────────────────────────────────


@dataclass
class DesignRecord:
    """Current state of a design in the store."""

    design_id: str
    current_version: int
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass
class DesignVersion:
    """Metadata for one immutable snapshot — no content field."""

    design_id: str
    version_num: int
    schema_version: str
    created_at: datetime
    created_by: str


@dataclass
class VerdictChain:
    """Full traceability thread for one SolutionOption."""

    option: SolutionOption
    satisfies_requirements: list[Requirement]
    satisfying_elements: list[Element]
    verdict: Verdict | None
