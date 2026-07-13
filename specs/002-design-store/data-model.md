# Data Model: Persistence & Design Store

**Branch**: `002-design-store` | **Date**: 2026-06-27  
**Source**: `src/adp/store/records.py` (SQLAlchemy 2 ORM table definitions)

This document describes the persistence schema — the tables and their contracts. The canonical domain entities (`ArchitectureDescription`, `Element`, etc.) are defined in ADP-SPEC-001 (`src/adp/models.py`); this spec stores them, not redefines them.

---

## Persistence Schema Tables

### `designs`

The mutable pointer table. One row per logical design; the only mutable column is `current_version`.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `TEXT` | NOT NULL | Stable design identifier (matches `ArchitectureDescription.id`); primary key |
| `current_version` | `INTEGER` | NOT NULL | Version number of the latest committed version; updated atomically when a new version is saved |
| `title` | `TEXT` | NOT NULL | Denormalized from `ArchitectureDescription.title` for fast listing without reading content |
| `schema_version_at_creation` | `TEXT` | NOT NULL | Schema version when the design was first created |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | When the design was first persisted |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | When the most recent version was committed |

**Constraints**: `id` is the primary key. `current_version` is updated only in the same transaction that inserts a new `design_versions` row.

---

### `design_versions`

Immutable per-version snapshots. Once a row is inserted, no column may ever change.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `design_id` | `TEXT` | NOT NULL | FK → `designs.id`; part of composite PK |
| `version_num` | `INTEGER` | NOT NULL | Monotonically increasing per design; part of composite PK |
| `schema_version` | `TEXT` | NOT NULL | Schema version (`ArchitectureDescription.schema_version`) at time of write |
| `content` | `JSONB` | NOT NULL | Full serialized `ArchitectureDescription`; validated against published schema before insert |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | When this version was committed |
| `created_by` | `TEXT` | NOT NULL | Actor who initiated this save |

**Primary key**: `(design_id, version_num)`  
**Constraints**: No UPDATE or DELETE permitted (enforced by ORM structure + database trigger).  
**Indexes**: 
- GIN index on `content` (full JSONB) for JSONB path queries
- Targeted expression index on `content -> 'elements'` for satisfies queries

---

### `audit_entries`

Append-only audit trail. Structurally non-deletable and non-updatable (database trigger + ORM).

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `TEXT` | NOT NULL | Stable audit entry identifier (matches `AuditEntry.id` from the model); primary key |
| `design_id` | `TEXT` | NOT NULL | FK → `designs.id`; which design this mutation affected |
| `design_version` | `INTEGER` | NOT NULL | Version number this entry was recorded against |
| `actor` | `TEXT` | NOT NULL | Human user ID or system step name |
| `action` | `TEXT` | NOT NULL | e.g., `"add-element"`, `"accept-verdict"` |
| `affected_entity` | `TEXT` | NOT NULL | ID of the mutated entity within the design |
| `summary` | `TEXT` | NOT NULL | What changed (max 240 chars, matching model constraint) |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL | When the mutation occurred |
| `origin` | `TEXT` | NOT NULL | `"human"` or `"ai"` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | When this row was inserted (server time; may differ from `timestamp`) |

**Primary key**: `id`  
**Indexes**: `(design_id, design_version)` for audit log retrieval by design  
**Trigger**: `BEFORE UPDATE OR DELETE ON audit_entries EXECUTE FUNCTION deny_audit_mutation()` — raises an exception regardless of caller

---

## Store Interface Entities (Python)

These are the return types from `DesignStore` operations — not persisted directly but produced from the tables above.

### `DesignRecord`

Returned by `save()` and `list_versions()`. Represents the current state of a design in the store.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | Stable design identifier |
| `current_version` | `int` | Latest version number |
| `title` | `str` | Current title |
| `created_at` | `datetime` | First persisted |
| `updated_at` | `datetime` | Last version committed |

### `DesignVersion`

Returned by `list_versions()`. Metadata about one version without the full content.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | Stable design identifier |
| `version_num` | `int` | This version's number |
| `schema_version` | `str` | Schema version at time of write |
| `created_at` | `datetime` | When this version was committed |
| `created_by` | `str` | Who committed it |

### `VerdictChain`

Returned by `query_verdict_chain()`. Aggregates the full traceability thread for one SolutionOption.

| Field | Type | Notes |
|---|---|---|
| `option` | `SolutionOption` | The option queried |
| `satisfies_requirements` | `list[Requirement]` | Requirements this option satisfies |
| `satisfying_elements` | `list[Element]` | Elements that also satisfy those requirements |
| `verdict` | `Verdict \| None` | The recorded verdict on this option (if any) |

---

## Schema Relationships

```
designs (one)
  │
  ├──── design_versions (many, immutable per-version snapshots)
  │         content: JSONB (full ArchitectureDescription)
  │         GIN-indexed for traceability queries
  │
  └──── audit_entries (many, append-only)
            linked by (design_id, design_version)
```

---

## Database Trigger: Audit Entry Immutability

```sql
CREATE OR REPLACE FUNCTION deny_audit_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'audit_entries is append-only: UPDATE and DELETE are prohibited (ART-IX / FR-004)';
END;
$$;

CREATE TRIGGER audit_entries_immutable
    BEFORE UPDATE OR DELETE ON audit_entries
    FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation();
```

This trigger is created by the initial Alembic migration and must be present in every environment. Integration tests must verify it fires.
