# Data Model: Business Domain Registry and Stage-Capability Mapping (ADP-SPEC-035)

## Database Schema Changes (Alembic migration 009)

### New table: `business_domains`

```sql
CREATE TABLE business_domains (
    id              VARCHAR(36)  PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    scope_statement TEXT,
    classification  TEXT         NOT NULL CHECK (classification IN ('strategic', 'differentiating', 'commodity')),
    org_unit        VARCHAR(255),
    risk_flags      TEXT[]       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL,
    updated_at      TIMESTAMPTZ  NOT NULL
);

CREATE INDEX ix_business_domains_name ON business_domains (name);
```

### Alter table: `business_capabilities`

```sql
ALTER TABLE business_capabilities
    ADD COLUMN domain_id VARCHAR(36)
    REFERENCES business_domains(id) ON DELETE SET NULL;

CREATE INDEX ix_business_capabilities_domain_id ON business_capabilities (domain_id);
```

`ON DELETE SET NULL` implements FR-008: deleting a domain automatically nulls `domain_id` on all its L1 capabilities without application-level loops.

### New table: `value_stream_stage_capabilities`

```sql
CREATE TABLE value_stream_stage_capabilities (
    stage_id      VARCHAR(36) NOT NULL REFERENCES value_stream_stages(id) ON DELETE CASCADE,
    capability_id VARCHAR(36) NOT NULL REFERENCES business_capabilities(id) ON DELETE CASCADE,
    PRIMARY KEY (stage_id, capability_id)
);

CREATE INDEX ix_vssc_capability_id ON value_stream_stage_capabilities (capability_id);
```

Composite PK enforces uniqueness (→ 409 at API layer on duplicate). Reverse index on `capability_id` enables forward-looking "which stages use capability X?" queries.

---

## Pydantic v2 Models (new, in `src/adp/business/models.py`)

### DomainClassification

```python
DomainClassification = Literal["strategic", "differentiating", "commodity"]
```

### BusinessDomain (read model)

```python
class BusinessDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    scope_statement: str | None
    classification: DomainClassification
    org_unit: str | None
    risk_flags: list[str]
    created_at: datetime
    updated_at: datetime
```

### DomainSummary (list response item — includes capability count)

```python
class DomainSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    classification: DomainClassification
    org_unit: str | None
    risk_flags: list[str]
    capability_count: int
    created_at: datetime
    updated_at: datetime
```

### DomainDetail (detail response — includes L1 capability list)

```python
class DomainDetail(BusinessDomain):
    capabilities: list[CapabilityRef]   # reuses existing CapabilityRef from 034
```

### BusinessDomainCreate

```python
class BusinessDomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    scope_statement: str | None = None
    classification: DomainClassification
    org_unit: str | None = None
    risk_flags: list[str] = []

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v

    @field_validator("risk_flags")
    @classmethod
    def flags_not_blank(cls, v: list[str]) -> list[str]:
        for flag in v:
            if not flag.strip():
                raise ValueError("risk_flags entries must not be blank")
        # deduplicate preserving order
        return list(dict.fromkeys(v))
```

### BusinessDomainUpdate

```python
class BusinessDomainUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    scope_statement: str | None = None
    classification: DomainClassification | None = None
    org_unit: str | None = None
    risk_flags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v

    @field_validator("risk_flags")
    @classmethod
    def flags_not_blank(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for flag in v:
                if not flag.strip():
                    raise ValueError("risk_flags entries must not be blank")
            return list(dict.fromkeys(v))
        return v
```

### DomainListResponse

```python
class DomainListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[DomainSummary]
    total: int
```

### CapabilityDomainAssign (PATCH body)

```python
class CapabilityDomainAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_id: str | None   # null = clear assignment
```

### StageCap models

```python
class StageCapabilityRef(BaseModel):
    """A capability linked to a value stream stage."""
    model_config = ConfigDict(extra="forbid")
    capability_id: str
    name: str
    level: int
    domain_id: str | None
    domain_name: str | None

class StageCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_id: str

    @field_validator("capability_id")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("capability_id must not be blank")
        return v.strip()

class StageCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[StageCapabilityRef]

class DuplicateStageCapError(Exception):
    """Raised when the (stage_id, capability_id) link already exists."""

class StageCapNotFoundError(Exception):
    """Raised when a stage-capability link to delete does not exist."""
```

---

## Store Functions (new, appended to `src/adp/business/store.py`)

New SA Table definitions to add:

```python
_domains = sa.Table(
    "business_domains", _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("scope_statement", sa.Text()),
    sa.Column("classification", sa.Text(), nullable=False),
    sa.Column("org_unit", sa.String(255)),
    sa.Column("risk_flags", sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_stage_caps = sa.Table(
    "value_stream_stage_capabilities", _metadata,
    sa.Column("stage_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
)
```

Extend `_capabilities` Table definition to include `domain_id` column.

New store functions (7 domain + 2 assignment + 3 stage-cap = 12 total):

| Function | Returns | Notes |
|---|---|---|
| `list_domains(session)` | `list[DomainSummary]` | LEFT JOIN capability count; ordered by name |
| `get_domain(domain_id, session)` | `DomainDetail \| None` | Includes L1 capability list |
| `create_domain(body, session)` | `BusinessDomain` | |
| `update_domain(domain_id, body, session)` | `BusinessDomain \| None` | Partial update |
| `delete_domain(domain_id, session)` | `bool` | DB CASCADE handles capability nulling |
| `assign_capability_domain(cap_id, domain_id, session)` | `BusinessCapability \| None` | SET domain_id; None if cap not found; 422 if level ≠ 1 |
| `clear_capability_domain(cap_id, session)` | `BusinessCapability \| None` | SET domain_id = null |
| `list_stage_capabilities(stage_id, session)` | `list[StageCapabilityRef]` | JOIN capabilities + domains for name |
| `link_stage_capability(stage_id, cap_id, session)` | None | Raises DuplicateStageCapError |
| `unlink_stage_capability(stage_id, cap_id, session)` | None | Raises StageCapNotFoundError |

---

## Updated BusinessCapability Model

`BusinessCapability` in models.py gains two optional fields:

```python
class BusinessCapability(BaseModel):
    ...
    domain_id: str | None = None
    domain_name: str | None = None   # denormalized for tree display; None if no domain
```

The `_row_to_capability()` helper in store.py will populate `domain_name` from a LEFT JOIN with `business_domains` when querying capabilities.

---

## TypeScript Interfaces (new, in `web/src/api/business.ts`)

```typescript
export type DomainClassification = "strategic" | "differentiating" | "commodity";

export interface BusinessDomain {
  id: string;
  name: string;
  scope_statement: string | null;
  classification: DomainClassification;
  org_unit: string | null;
  risk_flags: string[];
  created_at: string;
  updated_at: string;
}

export interface DomainSummary extends Omit<BusinessDomain, "scope_statement"> {
  capability_count: number;
}

export interface DomainDetail extends BusinessDomain {
  capabilities: CapabilityRef[];   // existing interface from 034
}

export interface DomainCreate {
  name: string;
  scope_statement?: string | null;
  classification: DomainClassification;
  org_unit?: string | null;
  risk_flags?: string[];
}

export interface DomainUpdate {
  name?: string;
  scope_statement?: string | null;
  classification?: DomainClassification;
  org_unit?: string | null;
  risk_flags?: string[];
}

export interface StageCapabilityRef {
  capability_id: string;
  name: string;
  level: number;
  domain_id: string | null;
  domain_name: string | null;
}

export interface StageCapabilitiesResponse {
  items: StageCapabilityRef[];
}
```

---

## Cardinality Summary

| Relationship | Type | Constraint |
|---|---|---|
| Domain → L1 Capability | one-to-many | L1 cap has `domain_id` FK; ON DELETE SET NULL |
| Value stream stage → Capability | many-to-many | `value_stream_stage_capabilities`; composite PK; both CASCADE |
