# COMPLY-01 Addendum — RegulatoryFramework Versioning Correction

**Status:** proposed addendum to COMPLY-01 (not a new spec — corrects a field
shape drafted in COMPLY-01 before build)
**Domain:** `adp.compliance`
**Depends on:** COMPLY-01 (RegulatoryFramework / Control registry)
**Touches:** migration, models, store

---

## 1. What to build

Replace the current scalar `version` field on `RegulatoryFramework`
(`NUMERIC`, e.g. `2.5`) with a small set of dated, evidenced fields plus two
child tables. Regulatory instruments don't version like software — they have
a stable legal identity, a set of legal-event dates, a consolidation date
that stands in for "current version," and — for some frameworks — staged
application dates and a growing stack of amending acts. A single number
can't carry any of that, and it isn't queryable against anything real (there
is no external authority that would ever confirm "DORA is at 2.5").

This corrects the field before COMPLY-02 through COMPLY-05 build on top of
it, since `compute_compliance_status()` and the read-side rollups will need
to reason about application-date phasing, not just framework identity.

## 2. Why

Reviewed against GDPR, EU AI Act, and DORA as reference cases:

| Framework | What "version" would have to mean |
|---|---|
| GDPR (2016/679) | No amendments since enactment — a scalar would just always read `1.0`, carrying no information |
| EU AI Act (2024/1689) | Single regulation, but **phased application dates** by obligation category (prohibited practices → GPAI → high-risk → remaining), consolidated text already updated post-enactment |
| DORA (2022/2554) | Base regulation plus a growing stack of Delegated/Implementing Regulations (RTS) that supplement specific articles — no single "version" covers the base act and the RTS stack at once |

None of these fit `NUMERIC`. What they share is: a stable identity (the
regulation number), a set of distinct legal-event dates, a consolidation
date EUR-Lex itself uses as the de facto "as-of" marker, and — for two of
three — a one-to-many relationship to either phased application dates or
amending instruments.

## 3. Migration delta

Alembic revision, additive to the `RegulatoryFramework` table created in
COMPLY-01. Column/constraint definitions live only in the migration, per
convention — the store-layer `Table()` object is SELECT/INSERT/UPDATE/DELETE
only.

```python
"""COMPLY-01a: correct RegulatoryFramework versioning shape

Revision ID: <next>
Revises: <COMPLY-01 create_regulatory_framework revision>
"""

def upgrade() -> None:
    # --- drop the incorrect scalar version field ---
    op.drop_column("regulatory_framework", "version")

    # --- replace with identity + dated legal-event fields ---
    op.add_column("regulatory_framework",
        sa.Column("regulation_number", sa.Text(), nullable=False))
    op.add_column("regulatory_framework",
        sa.Column("celex_number", sa.Text(), nullable=True))
    op.add_column("regulatory_framework",
        sa.Column("adoption_date", sa.Date(), nullable=True))
    op.add_column("regulatory_framework",
        sa.Column("oj_publication_date", sa.Date(), nullable=True))
    op.add_column("regulatory_framework",
        sa.Column("entry_into_force_date", sa.Date(), nullable=True))
    op.add_column("regulatory_framework",
        sa.Column("consolidated_as_of", sa.Date(), nullable=True))
    op.add_column("regulatory_framework",
        sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("regulatory_framework",
        sa.Column("status", sa.Text(), nullable=False,
                  server_default="in_force"))

    op.create_check_constraint(
        "ck_regulatory_framework_status",
        "regulatory_framework",
        "status IN ('in_force', 'amended', 'repealed', 'not_yet_applicable')",
    )
    op.create_unique_constraint(
        "uq_regulatory_framework_regulation_number",
        "regulatory_framework",
        ["regulation_number"],
    )

    # --- one-to-many: staged application dates ---
    # Single row for frameworks with one application date (GDPR, DORA);
    # multiple rows for phased frameworks (EU AI Act).
    op.create_table(
        "framework_application_phase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("framework_id", sa.Integer(),
                  sa.ForeignKey("regulatory_framework.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("phase_label", sa.Text(), nullable=False),
        sa.Column("applies_from_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_framework_application_phase_framework_id",
        "framework_application_phase",
        ["framework_id"],
    )

    # --- one-to-many: amending instruments ---
    # Empty for GDPR; populated for DORA's RTS stack and any future
    # AI Act amendments.
    op.create_table(
        "framework_amendment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("framework_id", sa.Integer(),
                  sa.ForeignKey("regulatory_framework.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("amending_celex", sa.Text(), nullable=True),
        sa.Column("amending_title", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_framework_amendment_framework_id",
        "framework_amendment",
        ["framework_id"],
    )


def downgrade() -> None:
    op.drop_table("framework_amendment")
    op.drop_table("framework_application_phase")
    op.drop_constraint("uq_regulatory_framework_regulation_number",
                        "regulatory_framework", type_="unique")
    op.drop_constraint("ck_regulatory_framework_status",
                        "regulatory_framework", type_="check")
    op.drop_column("regulatory_framework", "status")
    op.drop_column("regulatory_framework", "source_url")
    op.drop_column("regulatory_framework", "consolidated_as_of")
    op.drop_column("regulatory_framework", "entry_into_force_date")
    op.drop_column("regulatory_framework", "oj_publication_date")
    op.drop_column("regulatory_framework", "adoption_date")
    op.drop_column("regulatory_framework", "celex_number")
    op.drop_column("regulatory_framework", "regulation_number")
    op.add_column("regulatory_framework",
        sa.Column("version", sa.Numeric(), nullable=True))
```

## 4. Model delta (`adp/compliance/models.py`)

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl

FrameworkStatus = Literal["in_force", "amended", "repealed", "not_yet_applicable"]


class FrameworkApplicationPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    phase_label: str
    applies_from_date: date
    description: str | None = None


class FrameworkApplicationPhaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase_label: str
    applies_from_date: date
    description: str | None = None


class FrameworkAmendment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    amending_celex: str | None = None
    amending_title: str
    effective_date: date | None = None


class FrameworkAmendmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amending_celex: str | None = None
    amending_title: str
    effective_date: date | None = None


class RegulatoryFramework(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    regulation_number: str          # e.g. "2016/679" — stable identity
    celex_number: str | None = None # e.g. "32016R0679"
    official_title: str
    adoption_date: date | None = None
    oj_publication_date: date | None = None
    entry_into_force_date: date | None = None
    consolidated_as_of: date | None = None   # de facto "version" marker
    source_url: HttpUrl | None = None
    status: FrameworkStatus = "in_force"
    application_phases: list[FrameworkApplicationPhase] = []
    amendments: list[FrameworkAmendment] = []


class RegulatoryFrameworkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regulation_number: str
    celex_number: str | None = None
    official_title: str
    adoption_date: date | None = None
    oj_publication_date: date | None = None
    entry_into_force_date: date | None = None
    consolidated_as_of: date | None = None
    source_url: HttpUrl | None = None
    status: FrameworkStatus = "in_force"
```

## 5. Store delta (`adp/compliance/store.py`)

Follows the existing `Core`-style `Table()` shape — no FK/PK/CHECK objects
here, those live only in the migration.

```python
regulatory_framework = Table(
    "regulatory_framework",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("regulation_number", Text, nullable=False),
    Column("celex_number", Text),
    Column("official_title", Text, nullable=False),
    Column("adoption_date", Date),
    Column("oj_publication_date", Date),
    Column("entry_into_force_date", Date),
    Column("consolidated_as_of", Date),
    Column("source_url", Text),
    Column("status", Text, nullable=False),
)

framework_application_phase = Table(
    "framework_application_phase",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("framework_id", Integer, nullable=False),
    Column("phase_label", Text, nullable=False),
    Column("applies_from_date", Date, nullable=False),
    Column("description", Text),
    Column("created_at", DateTime(timezone=True)),
)

framework_amendment = Table(
    "framework_amendment",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("framework_id", Integer, nullable=False),
    Column("amending_celex", Text),
    Column("amending_title", Text, nullable=False),
    Column("effective_date", Date),
    Column("created_at", DateTime(timezone=True)),
)
```

New/changed store functions:

- `get_framework(session, framework_id) -> RegulatoryFramework | None` — now
  joins `framework_application_phase` and `framework_amendment`, assembling
  the two child lists onto the parent model rather than a scalar version
  lookup.
- `list_application_phases(session, framework_id) -> list[FrameworkApplicationPhase]`
- `add_application_phase(session, framework_id, phase: FrameworkApplicationPhaseCreate)`
- `add_amendment(session, framework_id, amendment: FrameworkAmendmentCreate)`
- `is_phase_applicable(phase: FrameworkApplicationPhase, as_of: date) -> bool`
  — pure function, `as_of >= phase.applies_from_date`, in the same style as
  `compute_evolution_stage()` / `compute_business_value_score()`. This is
  the hook `compute_compliance_status()` will need once COMPLY-03 lands, so
  a control mapped to a not-yet-applicable phase can be excluded from a
  compliance-gap rollup rather than silently counted as in scope.

## 6. Out of scope for this addendum

- Any change to `Control` or `ControlMapping` shapes — untouched.
- Backfilling `consolidated_as_of` / dates for existing seeded frameworks —
  follow-on data task, not a schema concern.
- Surfacing `framework_amendment` / `framework_application_phase` in the
  Governance & Standards screen — UI follow-on, tracked separately.
- Automated ingestion from EUR-Lex (e.g. polling the ELI API for new
  consolidations) — out of scope; records are populated by an architect,
  consistent with the platform's current manual-entry posture for reference
  data.

## 7. Open questions (preserved, not resolved here)

- Should `framework_application_phase` support phases that vary **by
  obligation category** within a single framework (e.g. AI Act: prohibited
  practices vs. GPAI vs. high-risk), or is `phase_label` free text sufficient
  for `ControlMapping` to reference informally? If `compute_compliance_status()`
  needs to programmatically exclude not-yet-applicable controls, `phase_label`
  may need to become a controlled vocabulary or a link target rather than
  free text.
- Should `consolidated_as_of` be treated as a hard uniqueness constraint per
  framework (only one "current" consolidated text at a time), or should ADP
  keep a history of prior consolidations for audit purposes? Current shape
  assumes the row is always overwritten in place — no history table.
- Does `status = 'not_yet_applicable'` at the framework level conflict with
  or duplicate what `framework_application_phase` already expresses at the
  phase level? As drafted, both exist; worth deciding whether framework-level
  `status` should instead be **derived** from the phase table rather than
  stored independently — same tension `compute_evolution_stage()` resolves
  elsewhere by deriving rather than storing.
- `source_url` currently points at one canonical EUR-Lex URL per framework.
  DORA's shape (base act + several Delegated/Implementing Regulations, each
  with its own URL) may argue for `source_url` living on
  `framework_amendment` instead of only on the parent — currently the parent
  URL would only ever point at the base act's OJ page, not the consolidated
  text reflecting the RTS stack.
- No `ThemeFrameworkMapping` decision dependency here, but worth flagging:
  if that mapping type is built, it will inherit whatever `status` /
  `consolidated_as_of` semantics are settled by this addendum.