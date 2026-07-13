# Contract: RecommendationOrchestrator Python Interface

**Module**: `adp.recommendation`  
**Primary class**: `RecommendationOrchestrator`  
**Consumers**: ADP-SPEC-003 operations router (when `kind=recommendation`)  
**Date**: 2026-07-01

Internal Python interface. No HTTP surface. All parameters and return types are typed.

---

## `RecommendationOrchestrator`

```python
class RecommendationOrchestrator:
    def __init__(
        self,
        llm_base_url: str,           # ADP_LLM_BASE_URL
        llm_api_key: str,            # ADP_LLM_API_KEY — NEVER logged
        llm_model: str,              # ADP_LLM_MODEL
        knowledge_retrieval: KnowledgeRetrieval,  # from ADP-SPEC-005
        design_store: DesignStore,   # from ADP-SPEC-002
        option_count: int = 3,       # ADP_REC_OPTION_COUNT
        ranking_weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
        telemetry: RecommendationTelemetry | None = None,
    ) -> None: ...
```

### `run(operation_id, design_id, requirement_ids, operation_store, correlation_id?) → None` (async)

Execute the full five-step pipeline. Called as a background task by ADP-SPEC-003. Stores ranked `SolutionOption` list in `operation_store[operation_id]` when complete.

**Steps**: retrieve → generate → analyze_tradeoffs → rank → validate_citations

**On failure**: Sets operation status to `failed` with an error description; emits a failure span for the failing step; no options stored.

### `materialize_option(option_id, operation_id, accepting_actor, operation_store, design_id, *, advisory_acknowledged: bool = False) → list[Element]` (async)

Accept one `SolutionOption` and materialize its `ProposedElement` records as canonical `Element` and `Relationship` records in the design store.

**Pre-conditions** (enforced by caller):
- Operation status is `completed`
- Option `status == "pending"`
- `citations_present = True` OR advisory acknowledgment provided
- If `option.advisory == True` and `advisory_acknowledged == False` → raises `ValueError`; confirmation is blocked

**Steps**:
1. Load design from `DesignStore`
2. Convert each `ProposedElement` → `Element` with a new `ElementId`, `provenance=option_id`, `satisfies` from the option
3. Validate each element against ADP-SPEC-001 schema
4. Write `AuditEntry` via ADP-SPEC-004 `write_audit_record()`
5. Call `DesignStore.save(design, actor=accepting_actor)`
6. Mark option `status = accepted`
7. Return list of created `Element` records

**Raises**:
- `ValidationError` if any proposed element fails ADP-SPEC-001 schema
- `DesignNotFoundError` if design does not exist
- `ConcurrencyConflictError` (caller should re-read and retry)

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ADP_LLM_BASE_URL` | LLM endpoint | Yes |
| `ADP_LLM_API_KEY` | API key — NEVER logged | Yes |
| `ADP_LLM_MODEL` | Model identifier | Yes |
| `ADP_REC_OPTION_COUNT` | Number of candidates to generate (1–5) | No (default 3) |
| `ADP_REC_RANKING_WEIGHTS` | `"w_req,w_principle,w_tradeoff"` (comma-separated floats summing to 1.0) | No (default `"0.4,0.3,0.3"`) |
| `ADP_LLM_INPUT_COST_PER_1K` | For cost estimation in spans | No (default 0.0) |
| `ADP_LLM_OUTPUT_COST_PER_1K` | For cost estimation in spans | No (default 0.0) |

---

## Logging Contract (ART-VI / QG-10)

Per-job structured log:
```json
{
  "operation": "recommendation.pipeline",
  "operation_id": "...",
  "option_count": 3,
  "advisory_count": 0,
  "latency_ms": 18432,
  "status": "completed"
}
```

Fields NEVER logged: `api_key`, requirement descriptions, knowledge item full text, LLM prompts or responses.
