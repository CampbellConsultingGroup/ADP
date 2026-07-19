"""Business Capabilities Agent Review adapter (ADP-SPEC-039).

A "business architecture expert" reviews a single capability and everything
directly linked to it, proposing suggestions grounded in that context. This
is the first (and, for this spec, only) adapter built on the shared
`adp.agents` toolkit -- see that package for the domain-agnostic pieces
(grounding validator, LLM stub, provenance helpers) this module composes.

v1 scope (US1 of this spec): `flag_duplicate` only. Later stories add
`reclassify_strategic_relevance`, `set_maturity_level`, `assign_domain`, and
`propose_new_capability` to `_parse_suggestions`/`_ground_and_finalize`
without touching the endpoints, context assembly, or failure handling below.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adp.agents.grounding import verify_references
from adp.agents.models import GroundingCitation
from adp.agents.provenance import write_suggestion_reasoning
from adp.application import store as astore
from adp.business import store as bstore
from adp.business.models import BusinessCapability, CapabilitySuggestion
from adp.telemetry.spans import ai_step_span

logger = logging.getLogger("adp.business.agent_review")

# Loaded from docs/, not hardcoded, so the persona/domain framing (e.g.
# retail-industry blind spots) is editable without a code change.
_PROMPT_PATH = Path(__file__).resolve().parents[3] / "docs" / "system_prompt_sr_bus_arch.md"

_FALLBACK_SYSTEM_PROMPT = (
    "You are a senior business architecture expert reviewing a business "
    "capability and everything linked to it. Propose specific, actionable "
    "suggestions grounded strictly in the provided context; never invent "
    "an id that wasn't given to you."
)


def _load_system_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning(
            "agent_review: system prompt file not found at %s, using fallback", _PROMPT_PATH
        )
        return _FALLBACK_SYSTEM_PROMPT


# ── Context assembly (FR-008, FR-009) ─────────────────────────────────────────

@dataclass(frozen=True)
class CapabilityContext:
    """Everything directly linked to one capability (research.md D5: direct
    links only, no tree/subtree traversal)."""

    capability: BusinessCapability
    parent: BusinessCapability | None
    children: list[BusinessCapability]
    same_level_siblings: list[BusinessCapability]
    stages: list[bstore.CapabilityStageRef]
    applications: list[astore.CapabilityApplicationRef]
    technical_capabilities: list[tuple[str, str]]  # (tech_cap_id, name)
    designs: list[Any]  # DesignRef


async def assemble_context(
    capability_id: str, biz_session: Any, app_session: Any
) -> CapabilityContext | None:
    """Assemble a capability's review context. Returns None if it doesn't exist."""
    capability = await bstore.get_capability(capability_id, biz_session)
    if capability is None:
        return None

    all_caps = await bstore.list_capabilities(biz_session)
    parent = (
        next((c for c in all_caps if c.id == capability.parent_id), None)
        if capability.parent_id
        else None
    )
    children = [c for c in all_caps if c.parent_id == capability_id]
    same_level_siblings = [
        c for c in all_caps if c.level == capability.level and c.id != capability_id
    ]

    stages = await bstore.list_stages_for_capability(capability_id, biz_session)
    # FR-009: non-sensitive APM fields only -- list_applications_for_capability
    # never selects risk/cost/governance columns at all, by construction.
    applications = await astore.list_applications_for_capability(capability_id, app_session)
    designs = await bstore.list_capability_designs(capability_id, biz_session)

    tech_caps: dict[str, str] = {}
    for app in applications:
        links = await astore.list_app_tech_cap_links(app.app_id, app_session)
        for link in links.items:
            tech_caps[link.tech_cap_id] = link.tech_cap_name

    return CapabilityContext(
        capability=capability,
        parent=parent,
        children=children,
        same_level_siblings=same_level_siblings,
        stages=stages,
        applications=applications,
        technical_capabilities=sorted(tech_caps.items(), key=lambda t: t[1]),
        designs=designs,
    )


def _build_user_prompt(context: CapabilityContext) -> str:
    cap = context.capability
    lines = [
        f"Review this business capability (id={cap.id}):",
        f"- Name: {cap.name}",
        f"- Description: {cap.description or '(none)'}",
        f"- Hierarchy level: L{cap.level}",
        f"- Strategic relevance: "
        f"{cap.strategic_relevance if cap.strategic_relevance else 'unclassified'}",
        f"- Maturity level: {cap.maturity_level if cap.maturity_level else 'not assessed'}",
        f"- Domain: {cap.domain_name or 'unassigned'}",
    ]
    if context.parent:
        lines.append(f"- Parent capability: {context.parent.name} (id={context.parent.id})")
    if context.children:
        lines.append(
            "- Child capabilities: "
            + ", ".join(f"{c.name} (id={c.id})" for c in context.children)
        )
    if context.stages:
        lines.append(
            "- Linked value-stream stages: "
            + ", ".join(f"{s.stage_name} in {s.value_stream_name}" for s in context.stages)
        )
    if context.applications:
        lines.append("- Linked applications (non-sensitive fields only):")
        for a in context.applications:
            lines.append(
                f"    - {a.app_name} (id={a.app_id}, fit_score={a.fit_score}, "
                f"TIME={a.time_classification or 'unclassified'}, "
                f"health_score={a.health_score if a.health_score is not None else 'n/a'})"
            )
    if context.technical_capabilities:
        lines.append(
            "- Linked technical capabilities: "
            + ", ".join(f"{name} (id={tid})" for tid, name in context.technical_capabilities)
        )
    if context.designs:
        lines.append(
            "- Linked designs: "
            + ", ".join(f"{d.title} (id={d.design_id})" for d in context.designs)
        )

    lines.append("")
    lines.append(f"Other capabilities at the same hierarchy level (L{cap.level}):")
    if context.same_level_siblings:
        for sib in context.same_level_siblings:
            lines.append(f"  - {sib.name} (id={sib.id}): {sib.description or '(no description)'}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append(
        "Task: identify whether this capability is a likely structural duplicate of any "
        "capability in the same-level list above (not a parent/child/different-level "
        "capability). Respond with ONLY a JSON object of this exact shape:\n"
        '{"suggestions": [{"type": "flag_duplicate", '
        '"duplicate_of_capability_id": "<id from the list above>", "rationale": "<why>"}]}\n'
        "Only cite a capability id that appears in the same-level list above -- never "
        "invent one. If there is no plausible duplicate, return "
        '{"suggestions": []} rather than a low-confidence guess.'
    )
    return "\n".join(lines)


# ── LLM response parsing (v1: flag_duplicate only) ────────────────────────────

def _extract_json_content(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices:
        return {"suggestions": []}
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        return {"suggestions": []}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("agent_review: LLM response was not valid JSON, treating as no suggestions")
        return {"suggestions": []}
    return parsed if isinstance(parsed, dict) else {"suggestions": []}


async def _build_flag_duplicate_suggestion(
    raw: dict[str, Any], capability_id: str, cap_lookup: dict[str, str]
) -> CapabilitySuggestion | None:
    """Build and ground one flag_duplicate suggestion. Returns None if malformed."""
    duplicate_id = raw.get("duplicate_of_capability_id")
    rationale = raw.get("rationale")
    if not duplicate_id or not rationale:
        return None

    citation = GroundingCitation(entity_type="business_capability", entity_id=str(duplicate_id))

    async def _capability_exists(entity_id: str) -> bool:
        return entity_id in cap_lookup

    grounding = await verify_references(
        [citation], lookups={"business_capability": _capability_exists}
    )

    return CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="flag_duplicate",
        capability_id=capability_id,
        rationale=str(rationale),
        citations=[citation],
        advisory=not grounding.fully_grounded,
        duplicate_of_capability_id=str(duplicate_id),
    )


async def _parse_suggestions(
    response: dict[str, Any], capability_id: str, same_level_siblings: list[BusinessCapability]
) -> list[CapabilitySuggestion]:
    """Parse the LLM's JSON response into grounded CapabilitySuggestions.

    v1 (US1): flag_duplicate only. Later stories extend this with the other
    four types without changing the surrounding orchestration.
    """
    parsed = _extract_json_content(response)
    raw_suggestions = parsed.get("suggestions") or []
    if not isinstance(raw_suggestions, list):
        return []

    cap_lookup = {c.id: c.name for c in same_level_siblings}
    suggestions: list[CapabilitySuggestion] = []
    for raw in raw_suggestions:
        if not isinstance(raw, dict) or raw.get("type") != "flag_duplicate":
            continue
        suggestion = await _build_flag_duplicate_suggestion(raw, capability_id, cap_lookup)
        if suggestion is not None:
            suggestions.append(suggestion)
    return suggestions


# ── Orchestration (FR-004, FR-006, FR-021) ────────────────────────────────────

async def run_review(
    *,
    operation_id: str,
    capability_id: str,
    biz_session: Any,
    app_session: Any,
    llm_client: Any,
    op_store: Any,
) -> None:
    """Background job: assemble context, call the LLM, ground citations, store
    the suggestion set. Never raises to the caller -- always resolves the
    operation to completed or failed (FR-021).

    ai_step_span records the error on the span and re-raises (ART-VI); the
    outer try/except here catches that re-raise to resolve the operation --
    the try/except deliberately wraps the `with`, not the other way round,
    so the span sees the failure before we swallow it.
    """
    try:
        with ai_step_span("agent_review", operation_id=operation_id) as span:
            span.set_attribute("adp.capability_id", capability_id)

            await op_store.update(operation_id, status="running")

            context = await assemble_context(capability_id, biz_session, app_session)
            if context is None:
                await op_store.update(
                    operation_id,
                    status="failed",
                    payload_patch={"error_description": f"Capability {capability_id!r} not found"},
                )
                return

            system_prompt = _load_system_prompt()
            user_prompt = _build_user_prompt(context)
            response = await llm_client.chat(
                system=system_prompt, user=user_prompt, correlation_id=operation_id
            )

            suggestions = await _parse_suggestions(
                response, capability_id, context.same_level_siblings
            )

            usage = response.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            span.set_attribute("adp.input_tokens", input_tokens)
            span.set_attribute("adp.output_tokens", output_tokens)

            # Reasoning is recorded per-suggestion at generation time, regardless
            # of whether it's later accepted/rejected -- mirrors the recommendation
            # engine's per-option reasoning write (steps.py), not an accept-time
            # concern. Fire-and-forget: never blocks the operation from completing.
            model_id = getattr(llm_client, "_model", "unknown")
            for suggestion in suggestions:
                asyncio.create_task(
                    write_suggestion_reasoning(
                        operation_id=operation_id,
                        suggestion_id=suggestion.suggestion_id,
                        step_name="agent_review",
                        model_id=model_id,
                        reasoning_text=suggestion.rationale,
                        prompt=f"{system_prompt}\n{user_prompt}",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                )

            await op_store.update(
                operation_id,
                status="completed",
                payload_patch={
                    "suggestions": {s.suggestion_id: s.model_dump(mode="json") for s in suggestions}
                },
            )
    except Exception as exc:
        # FR-021: LLM-call (or any step) failure surfaces as failed with
        # error_description, never a silent empty result -- distinct from
        # the legitimate no-LLM-configured case, which COMPLETES empty.
        logger.exception("agent_review.run_review failed for capability %s", capability_id)
        await op_store.update(
            operation_id,
            status="failed",
            payload_patch={"error_description": str(exc)[:500]},
        )
