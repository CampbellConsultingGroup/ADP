# Data Model: AI Recommendation Engine

**Branch**: `007-recommendation-engine` | **Date**: 2026-07-01  
**Source**: `src/adp/recommendation/models.py`

---

## `TradeOffStance` (StrEnum)

| Value | Meaning |
|---|---|
| `meets` | Option fully addresses this criterion |
| `partially_meets` | Option partially addresses it; mitigation required |
| `does_not_meet` | Option cannot address this criterion |

---

## `TradeOffEntry`

One row in a `SolutionOption`'s trade-off assessment (FR-002).

| Field | Type | Notes |
|---|---|---|
| `criterion` | `str` | NFR id (e.g., `NFR-001`) or principle name (e.g., `"Stateless Services"`) |
| `stance` | `TradeOffStance` | The option's coverage of this criterion |
| `rationale` | `str` | One-sentence justification (max 200 chars) |

---

## `ProposedElement`

A partial element description embedded in a `SolutionOption`, converted to a canonical `Element` on acceptance.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Display name (max 120 chars) |
| `kind` | `ElementKind` | From ADP-SPEC-001: `person`, `system`, `container`, `component` |
| `description` | `str \| None` | Responsibility/purpose |
| `satisfies` | `list[RequirementId]` | Requirement ids this element addresses |

---

## `SolutionOption`

The primary output of the recommendation pipeline (FR-002). Stored transiently in the ADP-SPEC-003 operation store (TTL 24h).

| Field | Type | Required | Notes |
|---|---|---|---|
| `option_id` | `str` | Yes | UUID4; stable within the job's TTL |
| `operation_id` | `str` | Yes | Parent job's operation handle id |
| `rank` | `int` | Yes | 1 = highest; assigned by ranking step |
| `title` | `str` | Yes | Short option title (max 120 chars) |
| `rationale` | `str` | Yes | Why this option is recommended (max 500 chars) |
| `advisory` | `bool` | Yes | `True` if any citation failed validation (FR-003) |
| `grounded_on` | `list[CitationRef]` | Yes | Knowledge items cited; each carries `item_id` and `item_version` |
| `satisfies` | `list[str]` | Yes | Confirmed requirement ids this option addresses |
| `trade_offs` | `list[TradeOffEntry]` | Yes | One entry per applicable NFR and principle |
| `proposed_elements` | `list[ProposedElement]` | Yes | Elements the option would materialize |
| `ranking_score` | `float` | Yes | Composite weighted score (0–1) |
| `coverage_score` | `float` | Yes | Requirement coverage sub-score |
| `principle_score` | `float` | Yes | Principle alignment sub-score |
| `tradeoff_score` | `float` | Yes | NFR/principle trade-off sub-score |
| `status` | `str` | Yes | `pending` \| `accepted` \| `rejected` |
| `accepted_by` | `str \| None` | No | Principal ID of accepting architect |
| `accepted_at` | `datetime \| None` | No | UTC timestamp of acceptance |

---

## `RecommendationState` (LangGraph TypedDict)

The shared state threaded through all five pipeline steps. Never persisted; discarded after the pipeline completes.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | Operation handle id |
| `requirement_ids` | `list[str]` | Input confirmed requirement ids |
| `requirements` | `list[Requirement]` | Loaded from ADP-SPEC-002 design store |
| `retrieved_knowledge` | `list[RetrievalResultEntry]` | From ADP-SPEC-005 hybrid search |
| `candidate_options` | `list[SolutionOption]` | After generation step |
| `ranked_options` | `list[SolutionOption]` | After ranking step |
| `validated_options` | `list[SolutionOption]` | After citation validation |
| `correlation_id` | `str \| None` | From originating API request |
| `error` | `str \| None` | Set if any step fails |

---

## `RecommendationStep` (Telemetry)

One orchestration step's telemetry record (FR-006 / QG-11). Emitted regardless of success or failure.

| Field | Type | Notes |
|---|---|---|
| `operation_id` | `str` | Parent job id |
| `step_name` | `str` | `retrieve`, `generate`, `analyze_tradeoffs`, `rank`, `validate_citations` |
| `correlation_id` | `str \| None` | From API request |
| `retrieved_knowledge_refs` | `list[str]` | `item_id@version` strings |
| `input_tokens` | `int` | 0 for non-LLM steps |
| `output_tokens` | `int` | 0 for non-LLM steps |
| `cost_usd` | `float` | 0.0 for non-LLM steps |
| `latency_ms` | `float` | Step wall-clock time |
| `error` | `str \| None` | Error message if step failed |

---

## Pipeline State Machine

```
INPUT: requirement_ids, design_id, correlation_id
        │
        ▼
[Step 1: retrieve]
  KnowledgeRetrieval.hybrid_search() per requirement + merge
  → RecommendationState.retrieved_knowledge
  → emits span: step_name="retrieve", retrieved_knowledge_refs
        │
        ▼
[Step 2: generate]
  LLM call with requirements + knowledge summaries
  → 3 candidate SolutionOption records (with ProposedElements)
  → emits span: step_name="generate", input/output tokens, cost
        │
        ▼
[Step 3: analyze_tradeoffs]
  LLM call per option (may be batched)
  → TradeOffEntry list per option
  → emits span per batch: step_name="analyze_tradeoffs"
        │
        ▼
[Step 4: rank]
  Deterministic weighted-sum scoring
  → assigns rank integers (1 = best)
  → emits span: step_name="rank" (no LLM call; cost=0)
        │
        ▼
[Step 5: validate_citations]
  KnowledgeRetrieval.resolve_citation() per citation
  → marks options advisory=True if any citation unresolvable
  → emits span: step_name="validate_citations"
        │
        ▼
OUTPUT: ranked, validated SolutionOption list → stored in operation_store
        │
        ├── [architect accepts option_id] → materialize_option()
        │       ├── ProposedElement → Element (with provenance=option_id, satisfies=...)
        │       ├── AuditEntry written (ADP-SPEC-004)
        │       └── DesignStore.save() (ADP-SPEC-002)
        │
        └── [architect rejects / expires] → no model change
```

---

## Relationship to ADP-SPEC-001

When a `ProposedElement` is materialized:

| `ProposedElement` field | → `Element` field |
|---|---|
| `name` | `name` |
| `kind` | `kind` |
| `description` | `description` |
| `satisfies` | `satisfies` |
| `option_id` (from parent SolutionOption) | `provenance` |
| Assigned at materialization | `id` (new `ELM-NNN`) |
