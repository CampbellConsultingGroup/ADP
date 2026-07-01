# Contract: LLM Critic Prompt Schemas

**Module**: `adp.validation.prompts`  
**Date**: 2026-07-01

Four LLM critic prompts (structural critic uses no LLM). Each produces scored findings.

---

## Common Response Schema

All critics return the same JSON structure:
```json
{
  "score": 0.0-1.0,
  "findings": [
    {
      "element_id": "ELM-001 or null for design-level",
      "description": "Human-readable finding description",
      "cited_id": "knowledge item id from the provided list"
    }
  ]
}
```

Return ONLY this JSON. If no issues found, return `{"score": 1.0, "findings": []}`.

---

## Scoring Rubric (included in ALL critic system prompts)

```text
Score 1.0: Fully compliant — no deviations from applicable standards/principles/patterns
Score 0.75: Minor deviation — one non-critical issue with mitigatable risk
Score 0.5: Significant gap — one major issue requiring review
Score 0.25: Multiple gaps — two or more major issues
Score 0.0: Clear violation — explicit non-compliance with at least one mandatory item, cited
```

---

## Standards Critic Prompt (version 1.0)

**System**:
```text
You are an architecture standards compliance reviewer.
Evaluate the provided design elements against the applicable organizational standards.
[Scoring rubric above]

For each non-compliance, identify the element, describe the issue, and cite the standard id.
Return ONLY the JSON schema. "cited_id" must be an id from the provided standards list.
```

**User**:
```text
DESIGN ELEMENTS:
{elements_summary}

APPLICABLE STANDARDS:
{standards_knowledge_summary}

Evaluate compliance with each standard.
```

---

## Principles Critic Prompt (version 1.0)

**System**: Same structure as standards; judges against architecture principles.

**User**: Same structure; `{principles_knowledge_summary}` contains principle items.

---

## Pattern-Fit Critic Prompt (version 1.0)

**System**: Evaluates whether the design appropriately applies retrieved patterns.

**User**:
```text
DESIGN ELEMENTS:
{elements_summary}

RELEVANT PATTERNS:
{patterns_knowledge_summary}

Evaluate how well the design applies or deviates from these patterns.
```

---

## Consistency Critic Prompt (version 1.0)

**System**: Evaluates whether the design is consistent with prior approved solutions.

**User**:
```text
DESIGN ELEMENTS:
{elements_summary}

PRIOR APPROVED SOLUTIONS:
{prior_solutions_summary}

Identify significant inconsistencies with prior solutions without justification.
```

---

## Severity Mapping

| Score | Severity assigned to all findings in this response |
|---|---|
| 0.0 | `critical` |
| 0.25 | `major` |
| 0.5 | `major` |
| 0.75 | `minor` |
| 1.0 | (no findings) |

Score → severity mapping is deterministic (not LLM-generated). The LLM only produces a score and finding descriptions; severity is inferred by the aggregator.

---

## Parse Failure Handling

- Response cannot be parsed as JSON → `CriticOutput.error` set; `score=None`; findings excluded from aggregation; critic counts as failed-to-run for composite score
- `cited_id` not in provided knowledge list → finding marked `advisory=True` (citation unresolvable); does NOT count toward blocking thresholds
- Score outside 0–1 → clamped to [0, 1]
