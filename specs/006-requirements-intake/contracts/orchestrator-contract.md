# Contract: ExtractionOrchestrator Python Interface

**Module**: `adp.intake`  
**Primary class**: `ExtractionOrchestrator`  
**Consumers**: ADP-SPEC-003 operations router (when `kind=intake`)  
**Date**: 2026-07-01

Internal Python interface. No HTTP surface. All parameters and return types are typed.

---

## `ExtractionOrchestrator`

```python
class ExtractionOrchestrator:
    def __init__(
        self,
        llm_base_url: str,           # ADP_LLM_BASE_URL
        llm_api_key: str,            # ADP_LLM_API_KEY — NEVER logged
        llm_model: str,              # ADP_LLM_MODEL
        input_cost_per_1k: float,    # ADP_LLM_INPUT_COST_PER_1K
        output_cost_per_1k: float,   # ADP_LLM_OUTPUT_COST_PER_1K
        link_confidence_threshold: float = 0.7,  # ADP_LINK_CONFIDENCE_THRESHOLD
        knowledge_retrieval=None,    # KnowledgeRetrieval from ADP-SPEC-005 (optional)
        telemetry_exporter=None,     # OTel SpanExporter (None in dev; configured by ADP-SPEC-012)
    ) -> None: ...
```

### `run(submission: IntakeSubmission, operation_store: dict) -> None` (async)

Execute the full extraction pipeline for one submission. Called as a background task by ADP-SPEC-003. Updates the operation store with proposals when complete.

**Steps**:
1. Create telemetry span (context manager)
2. Call `LLMClient.extract()` → raw JSON
3. Call `LLMResponseParser.parse()` → `list[ExtractedProposal]`
4. For each proposal: call `SourceExcerptVerifier.verify()` → set `verification_status`
5. If `knowledge_retrieval` configured: call `KnowledgeLinker.link()` → set `proposed_links`
6. Store proposals in `operation_store[operation_id].proposals`
7. Close span with all required attributes (QG-11)
8. Update `OperationHandle.status = completed` (or `failed` on exception)

**On failure**: Stores error in `OperationHandle.error_description`; emits span with `error` field; operation status set to `failed`; no proposals stored.

### `confirm_proposal(proposal_id: str, operation_id: str, confirming_actor: str, edited_statement: str | None, operation_store: dict, design_store: DesignStore) -> Requirement` (async)

Confirm one proposal. Called by ADP-SPEC-003's confirmation router.

**Pre-conditions** (enforced by caller):
- `OperationHandle.status == completed`
- Proposal `status == pending`
- `citations_present = True` (ART-VII: source excerpt must exist)

**Steps**:
1. Mark proposal `status = confirmed` (or `edited_confirmed` if `edited_statement` is set)
2. Set `confirmed_by`, `confirmed_at`
3. Build `AuditRecord` and call `write_audit_record()` (ADP-SPEC-004)
4. Build `Requirement` from the confirmed proposal
5. Append to design's `requirements` list and call `design_store.save()`
6. Set `proposal.requirement_id` to the new `Requirement.id`
7. Return the created `Requirement`

### `reject_proposal(proposal_id: str, operation_id: str, rejecting_actor: str, operation_store: dict) -> None` (async)

Mark a proposal as rejected. Writes a rejection audit entry. Proposal is NOT committed to the model.

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ADP_LLM_BASE_URL` | LLM endpoint base URL (e.g., `https://api.openai.com`) | Yes |
| `ADP_LLM_API_KEY` | API key for the LLM endpoint — NEVER logged | Yes |
| `ADP_LLM_MODEL` | Model identifier (e.g., `gpt-4o`, `llama3.1`) | Yes |
| `ADP_LLM_INPUT_COST_PER_1K` | Cost per 1k input tokens in USD | No (default 0.0) |
| `ADP_LLM_OUTPUT_COST_PER_1K` | Cost per 1k output tokens in USD | No (default 0.0) |
| `ADP_LINK_CONFIDENCE_THRESHOLD` | Minimum confidence for knowledge base links | No (default 0.7) |

All variables externalized (QG-08). `ADP_LLM_API_KEY` is NEVER logged, included in spans, or stored.

---

## Logging Contract (ART-VI / QG-10)

Per-job structured log:
```json
{
  "operation": "intake.extraction",
  "operation_id": "...",
  "proposal_count": 5,
  "latency_ms": 3421,
  "model": "gpt-4o",
  "error": null
}
```

Fields NEVER logged: `api_key`, `source_text`, `draft_statement`, any requirement content.
