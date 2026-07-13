# Contract: LLM Prompt Schemas

**Module**: `adp.recommendation.prompts`  
**Date**: 2026-07-01

Two LLM prompt schemas — one for option generation, one for trade-off analysis.

---

## Generation Prompt (version 1.0)

### System Prompt

```text
You are an enterprise architecture advisor. Given a set of confirmed requirements and relevant 
organizational knowledge, generate {option_count} distinct candidate solution options.

For each option, return a JSON object with:
- "title": A concise option label (max 80 chars)
- "rationale": Why this option is appropriate (max 400 chars)
- "grounded_on": List of knowledge item IDs cited (must be ids from the provided knowledge list)
- "satisfies": List of requirement ids this option addresses
- "proposed_elements": List of elements this option would materialize, each with:
    - "name": element name
    - "kind": one of "person", "system", "container", "component"
    - "description": responsibility
    - "satisfies": which requirement ids this element addresses

Return ONLY a JSON object: {"options": [...]}. Options must use different approaches.
Each option MUST cite at least one knowledge item from the provided list.
```

### User Prompt Template

```text
REQUIREMENTS:
{requirements_list}

RELEVANT KNOWLEDGE:
{knowledge_summary}

Generate {option_count} distinct solution options that address these requirements.
```

**`{knowledge_summary}` format**: One line per item — `[{item_id}@{version}] {kind}: "{title}" — {excerpt}`

---

## Trade-off Analysis Prompt (version 1.0)

### System Prompt

```text
You are an enterprise architecture reviewer. Analyze how well the given solution option 
addresses each of the provided non-functional requirements and architecture principles.

For each criterion, return:
- "criterion": the NFR id or principle name (exactly as provided)
- "stance": one of "meets", "partially_meets", "does_not_meet"
- "rationale": one sentence justification (max 200 chars)

Return ONLY a JSON object: {"trade_offs": [...]}.
Be explicit about weaknesses — "does_not_meet" should appear when appropriate.
```

### User Prompt Template

```text
OPTION: {option_title}
RATIONALE: {option_rationale}
PROPOSED ELEMENTS: {element_names}

CRITERIA TO ASSESS:
{criteria_list}

Assess this option against each criterion.
```

---

## Parse Failure Handling

- **Generation**: If response cannot be parsed as valid JSON with `options` key → job fails; no options stored
- **Generation**: If an option's `grounded_on` list references an id not in the provided knowledge list → that citation is removed; if no citations remain → option marked `advisory=True` after citation validation step
- **Trade-off**: If response cannot be parsed → trade-offs for that option default to empty list; option is surfaced with a warning; job does NOT fail

---

## Prompt Version Tracking

| Prompt | Version | Change | Date |
|---|---|---|---|
| Generation | 1.0 | Initial | 2026-07-01 |
| Trade-off | 1.0 | Initial | 2026-07-01 |
