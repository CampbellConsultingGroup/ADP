# Data Model: Application Portfolio Management (ADP-SPEC-038)

All money is `NUMERIC(14,2)` at rest and `Decimal` in Pydantic — **never float**. All new scores are `SMALLINT NULL` with a `CHECK` range; `NULL` = "not assessed" (distinct from the lowest active value). Every write path emits an `AuditEntry` (ART-IX). Migrations chain from head `011_searchable_items`.

## Migration 012 — US1: business-value scores (`applications`)

```sql
ALTER TABLE applications
  ADD COLUMN business_value      SMALLINT NULL,
  ADD COLUMN business_criticality SMALLINT NULL;
ALTER TABLE applications
  ADD CONSTRAINT ck_app_business_value       CHECK (business_value IS NULL OR business_value BETWEEN 1 AND 5),
  ADD CONSTRAINT ck_app_business_criticality CHECK (business_criticality IS NULL OR business_criticality BETWEEN 1 AND 5);
```
Down: drop the two columns + constraints. (MVP — the TIME quadrant's value axis is `business_value`.)

## Migration 013 — US2: identity & ownership (`applications`)

```sql
ALTER TABLE applications
  ADD COLUMN owning_business_unit VARCHAR(255) NULL,
  ADD COLUMN business_owner       VARCHAR(255) NULL,
  ADD COLUMN technical_owner      VARCHAR(255) NULL,
  ADD COLUMN lifecycle_status     TEXT NOT NULL DEFAULT 'active';
ALTER TABLE applications
  ADD CONSTRAINT ck_app_lifecycle_status
      CHECK (lifecycle_status IN ('planned','active','sunset','retired'));
CREATE INDEX ix_applications_lifecycle_status ON applications (lifecycle_status);
CREATE INDEX ix_applications_business_unit    ON applications (owning_business_unit);
```
`primary_owner` is retained (kept for back-compat; `business_owner`/`technical_owner` are the APM split). `lifecycle_status` mirrors ADP-SPEC-030's design lifecycle vocabulary.

## Migration 014 — US3: risk & compliance (`application_risk`)

```sql
CREATE TABLE application_risk (
  app_id                VARCHAR(36) PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
  security_posture      TEXT NULL,          -- e.g. 'strong','adequate','weak','unknown'
  vulnerability_status  TEXT NULL,          -- e.g. 'none_known','open_low','open_high','critical'
  data_classification   TEXT NULL,          -- e.g. 'public','internal','confidential','restricted'
  regulatory_tags       TEXT[] NOT NULL DEFAULT '{}',   -- SOX, GDPR, HIPAA, ...
  dr_bc_status          TEXT NULL,          -- e.g. 'tested','documented','none'
  end_of_life_date      DATE NULL,
  end_of_support_date   DATE NULL,
  updated_at            TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_app_risk_eos    ON application_risk (end_of_support_date) WHERE end_of_support_date IS NOT NULL;
CREATE INDEX ix_app_risk_class  ON application_risk (data_classification);
CREATE INDEX ix_app_risk_regtags ON application_risk USING GIN (regulatory_tags);
```
1:1 with `applications`; cascade-deletes. Out-of-support = `end_of_support_date < now()`. Enum-like TEXT columns validated at the Pydantic boundary (Literals) to keep the vocabulary in one place.

## Migration 015 — US4: TCO (`application_cost`) — **ADP-9x6**

```sql
CREATE TABLE application_cost (
  app_id         VARCHAR(36) PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
  currency       CHAR(3) NOT NULL DEFAULT 'USD',   -- ISO-4217
  horizon_years  SMALLINT NOT NULL DEFAULT 5 CHECK (horizon_years > 0),
  -- eight buckets, each one-time + annual
  acquisition_one_time       NUMERIC(14,2) NOT NULL DEFAULT 0,  acquisition_annual       NUMERIC(14,2) NOT NULL DEFAULT 0,
  implementation_one_time    NUMERIC(14,2) NOT NULL DEFAULT 0,  implementation_annual    NUMERIC(14,2) NOT NULL DEFAULT 0,
  training_one_time          NUMERIC(14,2) NOT NULL DEFAULT 0,  training_annual          NUMERIC(14,2) NOT NULL DEFAULT 0,
  operational_one_time       NUMERIC(14,2) NOT NULL DEFAULT 0,  operational_annual       NUMERIC(14,2) NOT NULL DEFAULT 0,
  maintenance_one_time       NUMERIC(14,2) NOT NULL DEFAULT 0,  maintenance_annual       NUMERIC(14,2) NOT NULL DEFAULT 0,
  upgrades_one_time          NUMERIC(14,2) NOT NULL DEFAULT 0,  upgrades_annual          NUMERIC(14,2) NOT NULL DEFAULT 0,
  risk_downtime_one_time     NUMERIC(14,2) NOT NULL DEFAULT 0,  risk_downtime_annual     NUMERIC(14,2) NOT NULL DEFAULT 0,
  end_of_life_one_time       NUMERIC(14,2) NOT NULL DEFAULT 0,  end_of_life_annual       NUMERIC(14,2) NOT NULL DEFAULT 0,
  updated_at     TIMESTAMPTZ NOT NULL
);
```
**TCO = Σ(one_time) + Σ(annual) × horizon_years**, computed on read (not stored → no drift). `run` spend = operational + maintenance + risk_downtime; `change` spend = acquisition + implementation + upgrades; **run-vs-change ratio** derived from these. Per-BU rollup joins `applications.owning_business_unit`.

## Migration 016 — US5: technical fit (`applications`)

```sql
ALTER TABLE applications
  ADD COLUMN hosting_model        TEXT NULL,     -- 'on_prem','cloud','saas','hybrid'
  ADD COLUMN architecture_pattern TEXT NULL,     -- free-ish; validated set at boundary
  ADD COLUMN tech_debt_flags      TEXT[] NOT NULL DEFAULT '{}';  -- 'unsupported_version','deprecated_tech',...
ALTER TABLE applications
  ADD CONSTRAINT ck_app_hosting_model
      CHECK (hosting_model IS NULL OR hosting_model IN ('on_prem','cloud','saas','hybrid'));
CREATE INDEX ix_applications_hosting_model ON applications (hosting_model);
CREATE INDEX ix_applications_tech_debt     ON applications USING GIN (tech_debt_flags);
```

## Migration 017 — US6: roadmap (`transformation_initiatives`, `application_initiative_links`)

```sql
CREATE TABLE transformation_initiatives (
  id          VARCHAR(36) PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  description TEXT NULL,
  target_date DATE NULL,
  created_at  TIMESTAMPTZ NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL
);
CREATE TABLE application_initiative_links (
  app_id              VARCHAR(36) NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  initiative_id       VARCHAR(36) NOT NULL REFERENCES transformation_initiatives(id) ON DELETE CASCADE,
  planned_disposition TEXT NOT NULL,   -- 'retire','replace','modernize','invest'
  PRIMARY KEY (app_id, initiative_id),
  CONSTRAINT ck_ail_disposition CHECK (planned_disposition IN ('retire','replace','modernize','invest'))
);
CREATE INDEX ix_ail_initiative ON application_initiative_links (initiative_id);
```

## Migration 018 — US7: governance (`application_contracts`)

```sql
CREATE TABLE application_contracts (
  app_id           VARCHAR(36) PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
  contract_terms   TEXT NULL,
  renewal_date     DATE NULL,
  sla              TEXT NULL,
  business_sponsor VARCHAR(255) NULL,
  it_owner         VARCHAR(255) NULL,
  decision_rights  TEXT NULL,
  updated_at       TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_app_contracts_renewal ON application_contracts (renewal_date) WHERE renewal_date IS NOT NULL;
```
Renewals-soon = `renewal_date` within a configurable window.

## Migration 019 — US8: quality (`application_quality_metrics`)

```sql
CREATE TABLE application_quality_metrics (
  app_id             VARCHAR(36) PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
  uptime_pct         NUMERIC(5,2) NULL CHECK (uptime_pct IS NULL OR uptime_pct BETWEEN 0 AND 100),
  incidents_ytd      INTEGER NULL CHECK (incidents_ytd IS NULL OR incidents_ytd >= 0),
  satisfaction_score SMALLINT NULL CHECK (satisfaction_score IS NULL OR satisfaction_score BETWEEN 1 AND 5),
  perf_note          TEXT NULL,
  ticket_volume_30d  INTEGER NULL CHECK (ticket_volume_30d IS NULL OR ticket_volume_30d >= 0),
  updated_at         TIMESTAMPTZ NOT NULL
);
```
Manual/advisory in v1 (FR-011/021); does not override `health_score`.

## Migrations 020 / 021 — Business-fit feeders (coordinated, own beads)

- `020` — **ADP-33v**: `strategic_relevance SMALLINT NULL CHECK 1..3` on `business_capabilities` and `technical_capabilities`.
- `021` — **ADP-4ga**: `maturity_level SMALLINT NULL CHECK 1..5` on `business_capabilities`.

## Pydantic v2 Models (new / extended, `src/adp/application/models.py`)

All `model_config = ConfigDict(extra="forbid")`. Money fields typed `Decimal`.

```python
# Enums / Literals
LifecycleStatus = Literal["planned", "active", "sunset", "retired"]
HostingModel    = Literal["on_prem", "cloud", "saas", "hybrid"]
DataClassification = Literal["public", "internal", "confidential", "restricted"]
Disposition     = Literal["retire", "replace", "modernize", "invest"]
Score15 = Annotated[int, Field(ge=1, le=5)]

# Application (extended read model) — new optional fields
business_value: Score15 | None
business_criticality: Score15 | None
owning_business_unit: str | None
business_owner: str | None
technical_owner: str | None
lifecycle_status: LifecycleStatus
hosting_model: HostingModel | None
architecture_pattern: str | None
tech_debt_flags: list[str]

# ApplicationCost — one-time + annual per bucket; computed TCO
class CostBucket(BaseModel):
    one_time: Decimal = Decimal("0")
    annual:   Decimal = Decimal("0")

class ApplicationCost(BaseModel):
    currency: str = "USD"           # ISO-4217, validated
    horizon_years: Annotated[int, Field(gt=0)] = 5
    acquisition: CostBucket; implementation: CostBucket; training: CostBucket
    operational: CostBucket; maintenance: CostBucket; upgrades: CostBucket
    risk_downtime: CostBucket; end_of_life: CostBucket
    # tco (Decimal) and run_vs_change (tuple[Decimal, Decimal]) derived on read

class ApplicationRisk(BaseModel):
    security_posture: str | None; vulnerability_status: str | None
    data_classification: DataClassification | None
    regulatory_tags: list[str] = []
    dr_bc_status: str | None
    end_of_life_date: date | None; end_of_support_date: date | None

class TransformationInitiative(BaseModel):
    id: str; name: str; description: str | None; target_date: date | None
    created_at: datetime; updated_at: datetime

class ApplicationContract(BaseModel):
    contract_terms: str | None; renewal_date: date | None; sla: str | None
    business_sponsor: str | None; it_owner: str | None; decision_rights: str | None

class ApplicationQualityMetric(BaseModel):
    uptime_pct: Decimal | None; incidents_ytd: int | None
    satisfaction_score: Score15 | None; perf_note: str | None; ticket_volume_30d: int | None

# RationalizationEntry (derived, read-only)
class RationalizationEntry(BaseModel):
    app_id: str; name: str
    business_value: Score15 | None; health_score: Score15 | None
    quadrant: Literal["tolerate", "invest", "migrate", "eliminate"] | None  # None = unassessed
```

## Authz additions (`src/adp/authz`)

New actions in `permissions.py` (+ bump `PERMISSIONS_VERSION`): `READ_APPLICATION_COST` / `WRITE_APPLICATION_COST`, `READ_APPLICATION_RISK` / `WRITE_APPLICATION_RISK`, `READ_APPLICATION_GOVERNANCE` / `WRITE_APPLICATION_GOVERNANCE`. General application read does **not** imply these. Rollup/aggregate endpoints re-check the corresponding read action before emitting per-application sensitive values (FR-013 / SC-004). Route→action mapping registered in `enforcement.py`.
