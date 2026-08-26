# Data Model: Hybrid Search Phase 2 Completion

No schema change. No new table, no new column, no new migration.

## `searchable_items` (existing, migration 011) — one more discriminator value

| entity_type | entity_id | indexed text | Written by |
|---|---|---|---|
| `business_capability` | capability id | name + description | `adp.business.store` (phase 1, unchanged) |
| `technical_capability` | tech cap id | name + description | `adp.application.store` (phase 1, unchanged) |
| `application` | application id | name + description | `adp.application.store` (041, unchanged) |
| `value_stream` | value stream id | name + description | `adp.business.store` (041, unchanged) |
| `business_domain` | domain id | name + scope_statement **+ org_unit (NEW)** | `adp.business.store` (041 + this feature's FR-006) |
| `value_stream_stage` **(NEW)** | stage id | name + description | `adp.business.store` (this feature, FR-001–005) |

## New constant (`adp.search.index`)

```python
ENTITY_VALUE_STREAM_STAGE = "value_stream_stage"
```

Re-exported from `adp.search.__init__` alongside its five siblings.

## Write-hook call sites (`adp.business.store`)

| Function | Before this feature | After this feature |
|---|---|---|
| `add_stage` | no index call | `index_entity(ENTITY_VALUE_STREAM_STAGE, stage_id, build_text(name, description), session)` |
| `update_stage` | no index call | same, using the refreshed row's name/description |
| `delete_stage` | no unindex call | `unindex_entity(ENTITY_VALUE_STREAM_STAGE, stage_id, session)` on successful delete |
| `reorder_stages` | no index/unindex calls | `unindex_entity` for each dropped stage id; `index_entity` for each surviving (possibly renamed) stage |
| `delete_value_stream` | unindexes the value stream only (stages silently orphaned in the index) | additionally reads the value stream's stage ids *before* the cascading delete and unindexes each |
| `create_domain` | `build_text(name, scope_statement)` | `build_text(name, scope_statement, org_unit)` |
| `update_domain` | `build_text(name, scope_statement)` | `build_text(name, scope_statement, org_unit)` |

## `adp.search.backfill` — new function

```python
async def reindex_all(session: AsyncSession) -> dict[str, int]:
    """Indexes every write-hooked entity type. Returns a per-entity_type count."""
```

Covers, in one pass: `business_capability`, `technical_capability` (both via the existing
`reindex_capabilities()`, called internally), `application`, `value_stream`,
`value_stream_stage`, `business_domain`. `main()` calls `reindex_all()` instead of
`reindex_capabilities()` directly.

## No new Pydantic model, no new API response shape

`ValueStreamStage`/`BusinessDomain` are unchanged — this feature is entirely about what gets
written into the existing polymorphic index, not about any entity's own public shape.
