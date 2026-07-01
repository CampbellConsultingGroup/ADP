# Quickstart: Requesting and Accepting Recommendations

**Branch**: `007-recommendation-engine` | **Date**: 2026-07-01  
**Prerequisites**: `ADP_LLM_*` env vars set; ADP-SPEC-005 knowledge base indexed; ADP running

---

## US1: Request Recommendations for Confirmed Requirements

```bash
# Submit recommendation request via Platform API (ADP-SPEC-003)
curl -X POST http://localhost:8000/api/v1/operations \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "recommendation",
    "design_id": "DESIGN-001",
    "parameters": {
      "requirement_ids": ["REQ-001", "REQ-002", "REQ-003"]
    }
  }'

# Immediate response (within 2 seconds):
# { "operation_id": "op-uuid", "kind": "recommendation", "status": "pending", ... }

# Poll until completed (60s for typical inputs):
curl -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  http://localhost:8000/api/v1/operations/op-uuid

# When complete:
# {
#   "status": "completed",
#   "result_summary": "3 options generated, 0 advisory",
#   "options": [
#     {
#       "option_id": "opt-001",
#       "rank": 1,
#       "title": "API Gateway with JWT Auth",
#       "rationale": "Reuses the existing gateway pattern with stateless auth...",
#       "advisory": false,
#       "grounded_on": [
#         {"item_id": "PAT-012", "item_version": "1.3.0"},
#         {"item_id": "STD-005", "item_version": "2.1.0"}
#       ],
#       "satisfies": ["REQ-001", "REQ-002"],
#       "trade_offs": [
#         {"criterion": "NFR-001", "stance": "meets", "rationale": "Gateway handles auth..."},
#         {"criterion": "Zero Trust", "stance": "meets", "rationale": "JWT validated at edge..."}
#       ],
#       "proposed_elements": [
#         {"name": "API Gateway", "kind": "container", "description": "...", "satisfies": ["REQ-001"]}
#       ],
#       "ranking_score": 0.87
#     }
#   ]
# }
```

---

## US3: Accept an Option to Materialize Elements

```bash
# Accept option opt-001 (explicit human action — ART-VIII)
curl -X POST http://localhost:8000/api/v1/operations/op-uuid/confirm \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "op-uuid",
    "option_id": "opt-001",
    "stated_intent": "Accepting API Gateway option for Order Processing design"
  }'

# Response:
# {
#   "operation_id": "op-uuid",
#   "option_id": "opt-001",
#   "confirmed_by": "sub:architect-123",
#   "confirmed_at": "2026-07-01T14:30:00Z",
#   "materialized_elements": ["ELM-004", "ELM-005"],
#   "audit_entry_id": "AUD-012"
# }

# Verify elements in design:
curl -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  http://localhost:8000/api/v1/designs/DESIGN-001

# Design now contains ELM-004 with provenance="opt-001" and satisfies=["REQ-001"]
```

---

## Advisory Options (FR-003)

When a citation cannot be resolved against the knowledge base:

```bash
# Result shows advisory=true for opt-003:
# { "option_id": "opt-003", "advisory": true, "rank": 3, ... }

# Accepting an advisory option requires explicit acknowledgment:
curl -X POST http://localhost:8000/api/v1/operations/op-uuid/confirm \
  -d '{
    "operation_id": "op-uuid",
    "option_id": "opt-003",
    "stated_intent": "Accepting advisory option; unresolved citation accepted with manual review",
    "advisory_acknowledged": true
  }'

# Materialized elements will carry advisory_provenance=true
```

---

## US4: What Each Step Span Contains

After a recommendation job, the telemetry pipeline (ADP-SPEC-012) contains 5 spans:

| Span Name | Key Attributes |
|---|---|
| `adp.recommendation.retrieve` | `retrieved_knowledge_refs`, `latency_ms` |
| `adp.recommendation.generate` | `input_tokens`, `output_tokens`, `cost_usd`, `option_count` |
| `adp.recommendation.analyze_tradeoffs` | `input_tokens`, `output_tokens`, `cost_usd` |
| `adp.recommendation.rank` | `latency_ms`, `cost_usd=0` |
| `adp.recommendation.validate_citations` | `advisory_count`, `latency_ms` |

All spans share `correlation_id` with the original API request.
