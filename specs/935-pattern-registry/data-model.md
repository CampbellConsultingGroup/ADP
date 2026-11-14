# Data Model: EA Pattern Registry (935)

Migration `044_ea_pattern_registry.py` (`down_revision = "043"`). All ids and keys are TEXT or `String(36)`, as everywhere in ADP. Timestamps are `TIMESTAMPTZ`.

## Tables

### `ea_pattern` (family)

| Column | Type | Notes |
|---|---|---|
| `pattern_key` | TEXT PK | 934 key grammar: dotted lowercase, 2–5 segments |
| `kind` | TEXT NOT NULL | `reference-architecture` \| `portfolio-rule` \| `transition` \| `anti-pattern`. Fixed per family |
| `owner_role` | TEXT NOT NULL | `enterprise` (934 V9) |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `created_by` | TEXT NOT NULL | |

CHECKs:
- `ck_ea_pattern_key_format`: `pattern_key ~ '^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){1,4}$'` (identical to 934 `PatternKey`, `src/adp/patterns/models.py:33`);
- `ck_ea_pattern_kind`;
- `ck_ea_pattern_owner_role`.

### `ea_pattern_version`

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | uuid4 |
| `pattern_key` | TEXT NOT NULL | FK → `ea_pattern.pattern_key` ON DELETE CASCADE |
| `version` | TEXT NOT NULL | semver `MAJOR.MINOR.PATCH` |
| `lifecycle` | TEXT NOT NULL DEFAULT `'draft'` | see state machine |
| `name` | TEXT NOT NULL | Denormalised from the definition |
| `summary` | TEXT NOT NULL | Denormalised |
| `definition` | JSONB NOT NULL | `json.loads(to_canonical_json(defn))` |
| `digest` | CHAR(64) NOT NULL | `compute_digest(defn)` |
| `created_at`, `created_by` | NOT NULL | |
| `lifecycle_changed_at`, `lifecycle_changed_by` | NOT NULL | Set at creation, updated on every transition |

Constraints and indexes:
- `uq_ea_pattern_version_key_version` UNIQUE(`pattern_key`, `version`);
- `uq_ea_pattern_version_current` UNIQUE(`pattern_key`) WHERE `lifecycle = 'current'` (also declared on the store table with `sqlite_where`; research D2);
- `ck_ea_pattern_version_semver`;
- `ck_ea_pattern_version_lifecycle`;
- `ix_ea_pattern_version_digest`;
- `ix_ea_pattern_version_lifecycle`.

### `ea_pattern_relation`

| Column | Type | Notes |
|---|---|---|
| `source_version_id` | String(36) | PK part; FK → `ea_pattern_version.id` ON DELETE CASCADE |
| `target_pattern_key` | TEXT | PK part; **no FK** (research D2). An unresolved target is allowed in drafts |
| `relation_type` | TEXT | PK part; `realizes` \| `specializes` \| `replaces` \| `conflicts_with` \| `requires` \| `alternative_to` |
| `note` | TEXT NULL | |

- `ck_ea_pattern_relation_type`;
- `ix_ea_pattern_relation_target`.

Rows are rewritten from the definition on import and on draft update.

### `ea_pattern_lifecycle_event`

| Column | Type | Notes |
|---|---|---|
| `id` | String(36) PK | |
| `version_id` | String(36) NOT NULL | FK → `ea_pattern_version.id` ON DELETE CASCADE |
| `from_state` | TEXT NOT NULL | |
| `to_state` | TEXT NOT NULL | |
| `reason` | TEXT NOT NULL | 1–500 characters (`ck_ea_pattern_event_reason_len`) |
| `confirmation_id` | TEXT NOT NULL | ART-VIII |
| `actor` | TEXT NOT NULL | |
| `at` | TIMESTAMPTZ NOT NULL | |
| `caused_by_event_id` | String(36) NULL | Set on the automatic demotion row; points at the promotion event (no FK: same-transaction insert order) |

- `ck_ea_pattern_event_states`;
- `ix_ea_pattern_event_version`.

### Touched, no schema change

| Table | Change |
|---|---|
| `knowledge_items` | Rows with `id = source_ref = 'adp-pattern:<key>'` are written by the registry (research D6). `metadata.managed_by = 'pattern-registry'` |
| `control_pattern_mapping` | Application-level target check widened to kind `pattern` or `reference_architecture` (research D9) |

## State machine (`PatternLifecycle`)

```
draft ──▶ proposed ──▶ current ──▶ deprecated ──▶ decommissioned
  ▲          │                         │
  └──────────┘                         └──▶ current   (rollback)
```

| From | Allowed to | Effects |
|---|---|---|
| `draft` | `proposed` | Definition frozen |
| `proposed` | `current`, `draft` | `current`: re-validate + resolve (errors block), demote the other current version (extra event with `caused_by_event_id`), project. `draft`: editable again |
| `current` | `deprecated` | If no other version is current → projection deactivated |
| `deprecated` | `current`, `decommissioned` | `current`: same as promotion |
| `decommissioned` | — | Terminal |

Invariants:
- I1 at most one `current` per family (database-enforced);
- I2 `definition`/`digest` change only in `draft`;
- I3 only drafts are deleted; deleting the last version deletes the family;
- I4 a projection is active ⇔ the family has a current version.

## API models (`adp.patterns.registry_models`, frozen, `extra="forbid"`)

| Model | Fields |
|---|---|
| `PatternLifecycle` | StrEnum: draft, proposed, current, deprecated, decommissioned |
| `ImportStatus` | StrEnum: created, unchanged, rejected |
| `PatternViewKind` | StrEnum: structure, catalog, traceability |
| `PatternVersionSummary` | `id, pattern_key, version, kind, lifecycle, name, summary, tags, digest, created_at, created_by, lifecycle_changed_at` |
| `PatternFamily` | `pattern_key, kind, owner_role, created_at, created_by, current_version: str \| None, versions: list[PatternVersionSummary]` (current first, then semver descending) |
| `PatternRelationRow` | `source_version_id, source_pattern_key, target_pattern_key, relation_type, note, target_resolved: bool` |
| `LifecycleEvent` | `id, from_state, to_state, reason, confirmation_id, actor, at, caused_by_event_id` |
| `PatternVersionDetail` | Summary + `definition: PatternDefinition`, `relations: list[PatternRelationRow]`, `issues: list[PatternIssue]` (current resolution warnings), `allowed_transitions: list[PatternLifecycle]`, `history: list[LifecycleEvent]`, `knowledge_item_id: str \| None` |
| `PatternImportResult` | `status: ImportStatus, version: PatternVersionSummary \| None, issues: list[PatternIssue]` |
| `PatternValidateResult` | `ok: bool, digest: str \| None, issues: list[PatternIssue]` |
| `LifecycleTransitionRequest` | `to: PatternLifecycle, reason: str (1–500, stripped non-empty), confirmation_id: str (non-empty)` |
| `PatternRenderRequest` | `yaml: str (≤ 256 KB), view: Literal["structure"]` |
| `PatternViewResponse` | `view, flowchart: str, digest, generated_at, truncated: list[str]` |
| `PatternListResponse` | `items: list[PatternVersionSummary], total: int` |

Store exceptions → HTTP:

| Exception | Status |
|---|---|
| `PatternNotFoundError` | 404 |
| `PatternVersionNotFoundError` | 404 |
| `NotDraftError` | 409 |
| `IllegalTransitionError` | 409 |
| `ConcurrentPromotionError` | 409 |
| `PromotionBlockedError(issues)` | 422, with issues in the body |
| `KnowledgeItemManagedError` | 409, raised by the knowledge router |

## Issue codes added (on top of 934's P/V/schema codes)

| Code | Severity at import/update | At promotion |
|---|---|---|
| `R1.unresolved_principle` | warning | error |
| `R2.unresolved_control` | warning | error |
| `R3.unresolved_relation` | warning | error |
| `R4.unresolved_implementation` | warning | error |
| `I1.version_exists_use_update` | error (rejected) | — |
| `I2.version_immutable` | error (rejected) | — |
| `I3.kind_mismatch` | error (rejected) | — |
| `U1.identity_changed` | error | — |

## Knowledge projection (derived)

| Field | Value |
|---|---|
| `id`, `source_ref` | `adp-pattern:<key>` |
| `kind` | `reference_architecture` if pattern kind is `reference-architecture`, else `pattern` |
| `version` | the current pattern version |
| `title` | `name` |
| `full_text` | `summary` + `Context:` / `Problem:` / `Forces:` / `Benefits:` / `Liabilities:` / `Tags:` lines (empty parts omitted) |
| `metadata` | `{"managed_by": "pattern-registry", "pattern_key", "pattern_version", "pattern_kind"}` |
| `active` | true while the family has a current version |
| `embedding` | `embed_or_zero(title, full_text)` |
