# Quickstart: Submitting and Confirming Requirements

**Branch**: `006-requirements-intake` | **Date**: 2026-07-01  
**Prerequisites**: `ADP_LLM_BASE_URL`, `ADP_LLM_API_KEY`, `ADP_LLM_MODEL` set; ADP-SPEC-003 API running

---

## US1: Submit Requirements for Extraction

```bash
# Submit bulk text via the Platform API (ADP-SPEC-003)
curl -X POST http://localhost:8000/api/v1/operations \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "intake",
    "design_id": "DESIGN-001",
    "parameters": {
      "mode": "bulk_text",
      "text": "The system must authenticate all API requests before routing them to backend services. Response times should stay under 200ms for 95th percentile. We must follow the Zero Trust Architecture principle throughout. The platform must support 10,000 concurrent users."
    }
  }'

# Response (immediate — within 2 seconds):
# {
#   "operation_id": "op-uuid",
#   "kind": "intake",
#   "status": "pending",
#   "design_id": "DESIGN-001",
#   "confirmed": false,
#   "expires_at": "2026-07-02T12:00:00Z"
# }
```

---

## US1: Poll for Extraction Results

```bash
# Poll every few seconds until status = "completed"
curl -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  http://localhost:8000/api/v1/operations/op-uuid

# When complete:
# {
#   "status": "completed",
#   "result_summary": "4 requirements extracted",
#   "proposals": [
#     {
#       "proposal_id": "prop-001",
#       "draft_statement": "The API gateway must authenticate all requests before routing to backend services.",
#       "kind": "functional",
#       "source_excerpt": "authenticate all API requests before routing them to backend services",
#       "verification_status": "verified",
#       "confidence": 0.95,
#       "proposed_links": ["PR-001"],
#       "status": "pending"
#     },
#     ...
#   ]
# }
```

---

## US2: Confirm a Proposal

```bash
# Confirm proposal prop-001 as-is
curl -X POST http://localhost:8000/api/v1/operations/op-uuid/confirm \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "op-uuid",
    "proposal_id": "prop-001",
    "stated_intent": "Confirming authentication requirement for API gateway"
  }'

# Response:
# {
#   "operation_id": "op-uuid",
#   "proposal_id": "prop-001",
#   "confirmed_by": "sub:architect-123",
#   "confirmed_at": "2026-07-01T12:05:00Z",
#   "requirement_id": "REQ-042",
#   "audit_entry_id": "AUD-088"
# }
```

---

## US2: Edit Statement Before Confirming

```bash
# Confirm with an edited statement
curl -X POST http://localhost:8000/api/v1/operations/op-uuid/confirm \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "op-uuid",
    "proposal_id": "prop-002",
    "stated_intent": "Confirming latency requirement with clarified metric",
    "edited_statement": "95% of API responses must complete within 200 milliseconds under normal load."
  }'
```

---

## US2: Reject a Proposal

```bash
# Reject prop-003 (determined not to be a genuine requirement)
curl -X POST http://localhost:8000/api/v1/operations/op-uuid/reject \
  -H "Authorization: Bearer $ARCHITECT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation_id": "op-uuid",
    "proposal_id": "prop-003",
    "reason": "This is a design decision, not a requirement."
  }'
```

---

## US3: Proposals with Knowledge Base Links

When the LLM identifies "Zero Trust Architecture" in the source text and the knowledge base contains a principle matching that name, the proposal includes it:

```json
{
  "proposal_id": "prop-004",
  "draft_statement": "The platform must implement Zero Trust Architecture principles for all service-to-service communication.",
  "kind": "constraint",
  "source_excerpt": "must follow the Zero Trust Architecture principle throughout",
  "verification_status": "verified",
  "confidence": 0.91,
  "proposed_links": ["PR-007"],   ← resolved from knowledge base
  "status": "pending"
}
```

Confirming this proposal creates a `Requirement` with `provenance` referencing `PR-007`.

---

## What Gets Rejected or Flagged

| Scenario | Behavior |
|---|---|
| LLM endpoint unreachable | `OperationHandle.status = failed`; span emitted with error |
| LLM returns malformed JSON | Operation fails; no proposals stored |
| Proposal source_excerpt not found in source | Proposal marked `verification_status: unverified`; presented with warning |
| Unconfirmed proposal after 24h TTL | Status auto-set to `expired`; not entered into model |
| Confirmation without `proposal_id` | 422 Validation error |
