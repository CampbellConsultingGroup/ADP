# Quickstart: Running and Reviewing Validation

**Branch**: `008-llm-as-judge` | **Date**: 2026-07-01  
**Prerequisites**: `ADP_LLM_*` env vars set; ADP-SPEC-005 knowledge base indexed; ADP running

---

## US1 + US2: Submit a Design for Validation

```bash
# Submit validation request
curl -X POST http://localhost:8000/api/v1/operations \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "validation",
    "design_id": "DESIGN-001",
    "parameters": {}
  }'
# → { "operation_id": "op-uuid", "status": "pending", ... }

# Poll until completed (≤ 120 seconds for typical designs)
curl -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  http://localhost:8000/api/v1/operations/op-uuid

# When complete (fail example):
# {
#   "status": "completed",
#   "result_summary": "FAIL — 2 critical, 1 major, 3 minor findings",
#   "verdict": {
#     "verdict_id": "vrd-uuid",
#     "status": "fail",
#     "composite_score": 0.61,
#     "design_version": 3,
#     "findings": [
#       {
#         "finding_id": "fnd-001",
#         "critic_name": "standards",
#         "element_id": "ELM-002",
#         "severity": "critical",
#         "description": "Element does not implement TLS 1.3 as required",
#         "citation": {"item_id": "STD-005", "item_version": "2.1.0"}
#       },
#       {
#         "finding_id": "fnd-002",
#         "critic_name": "structural",
#         "element_id": "ELM-004",
#         "severity": "critical",
#         "description": "Orphan element — no satisfied requirement",
#         "citation": null
#       }
#     ],
#     "thresholds_snapshot": {"max_critical": 0, "max_major": 3, "max_minor": 10},
#     "citations_present": true
#   }
# }
```

---

## US3: Structural Failure (Orphan Element)

When a design has an orphan element, the structural critic returns an immediate fail:

```json
{
  "critic_name": "structural",
  "element_id": "ELM-004",
  "severity": "critical",
  "description": "Orphan element — satisfies list is empty; no requirement satisfied",
  "citation": null
}
```

The LLM critics are skipped in this case.

---

## US4: Override a Failing Verdict

```bash
# Override requires explicit justification
curl -X POST http://localhost:8000/api/v1/operations/op-uuid/confirm \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "op-uuid",
    "stated_intent": "Accepting this design under exception EXC-2026-003; TLS deviation documented in ADR-042",
    "verdict_override": true
  }'

# Response:
# {
#   "operation_id": "op-uuid",
#   "confirmed_by": "sub:reviewer-456",
#   "confirmed_at": "2026-07-01T16:30:00Z",
#   "audit_entry_id": "AUD-089",
#   "verdict_status": "overridden"
# }

# Attempting override without justification → 422 error:
# { "error_code": "VALIDATION_ERROR", "message": "stated_intent is required for verdict override" }
```

---

## What Gets Blocked vs. Advisory

| Finding type | Advisory? | Counts toward gate? |
|---|---|---|
| Finding with verified citation | No | Yes |
| Finding where cited_id not in knowledge base | **Yes (advisory)** | **No** |
| Structural finding (orphan/dangling) | No | Yes — always `critical` |

---

## Verdict Status Transitions

```
validation runs → "pass"
validation runs → "fail" → reviewer overrides → "overridden"
validation runs → "indeterminate" → must re-run; cannot be overridden
```
