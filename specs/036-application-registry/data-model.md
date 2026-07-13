# Data Model: Application Registry (ADP-SPEC-036)

## Database Schema Changes (Alembic migration 010)

`down_revision = "009"` (ADP-SPEC-035 business domain registry)

### New table: `applications`

```sql
CREATE TABLE applications (
    id                  VARCHAR(36)  PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    vendor              VARCHAR(255),
    primary_owner       VARCHAR(255),
    time_classification TEXT         CHECK (time_classification IN ('Tolerate', 'Invest', 'Migrate', 'Eliminate')),
    r_strategy          TEXT         CHECK (r_strategy IN ('Rehost', 'Replatform', 'Repurchase', 'Refactor', 'Retire', 'Retain', 'Relocate')),
    pace_layer          TEXT         CHECK (pace_layer IN ('Record', 'Differentiation', 'Innovation')),
    health_score        INTEGER      CHECK (health_score BETWEEN 1 AND 5),
    created_at          TIMESTAMPTZ  NOT NULL,
    updated_at          TIMESTAMPTZ  NOT NULL
);

CREATE INDEX ix_applications_name ON applications (name);
```

### New table: `technical_capabilities`

Self-referential three-level hierarchy; `ON DELETE RESTRICT` blocks parent deletion when children exist.

```sql
CREATE TABLE technical_capabilities (
    id          VARCHAR(36)  PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    parent_id   VARCHAR(36)  REFERENCES technical_capabilities(id) ON DELETE RESTRICT,
    level       INTEGER      NOT NULL CHECK (level IN (1, 2, 3)),
    created_at  TIMESTAMPTZ  NOT NULL
);

CREATE INDEX ix_technical_capabilities_parent_id ON technical_capabilities (parent_id);
```

### New table: `application_capability_links`

Join between applications and business_capabilities (ADP-SPEC-033). Both FKs CASCADE on delete.

```sql
CREATE TABLE application_capability_links (
    app_id        VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    capability_id VARCHAR(36) NOT NULL REFERENCES business_capabilities(id) ON DELETE CASCADE,
    fit_score     INTEGER     NOT NULL CHECK (fit_score BETWEEN 1 AND 5),
    PRIMARY KEY (app_id, capability_id)
);

CREATE INDEX ix_acl_capability_id ON application_capability_links (capability_id);
```

### New table: `application_tech_cap_links`

Join between applications and technical_capabilities with usage direction. Composite PK includes `usage_type` so a single app can both provide AND consume the same tech capability.

```sql
CREATE TABLE application_tech_cap_links (
    app_id      VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    tech_cap_id VARCHAR(36) NOT NULL REFERENCES technical_capabilities(id) ON DELETE CASCADE,
    usage_type  TEXT        NOT NULL CHECK (usage_type IN ('provides', 'consumes')),
    PRIMARY KEY (app_id, tech_cap_id, usage_type)
);

CREATE INDEX ix_atcl_tech_cap_id ON application_tech_cap_links (tech_cap_id);
```

### New table: `application_stage_links`

Join between applications and value_stream_stages (ADP-SPEC-033). Both FKs CASCADE.

```sql
CREATE TABLE application_stage_links (
    app_id   VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage_id VARCHAR(36) NOT NULL REFERENCES value_stream_stages(id) ON DELETE CASCADE,
    PRIMARY KEY (app_id, stage_id)
);

CREATE INDEX ix_asl_stage_id ON application_stage_links (stage_id);
```

### New table: `application_domain_integrations`

Relationship between an application and a business domain (ADP-SPEC-035) with integration context. `integration_type` is free text. Domain FK is CASCADE (FR-036).

```sql
CREATE TABLE application_domain_integrations (
    id               VARCHAR(36)  PRIMARY KEY,
    app_id           VARCHAR(36)  NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    domain_id        VARCHAR(36)  REFERENCES business_domains(id) ON DELETE CASCADE,
    integration_type VARCHAR(255) NOT NULL,
    direction        TEXT         NOT NULL CHECK (direction IN ('inbound', 'outbound', 'bidirectional')),
    created_at       TIMESTAMPTZ  NOT NULL
);

CREATE INDEX ix_adi_app_id    ON application_domain_integrations (app_id);
CREATE INDEX ix_adi_domain_id ON application_domain_integrations (domain_id);
```

### New table: `application_integrations`

Point-to-point integration between two applications. DB-level `CHECK (source_app_id <> target_app_id)` enforces FR-038. Both app FKs CASCADE so deleting either endpoint removes the integration.

```sql
CREATE TABLE application_integrations (
    id               VARCHAR(36) PRIMARY KEY,
    source_app_id    VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    target_app_id    VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    integration_type TEXT        NOT NULL CHECK (integration_type IN ('API', 'event', 'file', 'database', 'messaging', 'other')),
    description      TEXT,
    created_at       TIMESTAMPTZ NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL,
    CHECK (source_app_id <> target_app_id)
);

CREATE INDEX ix_ai_source ON application_integrations (source_app_id);
CREATE INDEX ix_ai_target ON application_integrations (target_app_id);
```

### New table: `application_design_links`

Join between applications and designs (ADP-SPEC-002). Both FKs CASCADE.

```sql
CREATE TABLE application_design_links (
    app_id    VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    design_id VARCHAR(36) NOT NULL REFERENCES designs(id) ON DELETE CASCADE,
    PRIMARY KEY (app_id, design_id)
);

CREATE INDEX ix_adl_design_id ON application_design_links (design_id);
```

---

## Pydantic v2 Models (new, in `src/adp/application/models.py`)

### Enums and Literals

```python
TimeClassification = Literal["Tolerate", "Invest", "Migrate", "Eliminate"]
RStrategy          = Literal["Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate"]
PaceLayer          = Literal["Record", "Differentiation", "Innovation"]
UsageType          = Literal["provides", "consumes"]
IntegrationDir     = Literal["inbound", "outbound", "bidirectional"]
AppIntegrationType = Literal["API", "event", "file", "database", "messaging", "other"]
```

### Application (read model)

```python
class Application(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    vendor: str | None
    primary_owner: str | None
    time_classification: TimeClassification | None
    r_strategy: RStrategy | None
    pace_layer: PaceLayer | None
    health_score: Annotated[int, Field(ge=1, le=5)] | None
    created_at: datetime
    updated_at: datetime
```

### ApplicationCreate

```python
class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    vendor: str | None = None
    primary_owner: str | None = None
    time_classification: TimeClassification | None = None
    r_strategy: RStrategy | None = None
    pace_layer: PaceLayer | None = None
    health_score: Annotated[int, Field(ge=1, le=5)] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v
```

### ApplicationUpdate

```python
class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    vendor: str | None = None
    primary_owner: str | None = None
    time_classification: TimeClassification | None = None
    r_strategy: RStrategy | None = None
    pace_layer: PaceLayer | None = None
    health_score: Annotated[int, Field(ge=1, le=5)] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v
```

### ApplicationListResponse

```python
class ApplicationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Application]
    total: int
```

### TechnicalCapability (read model)

```python
class TechnicalCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    parent_id: str | None
    level: int   # 1, 2, or 3
    created_at: datetime
```

### TechnicalCapabilityCreate

```python
class TechnicalCapabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v
```

### TechnicalCapabilityUpdate

```python
class TechnicalCapabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v
```

### TechCapListResponse

```python
class TechCapListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[TechnicalCapability]
    total: int
```

### ApplicationCapabilityLink (read model)

```python
class ApplicationCapabilityLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    capability_id: str
    capability_name: str
    fit_score: Annotated[int, Field(ge=1, le=5)]
```

### ApplicationCapabilityLinkCreate

```python
class ApplicationCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_id: str
    fit_score: Annotated[int, Field(ge=1, le=5)]
```

### ApplicationCapabilityLinkUpdate

```python
class ApplicationCapabilityLinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fit_score: Annotated[int, Field(ge=1, le=5)]
```

### ApplicationCapabilityLinksResponse

```python
class ApplicationCapabilityLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationCapabilityLink]
```

### ApplicationTechCapLink (read model)

```python
class ApplicationTechCapLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    tech_cap_id: str
    tech_cap_name: str
    usage_type: UsageType
```

### ApplicationTechCapLinkCreate

```python
class ApplicationTechCapLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tech_cap_id: str
    usage_type: UsageType
```

### ApplicationTechCapLinksResponse

```python
class ApplicationTechCapLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationTechCapLink]
```

### ApplicationStageLink (read model)

```python
class ApplicationStageLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    stage_id: str
    stage_name: str
```

### ApplicationStageLinkCreate

```python
class ApplicationStageLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_id: str
```

### ApplicationStageLinksResponse

```python
class ApplicationStageLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationStageLink]
```

### ApplicationDomainIntegration (read model)

```python
class ApplicationDomainIntegration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    app_id: str
    domain_id: str | None
    domain_name: str | None
    integration_type: str
    direction: IntegrationDir
    created_at: datetime
```

### ApplicationDomainIntegrationCreate

```python
class ApplicationDomainIntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain_id: str | None = None
    integration_type: str
    direction: IntegrationDir

    @field_validator("integration_type")
    @classmethod
    def type_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("integration_type must not be blank")
        return v
```

### ApplicationDomainIntegrationsResponse

```python
class ApplicationDomainIntegrationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationDomainIntegration]
```

### ApplicationIntegration (read model)

```python
class ApplicationIntegration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_app_id: str
    source_app_name: str
    target_app_id: str
    target_app_name: str
    integration_type: AppIntegrationType
    description: str | None
    created_at: datetime
    updated_at: datetime
```

### ApplicationIntegrationCreate

```python
class ApplicationIntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_app_id: str
    target_app_id: str
    integration_type: AppIntegrationType
    description: str | None = None

    @model_validator(mode="after")
    def source_ne_target(self) -> "ApplicationIntegrationCreate":
        if self.source_app_id == self.target_app_id:
            raise ValueError("source_app_id and target_app_id must differ")
        return self
```

### ApplicationIntegrationUpdate

```python
class ApplicationIntegrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None
```

### ApplicationIntegrationListResponse

```python
class ApplicationIntegrationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationIntegration]
    total: int
```

### ApplicationDesignLink (read model)

```python
class ApplicationDesignLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str
    design_id: str
```

### ApplicationDesignLinkCreate

```python
class ApplicationDesignLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_id: str
```

### ApplicationDesignLinksResponse

```python
class ApplicationDesignLinksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationDesignLink]
```

### Error classes

```python
class TechCapHasChildrenError(Exception):
    """Raised when deleting a technical capability that still has children."""

class DuplicateAppCapLinkError(Exception):
    """Raised when the (app_id, capability_id) link already exists."""

class DuplicateAppTechCapLinkError(Exception):
    """Raised when the (app_id, tech_cap_id, usage_type) link already exists."""

class DuplicateAppStageLinkError(Exception):
    """Raised when the (app_id, stage_id) link already exists."""

class DuplicateAppDesignLinkError(Exception):
    """Raised when the (app_id, design_id) link already exists."""

class TechCapDepthError(Exception):
    """Raised when creating a child of an L3 technical capability."""
```

---

## Store Functions (new `src/adp/application/store.py`)

### SA Table definitions

```python
_applications = sa.Table(
    "applications", _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("vendor", sa.String(255)),
    sa.Column("primary_owner", sa.String(255)),
    sa.Column("time_classification", sa.Text()),
    sa.Column("r_strategy", sa.Text()),
    sa.Column("pace_layer", sa.Text()),
    sa.Column("health_score", sa.Integer()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_tech_caps = sa.Table(
    "technical_capabilities", _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.String(255), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("parent_id", sa.String(36)),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_app_cap_links = sa.Table(
    "application_capability_links", _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
    sa.Column("fit_score", sa.Integer(), nullable=False),
)

_app_tech_cap_links = sa.Table(
    "application_tech_cap_links", _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("tech_cap_id", sa.String(36), nullable=False),
    sa.Column("usage_type", sa.Text(), nullable=False),
)

_app_stage_links = sa.Table(
    "application_stage_links", _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("stage_id", sa.String(36), nullable=False),
)

_app_domain_integrations = sa.Table(
    "application_domain_integrations", _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("domain_id", sa.String(36)),
    sa.Column("integration_type", sa.String(255), nullable=False),
    sa.Column("direction", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_app_integrations = sa.Table(
    "application_integrations", _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("source_app_id", sa.String(36), nullable=False),
    sa.Column("target_app_id", sa.String(36), nullable=False),
    sa.Column("integration_type", sa.Text(), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_app_design_links = sa.Table(
    "application_design_links", _metadata,
    sa.Column("app_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.String(36), nullable=False),
)
```

### Store function signatures

| Function | Returns | Notes |
|---|---|---|
| `list_applications(session)` | `ApplicationListResponse` | ORDER BY name |
| `get_application(app_id, session)` | `Application \| None` | |
| `create_application(body, session)` | `Application` | |
| `update_application(app_id, body, session)` | `Application \| None` | Partial update |
| `delete_application(app_id, session)` | `bool` | DB CASCADE handles links |
| `list_technical_capabilities(session)` | `TechCapListResponse` | ORDER BY level, name |
| `get_technical_capability(tc_id, session)` | `TechnicalCapability \| None` | |
| `create_technical_capability(body, session)` | `TechnicalCapability` | Raises TechCapDepthError if parent is L3 |
| `update_technical_capability(tc_id, body, session)` | `TechnicalCapability \| None` | |
| `delete_technical_capability(tc_id, session)` | `bool` | Raises TechCapHasChildrenError if has children |
| `list_app_capability_links(app_id, session)` | `ApplicationCapabilityLinksResponse` | JOIN business_capabilities for name |
| `create_app_capability_link(app_id, body, session)` | `ApplicationCapabilityLink` | Raises DuplicateAppCapLinkError |
| `update_app_capability_link(app_id, cap_id, body, session)` | `ApplicationCapabilityLink \| None` | Updates fit_score |
| `delete_app_capability_link(app_id, cap_id, session)` | `bool` | |
| `list_app_tech_cap_links(app_id, session)` | `ApplicationTechCapLinksResponse` | JOIN technical_capabilities for name |
| `create_app_tech_cap_link(app_id, body, session)` | `ApplicationTechCapLink` | Raises DuplicateAppTechCapLinkError |
| `delete_app_tech_cap_link(app_id, tc_id, usage_type, session)` | `bool` | |
| `list_app_stage_links(app_id, session)` | `ApplicationStageLinksResponse` | JOIN value_stream_stages for name |
| `create_app_stage_link(app_id, body, session)` | `ApplicationStageLink` | Raises DuplicateAppStageLinkError |
| `delete_app_stage_link(app_id, stage_id, session)` | `bool` | |
| `list_app_domain_integrations(app_id, session)` | `ApplicationDomainIntegrationsResponse` | LEFT JOIN business_domains for name |
| `create_app_domain_integration(app_id, body, session)` | `ApplicationDomainIntegration` | |
| `delete_app_domain_integration(app_id, link_id, session)` | `bool` | |
| `list_integrations(app_id, session)` | `ApplicationIntegrationListResponse` | WHERE source OR target; JOIN apps for names |
| `get_integration(int_id, session)` | `ApplicationIntegration \| None` | |
| `create_integration(body, session)` | `ApplicationIntegration` | Validates apps exist |
| `update_integration(int_id, body, session)` | `ApplicationIntegration \| None` | Only description |
| `delete_integration(int_id, session)` | `bool` | |
| `list_app_design_links(app_id, session)` | `ApplicationDesignLinksResponse` | |
| `create_app_design_link(app_id, body, session)` | `ApplicationDesignLink` | Validates design exists; Raises DuplicateAppDesignLinkError |
| `delete_app_design_link(app_id, design_id, session)` | `bool` | |

---

## TypeScript Interfaces (new, in `web/src/api/application.ts`)

```typescript
export type TimeClassification = "Tolerate" | "Invest" | "Migrate" | "Eliminate";
export type RStrategy = "Rehost" | "Replatform" | "Repurchase" | "Refactor" | "Retire" | "Retain" | "Relocate";
export type PaceLayer = "Record" | "Differentiation" | "Innovation";
export type UsageType = "provides" | "consumes";
export type IntegrationDir = "inbound" | "outbound" | "bidirectional";
export type AppIntegrationType = "API" | "event" | "file" | "database" | "messaging" | "other";

export interface Application {
  id: string;
  name: string;
  description: string | null;
  vendor: string | null;
  primary_owner: string | null;
  time_classification: TimeClassification | null;
  r_strategy: RStrategy | null;
  pace_layer: PaceLayer | null;
  health_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationCreate {
  name: string;
  description?: string | null;
  vendor?: string | null;
  primary_owner?: string | null;
  time_classification?: TimeClassification | null;
  r_strategy?: RStrategy | null;
  pace_layer?: PaceLayer | null;
  health_score?: number | null;
}

export interface ApplicationUpdate extends Partial<ApplicationCreate> {}

export interface ApplicationListResponse {
  items: Application[];
  total: number;
}

export interface TechnicalCapability {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  level: number;
  created_at: string;
}

export interface TechCapListResponse {
  items: TechnicalCapability[];
  total: number;
}

export interface ApplicationCapabilityLink {
  app_id: string;
  capability_id: string;
  capability_name: string;
  fit_score: number;
}

export interface ApplicationTechCapLink {
  app_id: string;
  tech_cap_id: string;
  tech_cap_name: string;
  usage_type: UsageType;
}

export interface ApplicationStageLink {
  app_id: string;
  stage_id: string;
  stage_name: string;
}

export interface ApplicationDomainIntegration {
  id: string;
  app_id: string;
  domain_id: string | null;
  domain_name: string | null;
  integration_type: string;
  direction: IntegrationDir;
  created_at: string;
}

export interface ApplicationIntegration {
  id: string;
  source_app_id: string;
  source_app_name: string;
  target_app_id: string;
  target_app_name: string;
  integration_type: AppIntegrationType;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationIntegrationCreate {
  source_app_id: string;
  target_app_id: string;
  integration_type: AppIntegrationType;
  description?: string | null;
}

export interface ApplicationDesignLink {
  app_id: string;
  design_id: string;
}
```

---

## Cardinality Summary

| Relationship | Type | FK constraint |
|---|---|---|
| Application → ApplicationCapabilityLink | one-to-many | CASCADE on app delete |
| BusinessCapability → ApplicationCapabilityLink | one-to-many | CASCADE on cap delete |
| Application → ApplicationTechCapLink | one-to-many | CASCADE on app delete |
| TechnicalCapability → ApplicationTechCapLink | one-to-many | CASCADE on tech cap delete |
| Application → ApplicationStageLink | one-to-many | CASCADE on app delete |
| ValueStreamStage → ApplicationStageLink | one-to-many | CASCADE on stage delete |
| Application → ApplicationDomainIntegration | one-to-many | CASCADE on app delete |
| BusinessDomain → ApplicationDomainIntegration | one-to-many | CASCADE on domain delete |
| Application (source) → ApplicationIntegration | one-to-many | CASCADE on source delete |
| Application (target) → ApplicationIntegration | one-to-many | CASCADE on target delete |
| Application → ApplicationDesignLink | one-to-many | CASCADE on app delete |
| Design → ApplicationDesignLink | one-to-many | CASCADE on design delete |
| TechnicalCapability (parent) → TechnicalCapability (child) | one-to-many | RESTRICT on parent delete |
