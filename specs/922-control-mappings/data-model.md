# Phase 1 Data Model: Control Mappings (Traceability Links) — COMPLY-02

**Feature**: 922-control-mappings
**Date**: 2026-08-18

## DDL (migration `033_control_mappings.py`, `down_revision = "032"`)

```python
def upgrade() -> None:
    _status_check = (
        "compliance_status IN "
        "('compliant','partial','non_compliant','not_assessed','not_applicable')"
    )

    op.create_table(
        "control_capability_mapping",
        sa.Column("control_id", sa.String(36), sa.ForeignKey("controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_id", sa.String(36), sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("control_id", "capability_id"),
        sa.CheckConstraint(_status_check, name="ck_ccm_status"),
    )
    op.create_index("ix_ccm_capability_id", "control_capability_mapping", ["capability_id"])

    op.create_table(
        "control_application_mapping",
        sa.Column("control_id", sa.String(36), sa.ForeignKey("controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("control_id", "application_id"),
        sa.CheckConstraint(_status_check, name="ck_cam_status"),
    )
    op.create_index("ix_cam_application_id", "control_application_mapping", ["application_id"])

    op.create_table(
        "control_design_mapping",
        sa.Column("control_id", sa.String(36), sa.ForeignKey("controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("design_id", sa.Text(), sa.ForeignKey("designs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("control_id", "design_id"),
        sa.CheckConstraint(_status_check, name="ck_cdm_status"),
    )
    op.create_index("ix_cdm_design_id", "control_design_mapping", ["design_id"])

    op.create_table(
        "control_pattern_mapping",
        sa.Column("control_id", sa.String(36), sa.ForeignKey("controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_id", sa.String(), sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("control_id", "pattern_id"),
        sa.CheckConstraint(_status_check, name="ck_cpm_status"),
    )
    op.create_index("ix_cpm_pattern_id", "control_pattern_mapping", ["pattern_id"])

    op.create_table(
        "control_organization_mapping",
        sa.Column("control_id", sa.String(36), sa.ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_status_check, name="ck_com_status"),
    )
```

Notes:
- `design_id` is `sa.Text()` (not `String(36)`) to match `designs.id`'s actual column type (confirmed in
  `001_initial_schema.py`); `pattern_id` is `sa.String()` unbounded to match `knowledge_items.id`
  (confirmed in `002_knowledge_schema.py`). Every other FK leg is `String(36)`, matching
  `controls.id`/`business_capabilities.id`/`applications.id`.
- Named `CHECK` constraints follow the existing `ck_<table-abbrev>_<column>` convention
  (`application_capability_links`' `ck_acl_fit_score` is the direct precedent).
- An index on each table's non-`control_id` FK leg mirrors `application_capability_links`'
  `ix_acl_capability_id` — supports the reverse-lookup queries (D7) efficiently.
- No index is needed on `control_id` alone beyond what the composite PK (or, for
  `control_organization_mapping`, the single-column PK) already provides — the forward lookup
  (`GET .../controls/{control_id}/mappings`) is a PK-prefix scan on every table.

## Pydantic Models (`adp/compliance/models.py` additions)

```python
class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"
    NOT_APPLICABLE = "not_applicable"


class MappingTargetType(StrEnum):
    CAPABILITY = "capability"
    APPLICATION = "application"
    DESIGN = "design"
    PATTERN = "pattern"
    ORGANIZATION = "organization"


class ControlMapping(BaseModel):
    """Read model. target_id is None only when target_type == ORGANIZATION."""
    model_config = ConfigDict(extra="forbid")

    control_id: str
    target_type: MappingTargetType
    target_id: str | None
    compliance_status: ComplianceStatus
    evidence_ref: str | None
    assessed_at: date | None
    assessed_by: str | None
    created_at: datetime


class ControlMappingWrite(BaseModel):
    """Write model for PUT (create-or-update, D3)."""
    model_config = ConfigDict(extra="forbid")

    compliance_status: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    evidence_ref: str | None = None
    assessed_at: date | None = None
    assessed_by: str | None = None


class ControlMappingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ControlMapping]
    total: int


# ── Typed exceptions ────────────────────────────────────────────────────────

class ControlNotFoundError(Exception):
    """control_id does not reference an existing Control. Router maps to HTTP 404."""


class MappingTargetNotFoundError(Exception):
    """target_id does not reference an existing Capability/Application/Design/knowledge item.
    Router maps to HTTP 404."""

    def __init__(self, target_type: str, target_id: str) -> None:
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(f"{target_type} {target_id!r} not found")


class InvalidPatternTargetError(Exception):
    """target_id resolves to a knowledge_items row whose kind != 'pattern' (D5).
    Router maps to HTTP 422."""

    def __init__(self, target_id: str, actual_kind: str) -> None:
        self.target_id = target_id
        self.actual_kind = actual_kind
        super().__init__(f"knowledge item {target_id!r} has kind {actual_kind!r}, not 'pattern'")


class MappingNotFoundError(Exception):
    """Raised by delete when the (control_id, target) pair has no existing mapping.
    Router maps to HTTP 404."""
```

## Store Table Definitions (`adp/compliance/store.py` additions)

Five new `sa.Table()` objects (`_control_capability_mapping`, `_control_application_mapping`,
`_control_design_mapping`, `_control_pattern_mapping`, `_control_organization_mapping`), DML-only, mirroring
the shape above — migration owns constraints (existing module convention).

Plus four narrow mirror tables (research.md D4), each carrying only the columns needed for existence/kind
validation, not full domain objects:

```python
_capabilities_mirror = sa.Table(
    "business_capabilities", _metadata, sa.Column("id", sa.String(36), primary_key=True)
)
_applications_mirror = sa.Table(
    "applications", _metadata, sa.Column("id", sa.String(36), primary_key=True)
)
_designs_mirror = sa.Table(
    "designs", _metadata, sa.Column("id", sa.Text(), primary_key=True)
)
_knowledge_items_mirror = sa.Table(
    "knowledge_items", _metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("kind", sa.Text(), nullable=False),
)
```

## Store Functions (`adp/compliance/store.py` additions)

- `get_control(control_id, session) -> Control | None` — new; COMPLY-01 never needed a standalone getter
  outside the framework-detail tree assembly.
- `capability_exists`, `application_exists`, `design_exists` — `(id, session) -> bool`, mirroring
  `adp.strategy.store`'s identical helpers.
- `get_knowledge_item_kind(pattern_id, session) -> str | None` — returns the row's `kind`, or `None` if it
  doesn't exist (feeds both existence and D5's kind check in one query).
- `upsert_capability_mapping`, `upsert_application_mapping`, `upsert_design_mapping`,
  `upsert_pattern_mapping`, `upsert_organization_mapping` — each validates its target (raising
  `ControlNotFoundError` / `MappingTargetNotFoundError` / `InvalidPatternTargetError` as applicable), then
  select-then-branch upsert (D3, revised during implementation — SQLite-contract-test-portable, mirrors `DesignStore.save()`'s own idiom), returns the resulting `ControlMapping`.
- `delete_capability_mapping`, ..., `delete_organization_mapping` — each raises `MappingNotFoundError` if no
  row matched (D6).
- `list_mappings_for_control(control_id, session) -> list[ControlMapping]` — unions all five tables'
  rows for one `control_id`, tagging each with its `target_type`.
- `list_mappings_for_capability`, `list_mappings_for_application`, `list_mappings_for_design`,
  `list_mappings_for_pattern` — `(target_id, session) -> list[ControlMapping]`, one table each, all rows
  tagged `target_type` accordingly.

## Key Entities Recap (from spec.md, restated with concrete shape)

- **Control Mapping**: five parallel table shapes sharing one logical read model (`ControlMapping`), unified
  by `target_type` + `target_id` (the latter `None` only for the organization-wide shape). A mapping's
  identity is `(control_id, target_type, target_id)`; `compliance_status` defaults to `not_assessed` when
  not supplied.
