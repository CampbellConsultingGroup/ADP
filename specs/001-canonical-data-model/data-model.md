# Data Model: Canonical Data Model & Schema Generation

**Branch**: `001-canonical-data-model` | **Date**: 2026-06-27  
**Source**: `src/adp/models.py` (Pydantic v2 — the authoritative definition per ART-II)

---

## Identifier Types

All entity identifiers are string aliases validated by regex at parse time. Unknown or malformed IDs are rejected with a validation error.

| Type Alias | Pattern | Example |
|---|---|---|
| `RequirementId` | `^REQ-\d{3}$` | `REQ-001` |
| `ElementId` | `^ELM-\d{3}$` | `ELM-002` |
| `RelationshipId` | `^REL-\d{3}$` | `REL-001` |
| `OptionId` | `^OPT-\d{3}$` | `OPT-001` |
| `FindingId` | `^FND-\d{3}$` | `FND-003` |
| `VerdictId` | `^VRD-\d{3}$` | `VRD-001` |
| `AuditEntryId` | `^AUD-\d{3}$` | `AUD-007` |

---

## Enumerations

### `ElementKind`

Closed enum for C4 structural element types. Stops at component level (v1 scope, see research.md Decision 1).

| Value | C4 Level | Description |
|---|---|---|
| `person` | Level 1 | A human user or role that interacts with the system |
| `system` | Level 1 | A software system (the subject of or a dependency in the description) |
| `container` | Level 2 | A deployable unit within a system (app, service, database, store) |
| `component` | Level 3 | A named, bounded component within a container |

### `VerdictStatus`

The decision state of a `SolutionOption`.

| Value | Meaning |
|---|---|
| `pending` | Under evaluation; no decision recorded |
| `accepted` | Option selected; becomes the recommended approach |
| `rejected` | Option ruled out; rationale recorded |
| `deferred` | Decision postponed; conditions for revisiting recorded |

---

## Entities

All entities set `extra="forbid"` — unknown fields cause a validation error at parse time (FR-002).

---

### `Requirement`

A single design requirement that drives the architecture. Starting point of every traceability chain.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `RequirementId` | Yes | Pattern `REQ-\d{3}` | Unique within a description |
| `title` | `str` | Yes | Non-empty, ≤ 120 chars | Short human-readable label |
| `description` | `str` | Yes | Non-empty | Full requirement statement |
| `priority` | `str` | No | One of: `must`, `should`, `may` | RFC-2119 level |
| `tags` | `list[str]` | No | Default `[]` | Grouping/filtering labels |

---

### `Element`

A C4 structural element. Carries traceability fields linking it to the requirements it satisfies.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `ElementId` | Yes | Pattern `ELM-\d{3}` | Unique within a description |
| `name` | `str` | Yes | Non-empty, ≤ 120 chars | Display name |
| `kind` | `ElementKind` | Yes | Closed enum | C4 level |
| `description` | `str` | No | — | Responsibility/purpose statement |
| `satisfies` | `list[RequirementId]` | No | Default `[]` | Requirements this element addresses; each ID MUST resolve (FR-007 / ART-XI) |
| `provenance` | `str \| None` | No | — | Origin of this element (human or AI recommendation ID) |
| `tags` | `list[str]` | No | Default `[]` | — |

**Referential integrity**: Every `RequirementId` in `satisfies` MUST exist in the parent `ArchitectureDescription.requirements`.

---

### `Relationship`

A directed link between two elements.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `RelationshipId` | Yes | Pattern `REL-\d{3}` | Unique within a description |
| `source` | `ElementId` | Yes | — | Source element; MUST resolve |
| `target` | `ElementId` | Yes | — | Target element; MUST resolve |
| `label` | `str` | No | ≤ 80 chars | Description of the interaction |
| `technology` | `str` | No | ≤ 80 chars | e.g., "HTTPS", "gRPC", "event" |

**Referential integrity**: Both `source` and `target` MUST exist in the parent `ArchitectureDescription.elements`.

---

### `SolutionOption`

A candidate recommendation option under consideration for a design decision.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `OptionId` | Yes | Pattern `OPT-\d{3}` | Unique within a description |
| `title` | `str` | Yes | Non-empty, ≤ 120 chars | Short option label |
| `description` | `str` | Yes | Non-empty | What this option proposes |
| `status` | `VerdictStatus` | Yes | Closed enum | Current decision state |
| `satisfies` | `list[RequirementId]` | No | Default `[]` | Requirements this option addresses; each MUST resolve |
| `provenance` | `str \| None` | No | — | Origin (human or AI recommendation ID) |

**Referential integrity**: Every `RequirementId` in `satisfies` MUST exist in the parent `ArchitectureDescription.requirements`.

---

### `Finding`

An audit or review observation attached to an element or option.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `FindingId` | Yes | Pattern `FND-\d{3}` | Unique within a description |
| `subject` | `ElementId \| OptionId` | Yes | — | The entity this finding concerns; MUST resolve |
| `summary` | `str` | Yes | Non-empty, ≤ 240 chars | One-line observation |
| `detail` | `str` | No | — | Expanded reasoning |
| `severity` | `str` | No | One of: `info`, `warning`, `critical` | Default `info` |
| `source` | `str` | No | — | Review step or human actor that raised this |

**Referential integrity**: `subject` MUST resolve to an ID present in either `ArchitectureDescription.elements` or `ArchitectureDescription.options`.

---

### `Verdict`

A recorded decision on a `SolutionOption`. Closes the traceability chain: requirement → element → option → verdict.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `VerdictId` | Yes | Pattern `VRD-\d{3}` | Unique within a description |
| `option_id` | `OptionId` | Yes | — | The option decided upon; MUST resolve |
| `status` | `VerdictStatus` | Yes | Closed enum | Must match or supersede the option's status |
| `rationale` | `str` | Yes | Non-empty | Justification for the decision |
| `decided_by` | `str` | Yes | Non-empty | Actor (human name or role) who made the decision |
| `decided_at` | `datetime` | Yes | ISO 8601 | Timestamp of the decision |
| `provenance` | `str \| None` | No | — | Links to the AI recommendation or session that produced this verdict |

**Referential integrity**: `option_id` MUST exist in the parent `ArchitectureDescription.options`.

---

### `AuditEntry`

An immutable record of a mutation to the `ArchitectureDescription`. Append-only; entries MUST NOT be edited or deleted (ART-IX).

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `AuditEntryId` | Yes | Pattern `AUD-\d{3}` | Unique within a description; ordered by creation |
| `actor` | `str` | Yes | Non-empty | Human user ID or system step name |
| `action` | `str` | Yes | Non-empty | e.g., "add-element", "accept-verdict" |
| `affected_entity` | `str` | Yes | Non-empty | ID of the mutated entity |
| `summary` | `str` | Yes | Non-empty, ≤ 240 chars | What changed |
| `timestamp` | `datetime` | Yes | ISO 8601 | When the mutation occurred |
| `origin` | `str` | Yes | One of: `human`, `ai` | Whether a human or AI step produced this mutation |

---

### `ArchitectureDescription` (Aggregate Root)

The top-level container; the unit of serialization, validation, and schema conformance. All referential integrity checks are enforced here via a model validator that runs after construction.

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `schema_version` | `str` | Yes | Semver format `\d+\.\d+\.\d+` | Embedded schema version (ART-XV) |
| `id` | `str` | Yes | Non-empty | Unique design identifier (not entity-typed) |
| `title` | `str` | Yes | Non-empty, ≤ 200 chars | Human-readable design name |
| `description` | `str` | No | — | Scope and context statement |
| `requirements` | `list[Requirement]` | No | Default `[]` | Unique IDs enforced by validator |
| `elements` | `list[Element]` | No | Default `[]` | Unique IDs enforced by validator |
| `relationships` | `list[Relationship]` | No | Default `[]` | Unique IDs enforced by validator |
| `options` | `list[SolutionOption]` | No | Default `[]` | Unique IDs enforced by validator |
| `findings` | `list[Finding]` | No | Default `[]` | Unique IDs enforced by validator |
| `verdicts` | `list[Verdict]` | No | Default `[]` | Unique IDs enforced by validator |
| `audit_log` | `list[AuditEntry]` | No | Default `[]` | Append-only; unique IDs enforced by validator |
| `created_at` | `datetime` | Yes | ISO 8601 | — |
| `updated_at` | `datetime` | Yes | ISO 8601 | MUST be >= `created_at` |

**Model validator (after)** performs:
1. Duplicate ID detection within each entity list
2. Reference resolution for all `satisfies`, `source`, `target`, `subject`, `option_id`, and `affected_entity` fields

---

## Entity Relationship Summary

```
ArchitectureDescription (root)
│
├── requirements[]      ←── ElementId, OptionId, AuditEntry: satisfies/references
│
├── elements[]          ──► satisfies → requirements[].id
│
├── relationships[]     ──► source, target → elements[].id
│
├── options[]           ──► satisfies → requirements[].id
│
├── findings[]          ──► subject → elements[].id  OR  options[].id
│
├── verdicts[]          ──► option_id → options[].id
│
└── audit_log[]         (append-only; affected_entity references any entity ID)
```

The requirement → element → option → verdict traceability thread (FR-007 / ART-XI):
```
Requirement ← satisfies ── Element
Requirement ← satisfies ── SolutionOption ──► Verdict
```
