# Phase 1 Data Model: Regulatory Framework Legal Dates & Identity (COMPLY-01a)

**Feature**: 926-framework-versioning-correction
**Date**: 2026-08-19

## DDL (migration `035_framework_legal_dates.py`, `down_revision = "034"`)

```python
def upgrade() -> None:
    # ── regulatory_frameworks: additive-only columns (research.md D2) ───────────
    op.add_column("regulatory_frameworks", sa.Column("regulation_number", sa.String(100), nullable=True))
    op.add_column("regulatory_frameworks", sa.Column("celex_number", sa.String(50), nullable=True))
    op.add_column("regulatory_frameworks", sa.Column("adoption_date", sa.Date(), nullable=True))
    op.add_column("regulatory_frameworks", sa.Column("oj_publication_date", sa.Date(), nullable=True))
    op.add_column("regulatory_frameworks", sa.Column("entry_into_force_date", sa.Date(), nullable=True))
    op.add_column("regulatory_frameworks", sa.Column("consolidated_as_of", sa.Date(), nullable=True))
    op.add_column(
        "regulatory_frameworks",
        sa.Column("status", sa.Text(), nullable=False, server_default="in_force"),
    )
    op.create_check_constraint(
        "ck_regulatory_frameworks_status",
        "regulatory_frameworks",
        "status IN ('in_force', 'amended', 'repealed', 'not_yet_applicable')",
    )
    # NULLs don't collide under a unique constraint (research.md D2) -- safe against
    # the three existing frameworks, all currently unset.
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
            "framework_id", sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"), nullable=False,
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
        "framework_application_phase", ["framework_id"],
    )

    # ── framework_amendment ──────────────────────────────────────────────────────
    op.create_table(
        "framework_amendment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id", sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"), nullable=False,
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
```

Zero existing columns altered, renamed, or dropped. Zero data loss against the three currently-tracked
frameworks (spec.md FR-004, SC-001).

## Entities

### RegulatoryFramework (existing, extended)

| Column | Type | Notes |
|---|---|---|
| `id`..`updated_at` | *(unchanged)* | `name`/`jurisdiction`/`authority`/`version`/`effective_date`/`source_url` untouched |
| `regulation_number` | `String(100)`, nullable, `UNIQUE` | e.g. `"2016/679"` — new identity field, additive to (not replacing) `name` |
| `celex_number` | `String(50)`, nullable | e.g. `"32016R0679"` |
| `adoption_date` | `Date`, nullable | |
| `oj_publication_date` | `Date`, nullable | |
| `entry_into_force_date` | `Date`, nullable | |
| `consolidated_as_of` | `Date`, nullable | latest known consolidation date; no history kept (research.md, spec.md Assumptions) |
| `status` | `Text`, `NOT NULL DEFAULT 'in_force'`, `CHECK` | `in_force` / `amended` / `repealed` / `not_yet_applicable` — directly set (research.md D3) |

### FrameworkApplicationPhase (new)

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` PK | |
| `framework_id` | `String(36)` FK → `regulatory_frameworks.id`, `ON DELETE CASCADE` | |
| `phase_label` | `String(255)`, `NOT NULL` | free text this pass (research.md/spec.md Assumptions) |
| `applies_from_date` | `Date`, `NOT NULL` | |
| `description` | `Text`, nullable | |
| `created_at` | `DateTime(timezone=True)` | |

Zero, one, or many per framework (spec.md FR-006).

### FrameworkAmendment (new)

| Column | Type | Notes |
|---|---|---|
| `id` | `String(36)` PK | |
| `framework_id` | `String(36)` FK → `regulatory_frameworks.id`, `ON DELETE CASCADE` | |
| `amending_celex` | `String(50)`, nullable | |
| `amending_title` | `String(255)`, `NOT NULL` | |
| `effective_date` | `Date`, nullable | |
| `created_at` | `DateTime(timezone=True)` | |

Zero, one, or many per framework; no limit (spec.md SC-004).

## Pydantic Models (`adp.compliance.models`)

```python
FrameworkStatus = Literal["in_force", "amended", "repealed", "not_yet_applicable"]


class FrameworkApplicationPhase(BaseModel):
    """Read model."""
    model_config = ConfigDict(extra="forbid")

    id: str
    framework_id: str
    phase_label: str
    applies_from_date: date
    description: str | None
    created_at: datetime


class FrameworkApplicationPhaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase_label: str = Field(max_length=255)
    applies_from_date: date
    description: str | None = None

    @field_validator("phase_label")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class FrameworkAmendment(BaseModel):
    """Read model."""
    model_config = ConfigDict(extra="forbid")

    id: str
    framework_id: str
    amending_celex: str | None
    amending_title: str
    effective_date: date | None
    created_at: datetime


class FrameworkAmendmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amending_celex: str | None = Field(default=None, max_length=50)
    amending_title: str = Field(max_length=255)
    effective_date: date | None = None

    @field_validator("amending_title")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


# RegulatoryFramework / RegulatoryFrameworkCreate / RegulatoryFrameworkUpdate each gain, all optional:
#   regulation_number: str | None = Field(default=None, max_length=100)
#   celex_number: str | None = Field(default=None, max_length=50)
#   adoption_date: date | None = None
#   oj_publication_date: date | None = None
#   entry_into_force_date: date | None = None
#   consolidated_as_of: date | None = None
#   status: FrameworkStatus = "in_force"   # Create only defaults; Update leaves unset = unchanged

# RegulatoryFrameworkDetail (already nests `controls: list[ControlNode]`) gains, research.md D4:
#   application_phases: list[FrameworkApplicationPhase] = []
#   amendments: list[FrameworkAmendment] = []
```

## Typed exceptions (`adp.compliance.models`)

- `DuplicateRegulationNumberError(regulation_number)` — mirrors `DuplicateControlCodeError`'s shape.
  Router maps to HTTP 409.
- `ApplicationPhaseNotFoundError(phase_id)` — router maps to HTTP 404.
- `AmendmentNotFoundError(amendment_id)` — router maps to HTTP 404.

## Store-layer additions (`adp.compliance.store`)

- `_frameworks` `Table()` gains the seven new columns (DML-only, migration owns constraints — existing
  convention).
- `_framework_application_phases`, `_framework_amendments` — two new DML-only `Table()`s.
- `_row_to_framework()` extended to read the new columns.
- `create_framework()` / `update_framework()` extended to accept the new fields; both catch a
  unique-violation on `regulation_number` → `DuplicateRegulationNumberError` (same catch-and-translate
  shape `link_objective_control` etc. already use elsewhere in this codebase for unique violations).
- `add_application_phase(framework_id, data, session) -> FrameworkApplicationPhase`
- `list_application_phases(framework_id, session) -> list[FrameworkApplicationPhase]` (ordered by
  `applies_from_date`)
- `delete_application_phase(framework_id, phase_id, session) -> None` (raises
  `ApplicationPhaseNotFoundError` if no row matched)
- `add_amendment(framework_id, data, session) -> FrameworkAmendment`
- `list_amendments(framework_id, session) -> list[FrameworkAmendment]` (ordered by `effective_date`,
  nulls last)
- `delete_amendment(framework_id, amendment_id, session) -> None` (raises `AmendmentNotFoundError`)
- `get_framework_detail()` extended to also assemble `application_phases`/`amendments` (research.md D4).

## State / validation rules

- Every new `RegulatoryFramework` field is optional at creation and update — no existing or new framework
  is ever blocked from saving by a missing legal-event date (spec.md FR-001, FR-002, SC-002).
- `regulation_number`, once set, must be unique across frameworks; leaving it unset never conflicts with
  another framework that also leaves it unset (spec.md Edge Cases).
- `status` accepts exactly the four spec.md FR-003 values; anything else is a 422 (existing `CHECK`
  constraint precedent, e.g. COMPLY-02's `compliance_status`).
- Deleting a framework cascades to its application phases and amendments (spec.md FR-009, SC-005) — no
  application-layer recursion (research.md D6).
- `framework_id`/`phase_id`/`amendment_id` must reference existing rows — the router does a friendly
  pre-check (`get_framework(...)` before insert; delete functions raise typed not-found exceptions) so a
  bad id gets a clean 404 rather than a raw FK-violation 500, mirroring `create_control`'s existing
  pattern.
