# Contract: LLM Prompt & Response Schema

**Module**: `adp.intake.llm`  
**Date**: 2026-07-01

The extraction prompt instructs the LLM to extract typed requirements from source text and return structured JSON. This contract is the LLM-facing boundary — any change to it constitutes a breaking change to the extraction pipeline.

---

## System Prompt (version 1.0)

```text
You are a requirements analyst. Extract all business requirements from the provided text.

For each requirement you identify, return a JSON object with these exact fields:
- "statement": A clear, testable requirement statement (rewritten in imperative form if needed)
- "kind": One of "functional", "non-functional", "constraint", or "driver"
- "source_excerpt": The exact verbatim phrase or sentence from the source text that this 
  requirement derives from (must be a substring of the input)
- "confidence": A float 0.0–1.0 indicating your confidence this is a genuine requirement
- "referenced_principles": A list of named principles, standards, or capabilities explicitly 
  mentioned in the source text related to this requirement (empty list if none)

Return ONLY a JSON object with a single key "requirements" containing a list of requirement objects.
Do not include any text outside the JSON.
If no requirements are found, return {"requirements": []}.
```

---

## User Prompt Template

```text
Extract all requirements from the following text:

---
{source_text}
---
```

Where `{source_text}` is the architect's submitted text (plain text or Markdown, max 20,000 characters).

---

## Expected JSON Response

```json
{
  "requirements": [
    {
      "statement": "The API gateway must authenticate all requests before routing them to backend services.",
      "kind": "functional",
      "source_excerpt": "All API requests must be authenticated before reaching any service",
      "confidence": 0.95,
      "referenced_principles": ["Zero Trust Architecture"]
    },
    {
      "statement": "The system must respond to 95% of requests within 200 milliseconds.",
      "kind": "non-functional",
      "source_excerpt": "response times should stay under 200ms for 95th percentile",
      "confidence": 0.88,
      "referenced_principles": []
    }
  ]
}
```

---

## Request Parameters

```json
{
  "model": "{ADP_LLM_MODEL}",
  "messages": [
    {"role": "system", "content": "{system_prompt}"},
    {"role": "user",   "content": "{user_prompt}"}
  ],
  "response_format": {
    "type": "json_object"
  },
  "temperature": 0.1,
  "max_tokens": 4096
}
```

`temperature: 0.1` for consistency across runs (determinism matters for testability).  
`response_format: json_object` — use `json_schema` with the full schema if the endpoint supports it.

---

## Parse Failure Handling

If the LLM response:
- Cannot be parsed as JSON → `ExtractionJob.status = failed`; error logged; no proposals stored
- Is valid JSON but missing `requirements` key → treated as `{"requirements": []}` (zero proposals)
- Contains a proposal missing required fields → that proposal is skipped; others are kept

---

## Prompt Version Tracking

| Version | Change | Date |
|---|---|---|
| 1.0 | Initial prompt | 2026-07-01 |

Breaking changes to the prompt require incrementing the version and noting it in the span's `prompt_version` attribute.
