# Data Model: Business Architecture Traceability (ADP-SPEC-034)

**Feature**: 034-business-arch-traceability
**Generated**: 2026-07-10
**Migration**: 008 (depends on 007 for `business_capabilities` and `value_streams` tables)

---

## New Tables

### `capability_design_links`

Many-to-many join between `business_capabilities` and `designs`.

| Column | Type | Constraints |
|--------|------|-------------|
| `capability_id` | `VARCHAR(36)` | FK → `business_capabilities.id` ON DELETE CASCADE, NOT NULL |
| `design_id` | `TEXT` | FK → `designs.id` ON DELETE CASCADE, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, default now() |

**Primary Key**: `(capability_id, design_id)` — composite, enforces uniqueness
**Indexes**: B-tree on `design_id` for reverse lookup (design → capabilities)

### `value_stream_design_links`

Many-to-many join between `value_streams` and `designs`.

| Column | Type | Constraints |
|--------|------|-------------|
| `value_stream_id` | `VARCHAR(36)` | FK → `value_streams.id` ON DELETE CASCADE, NOT NULL |
| `design_id` | `TEXT` | FK → `designs.id` ON DELETE CASCADE, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, default now() |

**Primary Key**: `(value_stream_id, design_id)` — composite, enforces uniqueness
**Indexes**: B-tree on `design_id` for reverse lookup (design → value streams)

---

## Entity Relationships

```
business_capabilities ──< capability_design_links >── designs
value_streams         ──< value_stream_design_links >── designs
```

Cardinality: a design can be linked to many capabilities and many value streams; a capability/value stream can be linked to many designs.

---

## Pydantic Models (Backend)

All models: `extra="forbid"`, `model_config = ConfigDict(extra="forbid")`

```python
class DesignRef(BaseModel):
    """Lightweight design reference for link list responses."""
    model_config = ConfigDict(extra="forbid")
    design_id: str
    title: str
    lifecycle_status: str

class CapabilityRef(BaseModel):
    """Lightweight capability reference for reverse-lookup responses."""
    model_config = ConfigDict(extra="forbid")
    capability_id: str
    name: str
    level: int

class ValueStreamRef(BaseModel):
    """Lightweight value stream reference for reverse-lookup responses."""
    model_config = ConfigDict(extra="forbid")
    value_stream_id: str
    name: str
    stakeholder: str | None

class DesignLinkCreate(BaseModel):
    """Request body for linking a design to a capability or value stream."""
    model_config = ConfigDict(extra="forbid")
    design_id: str

    @field_validator("design_id")
    @classmethod
    def design_id_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("design_id must not be blank")
        return v.strip()

class LinkedDesignsResponse(BaseModel):
    """Response for listing designs linked to a capability or value stream."""
    model_config = ConfigDict(extra="forbid")
    items: list[DesignRef]

class BusinessContextResponse(BaseModel):
    """Response for the design's business context — reverse lookup."""
    model_config = ConfigDict(extra="forbid")
    design_id: str
    capabilities: list[CapabilityRef]
    value_streams: list[ValueStreamRef]
```

---

## TypeScript Interfaces (Frontend)

```typescript
interface DesignRef {
  design_id: string;
  title: string;
  lifecycle_status: string;
}

interface CapabilityRef {
  capability_id: string;
  name: string;
  level: number;
}

interface ValueStreamRef {
  value_stream_id: string;
  name: string;
  stakeholder: string | null;
}

interface LinkedDesignsResponse {
  items: DesignRef[];
}

interface BusinessContextResponse {
  design_id: string;
  capabilities: CapabilityRef[];
  value_streams: ValueStreamRef[];
}

interface DesignLinkCreate {
  design_id: string;
}
```

---

## Store Functions (Backend additions to `src/adp/business/store.py`)

```python
# Capability-design links
async def list_capability_designs(capability_id: str, session: AsyncSession) -> list[DesignRef]
async def link_design_to_capability(capability_id: str, design_id: str, session: AsyncSession) -> None
    # raises DuplicateLinkError on (capability_id, design_id) conflict
async def unlink_design_from_capability(capability_id: str, design_id: str, session: AsyncSession) -> None
    # raises LinkNotFoundError if link does not exist

# Value stream-design links
async def list_value_stream_designs(value_stream_id: str, session: AsyncSession) -> list[DesignRef]
async def link_design_to_value_stream(value_stream_id: str, design_id: str, session: AsyncSession) -> None
    # raises DuplicateLinkError on (value_stream_id, design_id) conflict
async def unlink_design_from_value_stream(value_stream_id: str, design_id: str, session: AsyncSession) -> None
    # raises LinkNotFoundError if link does not exist

# Reverse lookup (design context)
async def get_design_business_context(design_id: str, session: AsyncSession) -> dict
    # returns {"capabilities": [...], "value_streams": [...]}
```

### Error Classes

```python
class DuplicateLinkError(Exception):
    """Raised when (capability_id, design_id) or (value_stream_id, design_id) already exists."""

class LinkNotFoundError(Exception):
    """Raised when a link to delete does not exist."""
```

---

## Validation Rules

1. `design_id` in `DesignLinkCreate` must not be blank
2. The design referenced by `design_id` MUST exist in the `designs` table (checked in store via JOIN; 404 if not found)
3. The capability or value stream MUST exist (checked via store's existing get functions; 404 if not found)
4. Duplicate link returns 409 Conflict
5. Cascading deletes are enforced at DB level (FK ON DELETE CASCADE) — no application-level cleanup needed
