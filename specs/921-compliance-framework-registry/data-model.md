# Data Model: Compliance Framework & Control Registry (COMPLY-01)

**Feature**: 921-compliance-framework-registry
**Date**: 2026-08-17

## Entity Relationship Overview

```
RegulatoryFramework
  └── has many → Control (ON DELETE CASCADE)

Control (self-referential, unbounded depth)
  └── parent_id → Control.id, nullable, ON DELETE CASCADE (must be within the same framework_id)
```

No join tables in this feature. Cross-domain links (`ControlMapping` → Capability/Application/Design/
Pattern) are COMPLY-02, out of scope here — this registry only establishes the stable IDs those future
links will target.

---

## Entity 1: RegulatoryFramework

**Table**: `regulatory_frameworks`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | VARCHAR(36) | PK | UUID, server-generated |
| `name` | VARCHAR(255) | NOT NULL | e.g. "NIST 800-53 Rev 5"; not required to be unique — `version` distinguishes revisions of an identically-named framework |
| `jurisdiction` | VARCHAR(255) | NOT NULL | e.g. "EU", "US-Federal", "Global" |
| `authority` | VARCHAR(255) | NOT NULL | Issuing body, e.g. "European Commission", "NIST" |
| `version` | VARCHAR(100) | NOT NULL | Tracked independently of `name` |
| `effective_date` | DATE | nullable | NULL = perpetually current, not an error |
| `source_url` | TEXT | nullable | Link to authoritative source |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

**Indexes**:
- Primary key on `id`

**Validation rules**:
- `name`, `jurisdiction`, `authority`, `version` must be non-empty after trimming
- No uniqueness constraint on `name` (Edge Case: two frameworks may share a name at different versions)

**State transitions**: None (Assumption: no lifecycle status field in this pass — frameworks exist or are
deleted; a future need for status tracking, e.g. "superseded," is a follow-on, not modeled now)

**Delete behavior**: Cascades to every `Control` referencing this framework, at every hierarchy depth
(D2). The API layer discloses the scope to the caller before commit (D3, frontend-computed from the
already-fetched tree — no server-side change of behavior here beyond the cascade itself).

---

## Entity 2: Control

**Table**: `controls`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | VARCHAR(36) | PK | UUID, server-generated |
| `framework_id` | VARCHAR(36) | FK → regulatory_frameworks.id ON DELETE CASCADE, NOT NULL | |
| `parent_id` | VARCHAR(36) | FK → controls.id ON DELETE CASCADE, nullable | NULL = top-level within its framework; must reference a control in the *same* `framework_id` (app-layer enforced, D5) |
| `code` | VARCHAR(100) | NOT NULL | e.g. "AC-2", "Art. 17"; unique within `framework_id`, not globally |
| `title` | VARCHAR(255) | NOT NULL | |
| `description` | TEXT | nullable at DB level; non-blank required by the `Create` API model (FR-006) | |
| `position` | INTEGER | NOT NULL DEFAULT 0 | Ordering among siblings (same `parent_id`, or same `framework_id` if top-level) |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

**Constraints**:
- `UNIQUE (framework_id, code)` — composite, DB-level (D6)

**Indexes**:
- Primary key on `id`
- B-tree on `framework_id` (child/top-level lookups; also backs the FK)
- B-tree on `(framework_id, parent_id, position)` (ordered sibling fetch within a framework)

**Validation rules**:
- `code`, `title` must be non-empty after trimming
- `description` must be non-empty after trimming when provided on create (FR-006)
- `parent_id`, if set, must reference an existing control whose `framework_id` matches this control's own
  `framework_id` (FR-008; app-layer, D5)
- `parent_id` must not create a cycle — the proposed parent must not be this control itself, nor any of its
  own descendants (FR-008; app-layer, D5)
- `(framework_id, code)` must be unique (FR-009; DB-level, D6)
- No fixed depth cap — nesting is unbounded (Assumption; D8, no `level` column)

**State transitions**: None (controls exist or are deleted; no status field in this pass — that belongs to
`ControlMapping.compliance_status` in COMPLY-02, a different entity entirely)

**Delete behavior**: Cascades to every descendant `Control` beneath it, at every depth (D2).

---

## Python Pydantic Models (`adp/compliance/models.py`)

```python
"""Pydantic v2 models for the Compliance domain (COMPLY-01 / ADP-3up.5-ish).

ART-XIII: extra="forbid" on all models; all boundary payloads are typed.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# ── RegulatoryFramework ────────────────────────────────────────────────────

class RegulatoryFramework(BaseModel):
    """Read model returned by the API."""
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    jurisdiction: str
    authority: str
    version: str
    effective_date: date | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime


class RegulatoryFrameworkDetail(RegulatoryFramework):
    """Framework with its full control hierarchy, nested by parent_id."""
    controls: list["ControlNode"] = []


class RegulatoryFrameworkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    jurisdiction: str
    authority: str
    version: str
    effective_date: date | None = None
    source_url: str | None = None

    @field_validator("name", "jurisdiction", "authority", "version")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class RegulatoryFrameworkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    jurisdiction: str | None = None
    authority: str | None = None
    version: str | None = None
    effective_date: date | None = None
    source_url: str | None = None


class RegulatoryFrameworkListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RegulatoryFramework]
    total: int


# ── Control ───────────────────────────────────────────────────────────────

class Control(BaseModel):
    """Read model returned by the API."""
    model_config = ConfigDict(extra="forbid")

    id: str
    framework_id: str
    parent_id: str | None
    code: str
    title: str
    description: str | None
    position: int
    created_at: datetime
    updated_at: datetime


class ControlNode(Control):
    """Control with nested children for tree responses."""
    children: list["ControlNode"] = []


class ControlCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None
    code: str
    title: str
    description: str
    position: int = 0

    @field_validator("code", "title", "description")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class ControlUpdate(BaseModel):
    """All fields optional. Changing `parent_id` or `code` re-runs the same
    cycle/cross-framework/uniqueness validation as create (D5, D6)."""
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None
    code: str | None = None
    title: str | None = None
    description: str | None = None
    position: int | None = None

    @field_validator("code", "title")
    @classmethod
    def must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("must not be blank")
        return v
```

**Typed exceptions** (`adp/compliance/store.py`, mirroring `DuplicateLinkError`/`ChildCapabilitiesExist`'s
existing shape in `adp.business.store`):

- `DuplicateControlCodeError` — `(framework_id, code)` already exists (translated to HTTP 409)
- `CyclicParentError` — proposed `parent_id` is the control itself or one of its own descendants (HTTP 422)
- `CrossFrameworkParentError` — proposed `parent_id` belongs to a different `framework_id` (HTTP 422)
- `ParentNotFoundError` — proposed `parent_id`/`framework_id` does not reference an existing row (HTTP 404)

---

## Alembic Migration

**File**: `src/adp/store/migrations/versions/032_compliance_framework_registry.py`
**Revision**: `032`, **Revises**: `031` (D7 — confirmed against the actual on-disk chain, not `CLAUDE.md`'s
narrative history)

Creates:
1. `regulatory_frameworks` table
2. `controls` table — FK to `regulatory_frameworks.id` (`ON DELETE CASCADE`), self-referencing FK to
   `controls.id` (`ON DELETE CASCADE`, D2), composite `UNIQUE(framework_id, code)` (D6)
3. Indexes listed above

**Rollback**: Drop tables in reverse order (`controls` → `regulatory_frameworks`) to avoid FK constraint
errors.
