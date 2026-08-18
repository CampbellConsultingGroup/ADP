# Phase 1 Data Model: Derived Compliance Status

No new table, no new migration, no new Pydantic model. This feature adds no persisted entity — its
only "data model" is the shape of the pure derivation and its thin lookup wrapper, both operating
entirely over types COMPLY-01/COMPLY-02 already define.

## Reused types (unchanged, from `adp.compliance.models`)

- **`ComplianceStatus`** (`StrEnum`): `COMPLIANT | PARTIAL | NON_COMPLIANT | NOT_ASSESSED |
  NOT_APPLICABLE`. This feature's output type — identical vocabulary to an individual mapping's own
  status (spec.md FR-009), so a derived status can sit anywhere an individual mapping's status
  already appears without a display-layer special case.
- **`MappingTargetType`** (`StrEnum`): `CAPABILITY | APPLICATION | DESIGN | PATTERN | ORGANIZATION`.
  This feature's dispatch key — restricted to the first four values (research.md D4); `ORGANIZATION`
  is a valid enum member overall but not a valid input to this feature's entity-lookup function.
- **`ControlMapping`** (read model): only its `.compliance_status` field is consumed here; every other
  field (`control_id`, `target_id`, `evidence_ref`, `assessed_at`, `assessed_by`, `created_at`) passes
  through unread by this feature.

## New functions (`src/adp/compliance/store.py`)

### `compute_compliance_status`

```text
compute_compliance_status(statuses: list[ComplianceStatus]) -> ComplianceStatus
```

Pure, synchronous, no I/O (research.md D2/D3). Implements the decision table from research.md D5:

| Input condition (evaluated in order) | Output |
|---|---|
| `statuses` is empty | `NOT_ASSESSED` |
| any element is `NON_COMPLIANT` | `NON_COMPLIANT` |
| else, any element is `PARTIAL` or `NOT_ASSESSED` | `PARTIAL` |
| else, any element is `COMPLIANT` | `COMPLIANT` |
| else (every element is `NOT_APPLICABLE`) | `NOT_APPLICABLE` |

The five rows are exhaustive and mutually exclusive over `ComplianceStatus`'s five values — every
possible non-empty `list[ComplianceStatus]` matches exactly one row after the empty-list case is
handled first.

**Traces to**: spec.md FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009; SC-001, SC-002,
SC-004.

### `get_entity_compliance_status`

```text
async get_entity_compliance_status(
    entity_type: MappingTargetType,
    entity_id: str,
    session: AsyncSession,
) -> ComplianceStatus
```

Thin async dispatch wrapper (research.md D3/D4). Behavior:

1. If `entity_type` is `ORGANIZATION` (or any value other than the four supported types), raise
   `ValueError` — there is no per-entity lookup for the estate-wide scope (research.md D4).
2. Otherwise, call the matching existing store function —
   `list_mappings_for_capability`/`list_mappings_for_application`/`list_mappings_for_design`/
   `list_mappings_for_pattern` (all pre-existing, COMPLY-02) — to fetch every `ControlMapping`
   currently targeting `entity_id`.
3. Extract `.compliance_status` from each returned mapping into a plain list.
4. Return `compute_compliance_status(that list)`.

This function does not itself validate that `entity_id` refers to an existing entity — the
`list_mappings_for_*` functions it calls already return an empty list (not an error) for an
entity_id with zero mappings, and an entity with zero mappings correctly derives to `NOT_ASSESSED`
per the same rule as an entity with zero mapped controls for any other reason (spec.md FR-005). This
matches COMPLY-02's own established behavior — `list_mappings_for_capability` et al. do not validate
existence either.

**Traces to**: spec.md FR-001, Assumptions ("Scope of entity types").

## State transitions

Not applicable — there is no persisted state for this feature to transition. The derived value is
recomputed from current `ControlMapping` rows on every call (spec.md FR-007); "transitions" are
entirely a property of the underlying `ControlMapping` writes COMPLY-02 already governs, unchanged by
this feature.
