"""LLM critic prompt templates for validation (ADP-SPEC-008)."""

from __future__ import annotations

SCORING_RUBRIC = """\
SCORING RUBRIC (use these anchors exactly):
1.0: Fully compliant — no deviations from any applicable item
0.75: Minor deviation — one non-critical issue with mitigatable risk
0.5: Significant gap — one major issue requiring review
0.25: Multiple gaps — two or more major issues
0.0: Clear violation — explicit non-compliance with at least one mandatory item\
"""

_COMMON_SYSTEM = (
    "{dimension_instruction}\n\n"
    + SCORING_RUBRIC
    + "\n\nFor each non-compliance, identify the element, describe the issue, and cite the item id."
    + "\nReturn ONLY JSON: "
    + '{{"score": 0.0-1.0, "findings": [{{"element_id": "ELM-NNN or null",'
    + ' "description": "...", "cited_id": "id from provided list"}}]}}'
    + '\nIf no issues found return: {{"score": 1.0, "findings": []}}'
)

STANDARDS_SYSTEM = _COMMON_SYSTEM.format(
    dimension_instruction=(
        "You are an architecture standards compliance reviewer. "
        "Evaluate the provided design elements against the applicable organizational standards."
    )
)

PRINCIPLES_SYSTEM = _COMMON_SYSTEM.format(
    dimension_instruction=(
        "You are an architecture principles reviewer. "
        "Evaluate the provided design elements against the applicable architecture principles."
    )
)

PATTERN_FIT_SYSTEM = _COMMON_SYSTEM.format(
    dimension_instruction=(
        "You are an architecture pattern reviewer. "
        "Evaluate how well the design applies or deviates from the provided relevant patterns."
    )
)

CONSISTENCY_SYSTEM = _COMMON_SYSTEM.format(
    dimension_instruction=(
        "You are an architecture consistency reviewer. "
        "Identify significant inconsistencies between the design and prior approved solutions "
        "that lack documented justification."
    )
)


def _elements_summary(design: object) -> str:
    elements = getattr(design, "elements", [])
    lines = [
        f"[{e.id}] {e.kind.value}: {e.name} — satisfies: {e.satisfies or '[]'}"
        for e in elements
    ]
    return "\n".join(lines) or "(no elements)"


def _knowledge_summary(entries: list) -> str:  # type: ignore[type-arg]
    lines = []
    for e in entries:
        item = e.item
        excerpt = (getattr(item, "full_text", "") or "")[:120].replace("\n", " ")
        lines.append(
            f"[{e.citation.item_id}@{e.citation.item_version}] "
            f"{getattr(item, 'kind', '?')}: \"{getattr(item, 'title', '?')}\" — {excerpt}"
        )
    return "\n".join(lines) or "(no knowledge items)"


def standards_user_prompt(design: object, knowledge_entries: list) -> str:  # type: ignore[type-arg]
    return (
        f"DESIGN ELEMENTS:\n{_elements_summary(design)}\n\n"
        f"APPLICABLE STANDARDS:\n{_knowledge_summary(knowledge_entries)}\n\n"
        "Evaluate compliance with each standard."
    )


def principles_user_prompt(design: object, knowledge_entries: list) -> str:  # type: ignore[type-arg]
    return (
        f"DESIGN ELEMENTS:\n{_elements_summary(design)}\n\n"
        f"APPLICABLE PRINCIPLES:\n{_knowledge_summary(knowledge_entries)}\n\n"
        "Evaluate alignment with each principle."
    )


def pattern_fit_user_prompt(design: object, knowledge_entries: list) -> str:  # type: ignore[type-arg]
    return (
        f"DESIGN ELEMENTS:\n{_elements_summary(design)}\n\n"
        f"RELEVANT PATTERNS:\n{_knowledge_summary(knowledge_entries)}\n\n"
        "Evaluate how well the design applies or deviates from these patterns."
    )


def consistency_user_prompt(design: object, knowledge_entries: list) -> str:  # type: ignore[type-arg]
    return (
        f"DESIGN ELEMENTS:\n{_elements_summary(design)}\n\n"
        f"PRIOR APPROVED SOLUTIONS:\n{_knowledge_summary(knowledge_entries)}\n\n"
        "Identify significant inconsistencies with prior solutions"
        " without documented justification."
    )
