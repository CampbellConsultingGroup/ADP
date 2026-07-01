# Contract: ValidationOrchestrator Python Interface

**Module**: `adp.validation`  
**Primary class**: `ValidationOrchestrator`  
**Consumers**: ADP-SPEC-003 operations router (when `kind=validation`)  
**Date**: 2026-07-01

Internal Python interface. All parameters and return types are typed.

---

## `ValidationOrchestrator`

```python
class ValidationOrchestrator:
    def __init__(
        self,
        llm_base_url: str,           # ADP_LLM_BASE_URL
        llm_api_key: str,            # ADP_LLM_API_KEY — NEVER logged
        llm_model: str,              # ADP_LLM_MODEL
        knowledge_retrieval: KnowledgeRetrieval,  # from ADP-SPEC-005
        design_store: DesignStore,   # from ADP-SPEC-002
        thresholds: GatingThreshold | None = None,  # defaults to v1 defaults
        telemetry: ValidationTelemetry | None = None,
    ) -> None: ...
```

### `run(operation_id, design_id, design_version?, operation_store, correlation_id?) → None` (async)

Execute the full validation pipeline as a background task. Stores `Verdict` in operation_store when complete.

**Steps**:
1. Load design from design_store (use current version if `design_version=None`)
2. Run structural check (pure Python)
3. If structural_passed=True: fan-out 4 LLM critics with `asyncio.gather()`
4. Aggregate findings and compute composite score
5. Apply deterministic gate → `Verdict.status`
6. Set `citations_present` on operation span
7. Store verdict in operation_store

**On failure**: Sets operation status to `failed`; emits failure telemetry; no verdict stored.

### `override_verdict(verdict_id, operation_id, reviewing_actor, justification, operation_store, design_id) → None` (async)

Override a failing verdict. Called by ADP-SPEC-003's confirmation router.

**Pre-conditions**:
- Verdict status is `fail` (raises `ValueError` if `pass`, `indeterminate`, or already `overridden`)
- `justification` is non-empty (raises `ValueError` if empty)

**Steps**:
1. Set `verdict.status = "overridden"`, `overridden_by`, `override_at`, `override_justification`
2. Write `AuditEntry` via ADP-SPEC-004 `write_audit_record()` with `action="override-validation-verdict"`
3. Call `design_store.save(design, actor=reviewing_actor)` with the updated audit log

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ADP_LLM_BASE_URL` | LLM endpoint base URL | Yes |
| `ADP_LLM_API_KEY` | API key — NEVER logged | Yes |
| `ADP_LLM_MODEL` | Model identifier | Yes |
| `ADP_VALIDATION_MAX_CRITICAL` | Gate threshold for critical findings | No (default 0) |
| `ADP_VALIDATION_MAX_MAJOR` | Gate threshold for major findings | No (default 3) |
| `ADP_VALIDATION_MAX_MINOR` | Gate threshold for minor findings | No (default 10) |

---

## Logging Contract (ART-VI / QG-10)

Per-job structured log:
```json
{
  "operation": "validation.pipeline",
  "operation_id": "...",
  "design_id": "...",
  "design_version": 3,
  "status": "fail",
  "composite_score": 0.72,
  "finding_count": 5,
  "citations_present": true
}
```

Fields NEVER logged: `api_key`, design content, finding descriptions containing element names.
