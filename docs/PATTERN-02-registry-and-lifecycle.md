# PATTERN-02 — Pattern registry & lifecycle

**Bundle:** PATTERN · **Package:** `adp.patterns` · **Depends on:** PATTERN-01 · **Status:** draft

## What

Persist pattern versions, enforce lifecycle transitions, and expose YAML import/export over the API. Normalize only what needs cross-pattern queries: pattern↔pattern relations and motivation links to principles and controls.

## Why

Patterns need to be governed artifacts: versioned, immutable once proposed, with exactly one `current` version per pattern. The catalog view (PATTERN-04) and the conformance engine (PATTERN-03) need a stable `pattern_version_id` to reference.

## Storage decision (explicit)

| Concern | Decision | Rationale |
|---|---|---|
| Roles, relationships, constraints, transition | **JSONB** `definition` column on the version row | The version is an immutable document. Nothing queries roles across patterns yet. Normalizing would duplicate PATTERN-01 validation in SQL |
| Pattern ↔ pattern relations | **Join table** | The catalog graph and "what replaces X" are cross-pattern queries |
| Pattern ↔ principle, pattern ↔ control | **Join tables** with FK + cascade | Traceability must be FK-enforced, matching the existing capability↔design and objective↔capability links |
| Family vs. version | Two tables: `ea_pattern` (stable key) and `ea_pattern_version` | Relations target a pattern **family** (any version), so the FK needs a unique key |

## Migration — `NNNN_ea_patterns.py`

### `ea_pattern` (family)

| Column | Type | Notes |
|---|---|---|
| `pattern_key` | `TEXT` PK | |
| `kind` | `TEXT NOT NULL` | Fixed per family; changing kind means a new key |
| `owner_role` | `TEXT NOT NULL` | |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | |
| `created_by` | `TEXT NOT NULL` | |

CHECKs: `ck_ea_pattern_key_format` (the PatternKey regex), `ck_ea_pattern_kind` (enum values), `ck_ea_pattern_owner_role` (enum values).

### `ea_pattern_version`

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `pattern_key` | `TEXT NOT NULL` FK → `ea_pattern.pattern_key` `ON DELETE CASCADE` | |
| `version` | `TEXT NOT NULL` | |
| `lifecycle` | `TEXT NOT NULL DEFAULT 'draft'` | |
| `name` | `TEXT NOT NULL` | Denormalized from `definition` for list views |
| `summary` | `TEXT NOT NULL` | Denormalized |
| `definition` | `JSONB NOT NULL` | Canonical JSON (PATTERN-01) |
| `digest` | `CHAR(64) NOT NULL` | `compute_digest()` |
| `created_at` / `created_by` | | |
| `lifecycle_changed_at` / `lifecycle_changed_by` | | |

Constraints:
- `uq_ea_pattern_version_key_version` UNIQUE (`pattern_key`, `version`)
- `uq_ea_pattern_version_current` **partial UNIQUE** (`pattern_key`) `WHERE lifecycle = 'current'`: at most one current version per family
- `ck_ea_pattern_version_semver`, `ck_ea_pattern_version_lifecycle`
- Index on `digest` (for idempotent import)

### Join tables

| Table | Composite PK | FKs (`ON DELETE CASCADE`) | Extra |
|---|---|---|---|
| `ea_pattern_relation` | (`source_version_id`, `target_pattern_key`, `relation_type`) | `source_version_id` → `ea_pattern_version.id`; `target_pattern_key` → `ea_pattern.pattern_key` | `note TEXT`; `ck_ea_pattern_relation_type` |
| `ea_pattern_principle_link` | (`pattern_version_id`, `knowledge_item_id`) | → `ea_pattern_version.id`; → knowledge item table (**verify table/PK name in `adp.knowledge`**) | |
| `ea_pattern_control_link` | (`pattern_version_id`, `control_id`) | → `ea_pattern_version.id`; → COMPLY-01 `control` | **Ship only if COMPLY-01 has merged**; otherwise defer to a follow-on migration |

**Relation targets must already exist.** Importing a pattern that `replaces` an unknown key fails with `unknown_relation_target`. **Open:** should a stub family be auto-created instead? See OQ-2.

## Lifecycle

`compute_allowed_transitions(current: PatternLifecycle) -> frozenset[PatternLifecycle]` is a pure function.

| From | Allowed to | Side effects |
|---|---|---|
| `draft` | `proposed` | `definition` becomes **immutable** |
| `proposed` | `current`, `draft` | → `current` atomically demotes the existing current version to `deprecated` in the same transaction. → `draft` re-opens editing |
| `current` | `deprecated` | |
| `deprecated` | `decommissioned`, `current` | Re-promotion is allowed (rollback); it also demotes any other current version |
| `decommissioned` | — | terminal |

Rules:
- `definition` and `digest` can change only while `lifecycle = draft` (enforced in the store; tested).
- A version can be deleted only in `draft`. Deleting the last version deletes the family (store logic, not a trigger).
- Promotion to `current` re-runs the full PATTERN-01 validation **plus** reference resolution (principles, controls, relation targets). A version that imported cleanly can fail promotion if a referenced principle was deleted in the meantime.

## Models — `adp/patterns/models.py` (additions)

| Model | Fields |
|---|---|
| `PatternVersionSummary` | `id, pattern_key, version, kind, lifecycle, name, summary, digest, created_at` |
| `PatternVersionDetail` | `PatternVersionSummary` + `definition: PatternDefinition` + `relations` + `principle_ids` + `control_ids` |
| `PatternImportResult` | `status: Literal["created", "unchanged", "rejected"]`, `version: PatternVersionSummary \| None`, `issues: list[PatternIssue]` |
| `LifecycleTransitionRequest` | `to: PatternLifecycle`, `reason: str (1–500)` |

## Store — `adp/patterns/store.py`

Core `Table()` objects with no FK/PK/CHECK (the convention). Async functions:

| Function | Notes |
|---|---|
| `import_pattern(yaml_text, actor)` | parse → validate → resolve refs → see idempotency below → insert family (if new) + version + links in **one transaction** |
| `update_draft(version_id, yaml_text, actor)` | Only when `draft`; replaces definition, digest and links |
| `transition_lifecycle(version_id, req, actor)` | Uses `compute_allowed_transitions`; does the demote-current swap in one transaction, honouring the partial unique index |
| `get_version(key, version)`, `get_current(key)`, `list_versions(filters)` | Filters: `kind`, `lifecycle`, `tag` (JSONB `definition->'tags' ?`), `q` (name/summary ILIKE) |
| `list_relations(key=None)` | Feeds the catalog view (PATTERN-04) |
| `delete_draft(version_id)` | |
| `export_yaml(version_id)` | `to_canonical_yaml()` with registry `lifecycle` injected |

**Idempotency:**

| Case | Result |
|---|---|
| Same `(key, version)` and same digest | `unchanged` |
| Same `(key, version)`, different digest, existing row is `draft` | `rejected` (`version_exists_use_update`) |
| Same `(key, version)`, different digest, existing row is not `draft` | `rejected` (`version_immutable`) |
| New `(key, version)` | `created` (as `draft`) |
| Kind differs from the family's kind | `rejected` (`kind_mismatch`) |

## Router — `adp/patterns/router.py`, prefix `/api/v1/patterns`

| Method & path | Action | Notes |
|---|---|---|
| `GET /` | read | List with filters |
| `GET /{key}` | read | Family plus versions, current first |
| `GET /{key}/versions/{version}` | read | Detail |
| `GET /{key}/versions/{version}/yaml` | read | `application/yaml` |
| `POST /import` | `PATTERN_WRITE` | Body `application/yaml` (≤ 256 KB). `201` created, `200` unchanged, `422` rejected (issues in body) |
| `PUT /{key}/versions/{version}` | `PATTERN_WRITE` | Draft only, otherwise `409` |
| `POST /{key}/versions/{version}/lifecycle` | `PATTERN_GOVERN` | `409` on an illegal transition |
| `DELETE /{key}/versions/{version}` | `PATTERN_WRITE` | Draft only |

**Permissions:** add `ActionType.PATTERN_WRITE` and `ActionType.PATTERN_GOVERN`. Add a route-prefix rule for `/api/v1/patterns`. Bump the permission table v1.8.0 → **v1.9.0**. Default grant: Enterprise Architect gets both. No other role is granted write in this spec (OQ-3).

**Audit:** import, update, transition and delete write audit entries (actor, timestamp, digest before/after, reason for transitions), using the existing audit trail mechanism.

## Export integration

Register the pattern registry with `adp.export` so `current` versions are written to `patterns/<pattern_key>@<version>.yaml` in the versioned export, byte-identical to `export_yaml()`. Whether git → DB import on merge is also wired up depends on OQ-B1 and is **not built here**.

## Tests

| Test | Asserts |
|---|---|
| `test_migration_upgrade_downgrade` | Clean up/down; named CHECKs present |
| `test_import_created_unchanged_rejected` | Every row of the idempotency table |
| `test_import_atomic` | Failure on a link insert leaves no family or version row |
| `test_definition_immutable_after_proposed` | `update_draft` on `proposed` raises/409 |
| `test_lifecycle_transition_table` | Pure function: every from/to pair (parametrized over the full matrix) |
| `test_single_current_swap` | Promoting v2 demotes v1 to `deprecated` in one transaction; concurrent promotion triggers the partial-index violation, mapped to 409 |
| `test_promotion_revalidates_refs` | A deleted principle makes promotion fail with `unresolved_principle` |
| `test_relation_cascade` | Deleting a family cascades the relations that target it |
| `test_permissions_completeness` | Existing completeness test passes with the new routes |
| `test_export_byte_identical` | Export file equals the `GET …/yaml` body |

## Out of scope

Git-to-DB sync, AI pattern drafting, editing in the UI, diffing between versions, sensitivity-gated reads (no pattern content is sensitive).

## Open questions

| # | Question |
|---|---|
| OQ-1 | (= OQ-B1) Git canonical or DB canonical? |
| OQ-2 | Auto-create a stub `ea_pattern` family for unknown relation targets (so you can say "replaces X" before X is written), or keep the hard failure? |
| OQ-3 | Should Solution Architects be allowed to import `draft` patterns (proposing upward), with only EAs able to `PATTERN_GOVERN`? |
| OQ-4 | (= OQ-B4) Coexistence with or migration from `adp.knowledge` pattern items. A `knowledge_item_id` column on `ea_pattern` would allow linking without migrating. |
| OQ-5 | Should `deprecated → current` rollback require a reason of its own, distinct from ordinary promotion? |
