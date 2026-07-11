# Data Model: Business Architecture — Capability Model and Value Streams

**Feature**: 033-business-architecture
**Date**: 2026-07-10

## Entity Relationship Overview

```
BusinessCapability (self-referential, max 3 levels)
  └── parent_id → BusinessCapability.id (nullable for Level 1)

ValueStream
  └── has many → ValueStreamStage (ordered by position, cascade delete)
```

No join tables in this feature. Traceability joins (`CapabilityDesignLink`, `ValueStreamDesignLink`) are in ADP-SPEC-034.

---

## Entity 1: BusinessCapability

**Table**: `business_capabilities`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | VARCHAR(36) | PK | UUID, server-generated |
| `name` | VARCHAR(255) | NOT NULL | Required; non-empty validated at API |
| `description` | TEXT | nullable | Optional free text |
| `level` | INTEGER | NOT NULL, CHECK (level IN (1,2,3)) | 1=strategic, 2=operational, 3=granular |
| `parent_id` | VARCHAR(36) | FK → business_capabilities.id, nullable | NULL for Level 1; must match expected level (parent.level == level-1) |
| `position` | INTEGER | NOT NULL DEFAULT 0 | Ordering within parent; 0-based |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

**Indexes**:
- Primary key on `id`
- B-tree on `parent_id` (for child lookups)
- B-tree on `(parent_id, position)` (for ordered child fetches)

**Validation rules**:
- `name` must be non-empty after trimming
- `level` must be 1, 2, or 3
- If `level == 1`, `parent_id` must be NULL
- If `level == 2`, `parent_id` must reference a capability with `level == 1`
- If `level == 3`, `parent_id` must reference a capability with `level == 2`
- Delete blocked if any row references this `id` as `parent_id`

**State transitions**: None (capabilities are not stateful; they exist or are deleted)

---

## Entity 2: ValueStream

**Table**: `value_streams`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | VARCHAR(36) | PK | UUID, server-generated |
| `name` | VARCHAR(255) | NOT NULL | Required; non-empty validated at API |
| `description` | TEXT | nullable | |
| `stakeholder` | VARCHAR(255) | nullable | Target stakeholder/customer segment |
| `position` | INTEGER | NOT NULL DEFAULT 0 | Ordering in list view |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT now() | |

**Indexes**:
- Primary key on `id`
- B-tree on `position` (for ordered list)

**Validation rules**:
- `name` must be non-empty after trimming

---

## Entity 3: ValueStreamStage

**Table**: `value_stream_stages`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | VARCHAR(36) | PK | UUID, server-generated |
| `value_stream_id` | VARCHAR(36) | FK → value_streams.id ON DELETE CASCADE, NOT NULL | |
| `name` | VARCHAR(255) | NOT NULL | Required; non-empty validated at API |
| `description` | TEXT | nullable | |
| `position` | INTEGER | NOT NULL DEFAULT 0 | Ordering within the value stream |

**Indexes**:
- Primary key on `id`
- B-tree on `(value_stream_id, position)` (for ordered stage fetch)

**Validation rules**:
- `name` must be non-empty after trimming
- `value_stream_id` must reference an existing value stream (FK enforced)

---

## Python Pydantic Models (adp/business/models.py)

```python
# Read models (returned by API)
class BusinessCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    level: Literal[1, 2, 3]
    parent_id: str | None
    position: int
    created_at: datetime
    updated_at: datetime

class BusinessCapabilityNode(BusinessCapability):
    """Capability with nested children for tree responses."""
    children: list["BusinessCapabilityNode"] = []

class ValueStreamStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    value_stream_id: str
    name: str
    description: str | None
    position: int

class ValueStream(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    stakeholder: str | None
    position: int
    created_at: datetime
    updated_at: datetime

class ValueStreamDetail(ValueStream):
    """Value stream with its ordered stages."""
    stages: list[ValueStreamStage] = []

# Write models (accepted by API)
class BusinessCapabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    level: Literal[1, 2, 3]
    parent_id: str | None = None
    position: int = 0

class BusinessCapabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    position: int | None = None

class ValueStreamCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    stakeholder: str | None = None

class ValueStreamUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    stakeholder: str | None = None

class ValueStreamStageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    position: int = 0

class ValueStreamStageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    position: int | None = None

class ValueStreamStagesReorder(BaseModel):
    """Bulk replace stages list (preserves IDs, updates positions)."""
    model_config = ConfigDict(extra="forbid")
    stage_ids: list[str]  # ordered list; positions assigned 0..n-1
```

---

## Alembic Migration

**File**: `alembic/versions/007_business_architecture.py`

Creates:
1. `business_capabilities` table with self-referential FK and level CHECK constraint
2. `value_streams` table
3. `value_stream_stages` table with CASCADE FK to `value_streams`
4. All indexes listed above

**Rollback**: Drop tables in reverse order (stages → value_streams → business_capabilities) to avoid FK constraint errors.
