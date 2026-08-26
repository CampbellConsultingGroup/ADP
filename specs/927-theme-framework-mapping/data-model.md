# Data Model: Theme–Framework Mapping

**Feature**: 927-theme-framework-mapping
**Date**: 2026-08-26

## New table — migration `037` (`down_revision = "036"`)

```python
op.create_table(
    "theme_framework_links",
    sa.Column(
        "theme_id", sa.String(36),
        sa.ForeignKey("strategic_themes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "framework_id", sa.String(36),
        sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

Composite PK `(theme_id, framework_id)` — a pair can only be linked once (re-linking is a duplicate,
research.md D3). `ON DELETE CASCADE` on both legs, following the platform's migration-owns-constraints
convention: deleting a Strategic Theme or Regulatory Framework silently removes any dependent link rows,
never blocking the delete and never orphaning a row. No other column — this link carries no status,
evidence, or payload of its own (spec.md Key Entities).

No changes to `strategic_themes` or `regulatory_frameworks` themselves.

## Pydantic model changes (`adp.strategy.models`)

```python
class StrategicTheme(BaseModel):
    ...
    framework_ids: list[str] = []   # NEW — mirrors StrategicObjective.control_ids exactly
```

`extra="forbid"` already set on `StrategicTheme` — unchanged.

```python
class ThemeFrameworkLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    framework_id: str
```

New, mirroring `ObjectiveControlLinkCreate`'s exact shape (`{"control_id": "..."}`) one level up.

`RegulatoryFramework` (`adp.compliance.models`) is **not** modified (research.md D2).

## Store layer (`adp.strategy.store`)

New read-only mirror table (existence checks only, never written to from this module):

```python
_regulatory_frameworks = sa.Table(
    "regulatory_frameworks", _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.Text(), nullable=False),
)
```

New `_theme_framework_links` table object (DML only — constraints live in the migration, existing
convention):

```python
_theme_framework_links = sa.Table(
    "theme_framework_links", _metadata,
    sa.Column("theme_id", sa.String(36), nullable=False),
    sa.Column("framework_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

New functions (alongside the existing `theme_exists`/`get_theme`/`create_theme`/`update_theme`):

- `framework_exists(framework_id: str, session) -> bool` — existence check against the new mirror table.
- `link_theme_framework(theme_id: str, framework_id: str, session) -> None` — plain `INSERT`; raises
  `DuplicateLinkError` on a unique-violation (existing exception, existing translation idiom — research.md D3).
- `unlink_theme_framework(theme_id: str, framework_id: str, session) -> None` — `DELETE ... WHERE
  theme_id=? AND framework_id=?`; raises `LinkNotFoundError` if zero rows affected (existing exception).
- `list_themes_for_framework(framework_id: str, session) -> StrategicThemeListResponse` — reverse lookup,
  called from `adp.compliance.router`; joins `_theme_framework_links` → `_themes`, mirrors
  `list_objectives_for_control`'s exact shape.

Existing functions that must be extended to populate the new field (each already constructs a
`StrategicTheme` — mirrors the multi-touch-point update `StrategicObjective.control_ids` required in 925):

- `_row_to_theme(row, session)` — becomes `async`, additionally reads this theme's linked `framework_id`s.
- `create_theme(...)` — a brand-new theme has no links yet; `framework_ids=[]`.
- `update_theme(...)` — must include the current `framework_ids` in its returned object, same reasoning.

## API surface (`adp.strategy.router`, `adp.compliance.router`)

See `contracts/theme-framework-links-api.md` for the full request/response contract.

- `POST /api/v1/strategy/themes/{theme_id}/frameworks` — `adp.strategy.router`
- `DELETE /api/v1/strategy/themes/{theme_id}/frameworks/{framework_id}` — `adp.strategy.router`
- `GET /api/v1/compliance/frameworks/{framework_id}/themes` — `adp.compliance.router` (reverse lookup)

## Validation rules

- `framework_id` in the create body MUST reference an existing `RegulatoryFramework` → 404 otherwise
  (FR-003).
- `theme_id` in the path MUST reference an existing `StrategicTheme` → 404 otherwise (FR-003).
- A `(theme_id, framework_id)` pair that already exists → 409 on a second create attempt (FR-002).
- Removing a `(theme_id, framework_id)` pair that does not exist → 404 (FR-008).

## State transitions

None — a link either exists or does not; there is no intermediate or derived state (unlike
`ControlMapping`'s `compliance_status`).
