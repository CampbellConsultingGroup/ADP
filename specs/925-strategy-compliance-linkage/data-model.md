# Phase 1 Data Model: Strategy Domain Linkage — COMPLY-05

**Feature**: 925-strategy-compliance-linkage
**Date**: 2026-08-19

## DDL (migration `034_strategy_compliance_links.py`, `down_revision = "033"`)

```python
def upgrade() -> None:
    # ── ObjectiveControlMapping ──────────────────────────────────────────────
    op.create_table(
        "objective_control_links",
        sa.Column(
            "objective_id", sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "control_id", sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ocl_control_id", "objective_control_links", ["control_id"])

    # ── InitiativeControlMapping — five parallel tables, one per ControlMapping
    #    target shape (research.md D1). Each carries a composite FK against the
    #    *composite primary key* of its corresponding control_*_mapping table
    #    (migration 033) -- Postgres supports FK(a, b) REFERENCES t(a, b).
    op.create_table(
        "initiative_control_capability_mapping",
        sa.Column(
            "initiative_id", sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("capability_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "capability_id"],
            ["control_capability_mapping.control_id", "control_capability_mapping.capability_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_iccm_mapping", "initiative_control_capability_mapping", ["control_id", "capability_id"]
    )

    op.create_table(
        "initiative_control_application_mapping",
        sa.Column(
            "initiative_id", sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "application_id"],
            ["control_application_mapping.control_id", "control_application_mapping.application_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icam_mapping", "initiative_control_application_mapping", ["control_id", "application_id"]
    )

    op.create_table(
        "initiative_control_design_mapping",
        sa.Column(
            "initiative_id", sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("design_id", sa.Text(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "design_id"],
            ["control_design_mapping.control_id", "control_design_mapping.design_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icdm_mapping", "initiative_control_design_mapping", ["control_id", "design_id"]
    )

    op.create_table(
        "initiative_control_pattern_mapping",
        sa.Column(
            "initiative_id", sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("pattern_id", sa.String(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "pattern_id"],
            ["control_pattern_mapping.control_id", "control_pattern_mapping.pattern_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icpm_mapping", "initiative_control_pattern_mapping", ["control_id", "pattern_id"]
    )

    op.create_table(
        "initiative_control_organization_mapping",
        sa.Column(
            "initiative_id", sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id"], ["control_organization_mapping.control_id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icom_mapping", "initiative_control_organization_mapping", ["control_id"]
    )


def downgrade() -> None:
    op.drop_table("initiative_control_organization_mapping")
    op.drop_table("initiative_control_pattern_mapping")
    op.drop_table("initiative_control_design_mapping")
    op.drop_table("initiative_control_application_mapping")
    op.drop_table("initiative_control_capability_mapping")
    op.drop_index("ix_ocl_control_id", table_name="objective_control_links")
    op.drop_table("objective_control_links")
```

Six new tables, zero altered existing tables, zero new columns on `strategic_objectives`,
`strategy_initiatives`, `controls`, or any `control_*_mapping` table.

## Entities

### ObjectiveControlMapping (`objective_control_links`)

| Column | Type | Notes |
|---|---|---|
| `objective_id` | `String(36)` | PK, FK → `strategic_objectives.id` `ON DELETE CASCADE` |
| `control_id` | `String(36)` | PK, FK → `controls.id` `ON DELETE CASCADE` |
| `created_at` | `DateTime(timezone=True)` | |

No `compliance_status` column, no `id` column — a bare existence link (spec.md Key Entities, Assumptions).

### InitiativeControlMapping (five tables — research.md D1)

Same shape repeated per target type; see DDL above. No `compliance_status` column on any of the five —
status is always read live from the corresponding `control_*_mapping` row via a mirror-table JOIN
(research.md D3), never stored on the link itself.

## Pydantic Models (`adp.strategy.models` / `adp.strategy.initiatives`)

```python
# adp.strategy.models — alongside ObjectiveDesignLinkCreate/ObjectiveApplicationLinkCreate

class ObjectiveControlLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control_id: str


# StrategicObjective (existing read model) gains one field, mirroring
# capability_ids/design_ids/application_ids's own established convention:
#   control_ids: list[str] = []


# adp.strategy.initiatives — alongside StrategyInitiative

class ControlMappingRef(BaseModel):
    """One InitiativeControlMapping target, plus the *live* status/evidence read
    straight off the linked ControlMapping row via mirror-table JOIN (research.md D3)
    -- never a value captured at link-creation time and never re-synced."""
    model_config = ConfigDict(extra="forbid")

    control_id: str
    target_type: MappingTargetType          # re-exported from adp.compliance.models
    target_id: str | None                   # None only when target_type == ORGANIZATION
    compliance_status: ComplianceStatus     # live, from adp.compliance.models
    evidence_ref: str | None
    assessed_at: date | None


# No request-body model for linking -- the link/unlink routes address the target entirely via
# path params (control_id/target_type/target_id), mirroring link_initiative_objective's own
# path-param-only shape (strategy/router.py:532-551), not a JSON-body shape.

# StrategyInitiative (existing read model) gains one field, mirroring
# objective_ids's own established convention:
#   control_mappings: list[ControlMappingRef] = []
```

`MappingTargetType`/`ComplianceStatus` are imported from `adp.compliance.models` — both packages already
sit in the same physical database and process; this is a type-only import (enums + a read model), not a
store-layer cross-package call, and mirrors `adp.chat.tools`'s existing precedent of importing typed
enums across domain package boundaries where the alternative (redefining the same five-value enum twice)
would violate ART-XIII's single-typed-contract intent.

## Store-layer additions

### `adp.strategy.store` (extends the existing `_designs`/`_applications` mirror-table idiom)

- `_objective_control_links` — `sa.Table` mirror of `objective_control_links` (no PK/FK constraints in
  Python; migration owns those — existing convention).
- `_controls_mirror` — read-only mirror of `controls`, columns `id`, `code`, `title`, `framework_id`
  (enough to resolve a Control's own display name without a second round-trip).
- Five read-only mirrors of the `control_*_mapping` tables, **including** `compliance_status`,
  `evidence_ref`, `assessed_at` (not just key columns — research.md D3).
- `control_exists(control_id, session) -> bool`
- `link_objective_control(objective_id, control_id, session) -> None` (raises `DuplicateLinkError`)
- `unlink_objective_control(objective_id, control_id, session) -> None` (raises `LinkNotFoundError`)
- `list_objectives_for_control(control_id, session) -> StrategicObjectiveListResponse` (reverse lookup,
  called from `adp.compliance.router` — mirrors `list_objectives_for_design`'s exact shape/docstring
  convention)

### `adp.strategy.initiatives` (extends the existing `_initiative_objective_links` pattern)

- `_initiative_control_mappings` — five `sa.Table` mirrors, one per target shape (matches the five
  physical tables 1:1).
- `link_initiative_control_mapping(initiative_id, control_id, target_type, target_id, session) -> None`
  (raises `ControlMappingNotFoundError` if the underlying `ControlMapping` row doesn't exist yet — an
  Initiative can only be linked to an *assessed* mapping, matching COMPLY-02's own
  `MappingTargetNotFoundError` precedent for "the thing you're pointing at must already exist"; raises
  `DuplicateLinkError` on a repeat link)
- `unlink_initiative_control_mapping(initiative_id, control_id, target_type, target_id, session) -> None`
- `_linked_control_mappings(initiative_id, session) -> list[ControlMappingRef]` (live JOIN across all
  five mirror tables, feeding `StrategyInitiative.control_mappings`)
- `list_initiatives_for_control_mapping(control_id, target_type, target_id, session) ->
  StrategyInitiativeListResponse` (reverse lookup, called from `adp.compliance.router`)

## State / validation rules

- `objective_id`/`control_id`/`initiative_id` must reference existing rows — enforced at the DB level by
  the FKs above; the router additionally does a friendly pre-check (mirrors `link_objective_design`'s
  existing `get_objective(...)`/`design_exists(...)` 404-before-insert pattern) so a bad ID gets a clean
  404 rather than a raw FK-violation 500.
- Linking an Initiative to a `ControlMapping` that does not yet exist (e.g., the Control has never been
  assessed against that target) is a 404, not an auto-created `not_assessed` mapping — COMPLY-02 already
  owns the lifecycle of creating a `ControlMapping` row; this feature only links to one that already exists.
- Re-linking an already-linked pair → 409 (`DuplicateLinkError`, research.md D5).
- Unlinking a pair that isn't linked → 404 (`LinkNotFoundError`).
- Deleting the Objective/Initiative/Control/`ControlMapping` cascades the link row away — no block, no
  orphan (spec.md FR-011).
