"""LLM prompt templates for recommendation generation and trade-off analysis."""

from __future__ import annotations

GENERATION_SYSTEM_PROMPT = """\
You are an enterprise architecture advisor. Given confirmed requirements and relevant \
organizational knowledge, generate {option_count} distinct candidate solution options.

For each option return a JSON object with:
- "title": concise label (max 80 chars)
- "rationale": why this option is appropriate (max 400 chars)
- "grounded_on": list of knowledge item IDs cited (must be ids from the provided knowledge list)
- "satisfies": list of requirement ids this option addresses
- "proposed_elements": list of elements this option would materialize, each with:
    "name", "kind" (one of: person, system, container, component), "description", "satisfies"

Return ONLY: {{"options": [...]}}. Options must use different approaches.
Each option MUST cite at least one knowledge item from the provided list.
Truncate to exactly {option_count} options.\
"""


def generation_user_prompt(
    requirements_list: str,
    knowledge_summary: str,
    option_count: int,
) -> str:
    return (
        f"REQUIREMENTS:\n{requirements_list}\n\n"
        f"RELEVANT KNOWLEDGE:\n{knowledge_summary}\n\n"
        f"Generate {option_count} distinct solution options that address these requirements."
    )


TRADEOFF_SYSTEM_PROMPT = """\
You are an enterprise architecture reviewer. Analyze how well the given solution option \
addresses each of the provided criteria.

For each criterion return:
- "criterion": exactly as provided
- "stance": one of "meets", "partially_meets", "does_not_meet"
- "rationale": one sentence (max 200 chars)

Return ONLY: {{"trade_offs": [...]}}. Be explicit — "does_not_meet" when appropriate.\
"""


def tradeoff_user_prompt(
    option_title: str,
    option_rationale: str,
    element_names: str,
    criteria_list: str,
) -> str:
    return (
        f"OPTION: {option_title}\n"
        f"RATIONALE: {option_rationale}\n"
        f"PROPOSED ELEMENTS: {element_names}\n\n"
        f"CRITERIA TO ASSESS:\n{criteria_list}\n\n"
        "Assess this option against each criterion."
    )
