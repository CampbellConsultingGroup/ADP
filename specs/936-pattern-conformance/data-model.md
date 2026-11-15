# Data Model: EA Pattern Adoptions, Conformance & Discovery (936)

Migration `045_ea_pattern_adoption.py` (`down_revision = "044"`). All ids are `String(36)`/TEXT.

## Tables

### `ea_pattern_adoption`

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | uuid4 |
| `pattern_key` | TEXT NOT NULL | FK → `ea_pattern.pattern_key` ON DELETE CASCADE |
| `pinned_version_id` | String(36) NULL | FK → `ea_pattern_version.id` ON DELETE RESTRICT; NULL = follow current |
| `scope_type` | TEXT NOT NULL | `business_domain` \| `application_set` \| `portfolio` |
| `scope_ref` | String(36) NULL | FK → `business_domains.id` ON DELETE CASCADE |
| `name` | TEXT NOT NULL | 1–120 characters |
| `created_at`, `created_by`, `updated_at` | | |

Constraints:
- `ck_ea_pattern_adoption_scope_type`
- `ck_ea_pattern_adoption_scope_ref` (`(scope_type = 'business_domain') = (scope_ref IS NOT NULL)`)
- `ck_ea_pattern_adoption_name_len`
- `uq_ea_pattern_adoption_domain` (`pattern_key`, `scope_ref`) WHERE `scope_type = 'business_domain'`
- `uq_ea_pattern_adoption_portfolio` (`pattern_key`) WHERE `scope_type = 'portfolio'`
- `uq_ea_pattern_adoption_name` (`pattern_key`, `name`)

### `ea_pattern_adoption_member`

PK(`adoption_id`, `application_id`). `adoption_id` → adoption CASCADE; `application_id` → `applications.id` CASCADE.

### `ea_pattern_adoption_pin`

PK(`adoption_id`, `role_key`, `element_type`, `element_id`).
- `adoption_id` → adoption CASCADE.
- `ck_ea_pattern_adoption_pin_type`: `element_type` IN the 7 `ElementType` values.
- `element_id`: no FK (polymorphic).

## Snapshot element maps (the authoring contract, FR-005/FR-006)

| Element | Keys |
|---|---|
| application | `id, name, lifecycle_status, application_type, time_classification, r_strategy, pace_layer, hosting_model, architecture_pattern, business_criticality, health_score, tech_debt_flags, domain_ids, capability_ids, technical_capability_ids` + gated `security_posture, vulnerability_status, data_classification, dr_bc_status, end_of_life_date, end_of_support_date` (READ_APPLICATION_RISK), `tco` (READ_APPLICATION_COST), `renewal_date, sla` (READ_APPLICATION_GOVERNANCE) |
| integration | `id, name` ("source → target"), `integration_type, description, source{id,name,domain_ids}, target{id,name,domain_ids}, cross_domain` (bool \| null) |
| business_capability | `id, name, level, parent_id, domain_id, strategic_relevance, maturity_level` |
| value_stream | `id, name, stage_ids` |
| business_domain | `id, name, classification, risk_flags` |
| technical_capability | `id, name, level, parent_id` |
| agent | `id, name, lifecycle_status, autonomy_level, human_approval, data_classification_max, solution_ids` |

Nullable registry values are present as `null`. Gated keys the caller cannot read are **absent**.

## Conformance models (`adp.patterns.conformance_models`, frozen, `extra="forbid"`)

| Model | Fields |
|---|---|
| `ScopeType` | business_domain, application_set, portfolio |
| `ConformanceStatus` | conformant, conformant_with_warnings, non_conformant, indeterminate, not_applicable |
| `FindingKind` | violation, match, binding, evaluation_error, field_unavailable, unverifiable, limit |
| `ElementRef` | `type: ElementType, id, name` |
| `Finding` | `code, kind, severity, rule, element_refs (≤100), truncated: bool` |
| `RoleBinding` | `role_key, element_type, label, elements: list[ElementRef], count` |
| `BindingResult` | `roles: list[RoleBinding]` (declared order), `findings` |
| `PlateauState` | `reached: str \| None, next: str \| None, blocking: list[str]` |
| `ConformanceReport` | `adoption_id: str \| None, pattern_key, version: str \| None, digest: str \| None, evaluated_at, scope, bindings: list[RoleBinding], findings, status, plateau: PlateauState \| None` |
| `DiscoveryReport` | `pattern_key, version, digest, evaluated_at, matches: list[Finding], match_count` |
| `EvalLimits` | `max_element_evaluations: int = 50_000, max_element_refs: int = 100` |
| `AdoptionScope` | `scope_type, scope_ref: str \| None, member_ids: list[str]` |
| `PinIn` | `role_key, element_type, element_id` |
| `AdoptionCreate` | `pattern_key, name (1–120), scope_type, scope_ref?, member_ids?, pinned_version?: str (semver), pins?: list[PinIn]` |
| `AdoptionUpdate` | `name?, pinned_version?` (explicit null = follow current) |
| `Adoption` | `id, pattern_key, pattern_name, kind, name, scope_type, scope_ref, scope_name, member_ids, pinned_version, resolved_version, pins, created_at, created_by, updated_at, status?: ConformanceStatus` |
| `EvaluateRequest` | `yaml?: str (≤256 KB), pattern_key?, version?, scope: AdoptionScope, pins?: list[PinIn]`; exactly one of yaml or (pattern_key + version) |

## Finding codes

| Code | Kind | Severity |
|---|---|---|
| `B1.no_current_version` | binding | info (status → not_applicable) |
| `B2.pin_fails_selector` | binding | warning |
| `B3.dangling_pin` | binding | error |
| `K:<role>`, `K:<role>/<per>` | violation | error |
| `E:<R..>` | violation, or unverifiable (info) | error / info |
| `S:<role>` | evaluation_error | error (selector errors summarised per role) |
| `C<n>` | violation / match / evaluation_error / field_unavailable | constraint severity (error for evaluation_error) |
| `L1.limit_exceeded` | limit | error |

## Store exceptions → HTTP

| Exception | Status |
|---|---|
| `AdoptionNotFoundError`, `PatternNotFoundError`, `PatternVersionNotFoundError`, `ScopeTargetNotFoundError` | 404 |
| `DuplicateAdoptionError` | 409 |
| `InvalidPinError(reasons)`, `InvalidScopeError`, `DraftPinError` | 422 |
| `NotAntiPatternError` | 422 |

## State and derivation

Nothing about conformance is stored. Status and plateau are computed by `compute_conformance_status(findings, bindings)` and `compute_transition_plateau(defn, findings)` on every read.
