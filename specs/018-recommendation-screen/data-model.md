# Data Model: Architecture Recommendation Screen

**Branch**: `018-recommendation-screen` | **Date**: 2026-07-02

---

## Python API Models (Pydantic v2, `extra="forbid"`)

### `RecommendRequest`
Request body for `POST /api/v1/designs/{id}/recommend`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `requirement_ids` | `list[str]` | Yes | Must be non-empty; min 1 requirement |
| `model` | `str \| None` | No | Optional LLM model override; uses global config if absent |

### `RecommendStatusResponse`
Response from `GET /api/v1/designs/{id}/recommend/{operation_id}`.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | UUID of this recommendation run |
| `design_id` | `str` | |
| `status` | `str` | `"pending"\|"running"\|"completed"\|"failed"` |
| `options` | `list[SolutionOptionResponse]` | Empty until status=completed |
| `result_summary` | `str \| None` | e.g. "3 options generated" |
| `error_description` | `str \| None` | Set when status=failed |

### `TradeOffEntryResponse`

| Field | Type | Notes |
|---|---|---|
| `criterion` | `str` | NFR or principle being evaluated |
| `stance` | `str` | `"meets"\|"partially_meets"\|"does_not_meet"` |
| `rationale` | `str` | Why this stance was assigned |

### `ProposedElementResponse`

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Element name as it would appear on the canvas |
| `kind` | `str` | `"person"\|"system"\|"container"\|"component"` |
| `description` | `str \| None` | Optional element description |
| `satisfies` | `list[str]` | Requirement IDs this element satisfies |

### `SolutionOptionResponse`
One ranked option returned in the status response.

| Field | Type | Notes |
|---|---|---|
| `option_id` | `str` | UUID |
| `rank` | `int` | 1 = best; lower is better |
| `title` | `str` | Short option name |
| `rationale` | `str` | Why this option was recommended |
| `advisory` | `bool` | True if grounding citations are incomplete (ART-VII) |
| `satisfies` | `list[str]` | Requirement IDs addressed |
| `trade_offs` | `list[TradeOffEntryResponse]` | Criterion analysis |
| `proposed_elements` | `list[ProposedElementResponse]` | C4 elements to be created on accept |
| `grounded_on` | `list[str]` | Knowledge item IDs cited |
| `ranking_score` | `float` | Overall score 0.0–1.0 |
| `status` | `str` | `"pending"\|"accepted"` |

### `AcceptOptionRequest`
Request body for `POST /api/v1/designs/{id}/recommend/{op_id}/options/{option_id}/accept`.

| Field | Type | Notes |
|---|---|---|
| `confirmation_id` | `str` | Non-empty string; ART-VIII gate (same pattern as export) |
| `advisory_acknowledged` | `bool` | Required to be `True` when option.advisory is True |

### `ElementSummaryResponse`
One created element in the accept response.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | e.g. "ELM-005" |
| `name` | `str` | |
| `kind` | `str` | |

### `AcceptOptionResponse`
Response from accept endpoint.

| Field | Type | Notes |
|---|---|---|
| `option_id` | `str` | |
| `elements_created` | `list[ElementSummaryResponse]` | Elements added to the design |
| `audit_entry_id` | `str` | AUD-NNN ID of the acceptance audit entry |

---

## TypeScript Interfaces (`web/src/api/recommend.ts`)

```typescript
export type RecommendStatus = "pending" | "running" | "completed" | "failed";
export type OptionStatus = "pending" | "accepted";
export type TradeOffStance = "meets" | "partially_meets" | "does_not_meet";

export interface RecommendRequest {
  requirement_ids: string[];
  model?: string;
}

export interface TradeOffEntry {
  criterion: string;
  stance: TradeOffStance;
  rationale: string;
}

export interface ProposedElement {
  name: string;
  kind: string;
  description?: string | null;
  satisfies: string[];
}

export interface SolutionOption {
  option_id: string;
  rank: number;
  title: string;
  rationale: string;
  advisory: boolean;
  satisfies: string[];
  trade_offs: TradeOffEntry[];
  proposed_elements: ProposedElement[];
  grounded_on: string[];
  ranking_score: number;
  status: OptionStatus;
}

export interface RecommendStatusResponse {
  operation_id: string;
  design_id: string;
  status: RecommendStatus;
  options: SolutionOption[];
  result_summary?: string | null;
  error_description?: string | null;
}

export interface AcceptOptionRequest {
  confirmation_id: string;
  advisory_acknowledged: boolean;
}

export interface ElementSummary {
  id: string;
  name: string;
  kind: string;
}

export interface AcceptOptionResponse {
  option_id: string;
  elements_created: ElementSummary[];
  audit_entry_id: string;
}
```

---

## Operation Store Entry

```python
# _recommend_store[operation_id] = {
#   "status": "pending"|"running"|"completed"|"failed",
#   "design_id": str,
#   "requirement_ids": list[str],
#   "options": dict[option_id, SolutionOption],   # set by orchestrator
#   "result_summary": str | None,
#   "error_description": str | None,
#   "correlation_id": str,
#   "created_at": datetime,
# }
```

---

## State Machine: Option Status

```
PENDING ──accept (with confirmation)──► ACCEPTED
```

ACCEPTED is terminal. Attempting to accept an already-accepted option returns 409.

---

## ProposedElement → Element Mapping (via materialize_option)

| ProposedElement field | Element field |
|---|---|
| `name` | `name` |
| `kind` | `kind` |
| `description` | `description` |
| `satisfies` | `satisfies` |
| `option_id` | `provenance` (ART-XI traceability) |
| auto-generated | `id` (ELM-NNN, next available) |
