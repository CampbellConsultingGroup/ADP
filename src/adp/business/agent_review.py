"""Business Capabilities Agent Review adapter (ADP-SPEC-039/040).

A "business architecture expert" reviews either a single capability and
everything directly linked to it (`run_review`), or the whole capability
portfolio at once (`run_portfolio_review`, ADP-SPEC-040), proposing
suggestions grounded in that context. This is the first (and, for 039, only)
adapter built on the shared `adp.agents` toolkit -- see that package for the
domain-agnostic pieces (grounding validator, LLM stub, provenance helpers)
this module composes.

Per-capability scope supports five suggestion types: `flag_duplicate`,
`reclassify_strategic_relevance`, `set_maturity_level`, `assign_domain`,
`propose_new_capability` (US1-US4). Portfolio scope reuses
`propose_new_capability` (scanning uncovered stages across every value
stream, not just one capability's siblings) and adds a sixth type,
`flag_capability_for_removal`, that only a whole-tree review can meaningfully
produce.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adp.admin import prompt_registry
from adp.agents.grounding import verify_references
from adp.agents.models import GroundingCitation
from adp.agents.provenance import write_suggestion_reasoning
from adp.application import store as astore
from adp.business import store as bstore
from adp.business.models import (
    MATURITY_LEVEL_LABELS,
    STRATEGIC_RELEVANCE_LABELS,
    BusinessCapability,
    BusinessDomain,
    CapabilitySuggestion,
)
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
    # Populated only when assign_domain could apply (FR-012: L1, unassigned) --
    # empty otherwise, so the prompt never offers a domain-assignment task to a
    # capability it doesn't apply to.
    assignable_domains: list[BusinessDomain]
    # Value-stream stages in the same value stream(s) as `stages` above that
    # have NO capability coverage at all -- the supporting-context signal for
    # propose_new_capability (US4). Direct-link scoped (research D5): only the
    # value streams this capability itself already touches.
    uncovered_stages: list[bstore.CapabilityStageRef]


async def _find_uncovered_sibling_stages(
    context_stages: list[bstore.CapabilityStageRef], biz_session: Any
) -> list[bstore.CapabilityStageRef]:
    """Stages in the same value stream(s) as `context_stages` that have no
    capability linked at all -- a candidate capability gap (US4). Scoped to
    the value streams the reviewed capability's own stages already belong to,
    not a full portfolio scan (research D5: direct links only)."""
    seen_vs_ids = {s.value_stream_id for s in context_stages}
    own_stage_ids = {s.stage_id for s in context_stages}

    uncovered: list[bstore.CapabilityStageRef] = []
    for vs_id in seen_vs_ids:
        vs = await bstore.get_value_stream(vs_id, biz_session)
        if vs is None:
            continue
        for stage in vs.stages:
            if stage.id in own_stage_ids:
                continue
            caps = await bstore.list_stage_caps(vs_id, stage.id, biz_session)
            if caps is not None and not caps.items:
                uncovered.append(
                    bstore.CapabilityStageRef(
                        stage_id=stage.id,
                        stage_name=stage.name,
                        value_stream_id=vs_id,
                        value_stream_name=vs.name,
                    )
                )
    return uncovered


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

    # FR-012: assign_domain only applies to an unassigned L1 capability -- only
    # fetch/offer domains in that case, so a lower-level or already-assigned
    # capability's prompt never invites the suggestion at all.
    assignable_domains = (
        await bstore.list_domains_full(biz_session)
        if capability.level == 1 and capability.domain_id is None
        else []
    )
    uncovered_stages = await _find_uncovered_sibling_stages(stages, biz_session)

    return CapabilityContext(
        capability=capability,
        parent=parent,
        children=children,
        same_level_siblings=same_level_siblings,
        stages=stages,
        applications=applications,
        technical_capabilities=sorted(tech_caps.items(), key=lambda t: t[1]),
        designs=designs,
        assignable_domains=assignable_domains,
        uncovered_stages=uncovered_stages,
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

    if context.assignable_domains:
        lines.append("")
        lines.append("Available business domains (this capability has none assigned):")
        for domain in context.assignable_domains:
            lines.append(
                f"  - {domain.name} (id={domain.id}, classification={domain.classification}): "
                f"{domain.scope_statement or '(no scope statement)'}"
            )

    if context.uncovered_stages:
        lines.append("")
        lines.append(
            "Value-stream stages with NO capability coverage at all "
            "(potential capability gaps):"
        )
        for stage in context.uncovered_stages:
            lines.append(
                f"  - {stage.stage_name} in {stage.value_stream_name} (id={stage.stage_id})"
            )

    relevance_label = (
        STRATEGIC_RELEVANCE_LABELS.get(cap.strategic_relevance, "unclassified")
        if cap.strategic_relevance
        else "unclassified"
    )
    maturity_label = (
        MATURITY_LEVEL_LABELS.get(cap.maturity_level, "not assessed")
        if cap.maturity_level
        else "not assessed"
    )
    lines.append("")
    lines.append(
        f"Current strategic relevance: {relevance_label}. Current maturity level: {maturity_label}."
    )

    task_lines = [
        "Tasks -- propose zero or more of the following, each as one object in a "
        '"suggestions" list. Respond with ONLY a JSON object: {"suggestions": [...]}.\n',
        "1. flag_duplicate -- is this capability a likely structural duplicate of any "
        "capability in the same-level list above (never a parent/child/different-level "
        "capability)? {\"type\": \"flag_duplicate\", "
        '"duplicate_of_capability_id": "<id from the same-level list above>", '
        '"rationale": "<why>"}. Only cite an id from that list -- never invent one.\n',
        "2. reclassify_strategic_relevance -- should strategic relevance be set or "
        "changed? Values: 1=Strategic, 2=Core, 3=Supporting. "
        '{"type": "reclassify_strategic_relevance", "strategic_relevance": <1|2|3>, '
        '"rationale": "<why, stating the current value if already classified>"}.\n',
        "3. set_maturity_level -- should the CMMI-style maturity level be set or "
        "changed? Values: 1=Ad hoc, 2=Emerging, 3=Established, 4=Advanced, "
        "5=World Class. "
        '{"type": "set_maturity_level", "maturity_level": <1-5>, '
        '"rationale": "<why, stating the current value if already assessed>"}.\n',
    ]
    if context.assignable_domains:
        task_lines.append(
            "4. assign_domain -- does this capability clearly belong to one of the "
            "business domains listed above, based on its scope statement? "
            '{"type": "assign_domain", "domain_id": "<id from the domains list above>", '
            '"rationale": "<why this domain\'s scope fits>"}. Only cite an id from that '
            "list -- never invent one, and never suggest this if no domain list was "
            "given above.\n"
        )
    if context.uncovered_stages:
        child_level_hint = (
            f"a child would be level {cap.level + 1}"
            if cap.level < 3
            else "a child is not possible (max depth L3 already reached)"
        )
        task_lines.append(
            "5. propose_new_capability -- does one of the uncovered stages above imply "
            "a capability that doesn't exist yet? Propose exactly ONE new capability "
            f"as either a sibling of this one (level {cap.level}, same parent_id) or "
            f"a child of this one ({child_level_hint}, parent_id="
            f'"{cap.id}"). {{"type": "propose_new_capability", '
            '"proposed_name": "<name>", "proposed_description": "<description>", '
            f'"proposed_level": <1-3>, "proposed_parent_id": "<parent id, or null for '
            'a top-level sibling>", "supporting_stage_id": "<id from the uncovered-'
            'stages list above>", "rationale": "<why, citing the specific uncovered '
            'stage>"}. Only cite a stage id from that list -- never invent one, and '
            "never propose this if no uncovered-stages list was given above.\n"
        )
    task_lines.append(
        'If none apply, return {"suggestions": []} rather than a low-confidence guess.'
    )

    lines.append("")
    lines.append("\n".join(task_lines))
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


def _build_flag_duplicate_suggestion(
    raw: dict[str, Any], capability_id: str, cap_lookup: dict[str, str]
) -> tuple[CapabilitySuggestion, GroundingCitation] | None:
    """Build one flag_duplicate suggestion (ungrounded -- caller grounds it).
    Returns None if malformed."""
    duplicate_id = raw.get("duplicate_of_capability_id")
    rationale = raw.get("rationale")
    if not duplicate_id or not rationale:
        return None

    citation = GroundingCitation(entity_type="business_capability", entity_id=str(duplicate_id))
    suggestion = CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="flag_duplicate",
        capability_id=capability_id,
        rationale=str(rationale),
        citations=[citation],
        duplicate_of_capability_id=str(duplicate_id),
    )
    return suggestion, citation


def _build_reclassify_strategic_relevance_suggestion(
    raw: dict[str, Any], capability: BusinessCapability
) -> CapabilitySuggestion | None:
    """Build one reclassify_strategic_relevance suggestion. No citations to
    ground -- it targets the reviewed capability's own field, not another
    entity. Captures the current value as the FR-015 accept-time snapshot."""
    value = raw.get("strategic_relevance")
    rationale = raw.get("rationale")
    if value not in (1, 2, 3) or not rationale:
        return None

    return CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="reclassify_strategic_relevance",
        capability_id=capability.id,
        rationale=str(rationale),
        strategic_relevance=value,
        previous_strategic_relevance=capability.strategic_relevance,
    )


def _build_set_maturity_level_suggestion(
    raw: dict[str, Any], capability: BusinessCapability
) -> CapabilitySuggestion | None:
    """Build one set_maturity_level suggestion. Same shape as strategic
    relevance above: no citations, captures the FR-015 snapshot."""
    value = raw.get("maturity_level")
    rationale = raw.get("rationale")
    if value not in (1, 2, 3, 4, 5) or not rationale:
        return None

    return CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="set_maturity_level",
        capability_id=capability.id,
        rationale=str(rationale),
        maturity_level=value,
        previous_maturity_level=capability.maturity_level,
    )


def _build_assign_domain_suggestion(
    raw: dict[str, Any], capability: BusinessCapability
) -> tuple[CapabilitySuggestion, GroundingCitation] | None:
    """Build one assign_domain suggestion (ungrounded -- caller grounds it
    against business_domains, not business_capabilities -- cross-entity-type
    grounding, US3). FR-012 gates this to an unassigned L1 capability; the
    caller only offers a domain list to the LLM in that case, but we also gate
    here defensively in case the model ignores that."""
    if capability.level != 1 or capability.domain_id is not None:
        return None

    domain_id = raw.get("domain_id")
    rationale = raw.get("rationale")
    if not domain_id or not rationale:
        return None

    citation = GroundingCitation(entity_type="business_domain", entity_id=str(domain_id))
    suggestion = CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="assign_domain",
        capability_id=capability.id,
        rationale=str(rationale),
        citations=[citation],
        domain_id=str(domain_id),
    )
    return suggestion, citation


def _build_propose_new_capability_suggestion(
    raw: dict[str, Any],
) -> tuple[CapabilitySuggestion, GroundingCitation] | None:
    """Build one propose_new_capability suggestion (ungrounded -- caller
    grounds it). Unlike every other type, there's no existing capability id to
    cite for what's being proposed (it doesn't exist yet) -- ART-VII is
    satisfied instead by requiring a real, verifiable *supporting-context*
    citation (the uncovered stage), never a fabricated "proposed capability
    id". capability_id is left None (data-model.md: null only for this type).
    Takes no capability param -- shared verbatim between per-capability
    review (US4) and portfolio review (ADP-SPEC-040), neither of which this
    builder needs to know about."""
    name = raw.get("proposed_name")
    level = raw.get("proposed_level")
    rationale = raw.get("rationale")
    supporting_stage_id = raw.get("supporting_stage_id")
    if not name or level not in (1, 2, 3) or not rationale or not supporting_stage_id:
        return None

    parent_id = raw.get("proposed_parent_id")
    citation = GroundingCitation(
        entity_type="value_stream_stage", entity_id=str(supporting_stage_id)
    )
    suggestion = CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="propose_new_capability",
        capability_id=None,
        rationale=str(rationale),
        citations=[citation],
        proposed_name=str(name),
        proposed_description=raw.get("proposed_description"),
        proposed_level=level,
        proposed_parent_id=str(parent_id) if parent_id else None,
    )
    return suggestion, citation


def _build_flag_capability_for_removal_suggestion(
    raw: dict[str, Any],
) -> tuple[CapabilitySuggestion, GroundingCitation] | None:
    """Build one flag_capability_for_removal suggestion (ungrounded -- caller
    grounds it). Portfolio-review scope only (ADP-SPEC-040): unlike
    flag_duplicate, which compares two capabilities at the same level, this
    targets a single existing capability directly -- the citation IS the
    suggestion's own capability_id, grounded against the full portfolio
    (any level), not a level-scoped pool."""
    target_id = raw.get("target_capability_id")
    rationale = raw.get("rationale")
    if not target_id or not rationale:
        return None

    citation = GroundingCitation(entity_type="business_capability", entity_id=str(target_id))
    suggestion = CapabilitySuggestion(
        suggestion_id=str(uuid.uuid4()),
        type="flag_capability_for_removal",
        capability_id=str(target_id),
        rationale=str(rationale),
        citations=[citation],
    )
    return suggestion, citation


async def _parse_suggestions(
    response: dict[str, Any], context: CapabilityContext
) -> list[CapabilitySuggestion]:
    """Parse the LLM's JSON response into grounded CapabilitySuggestions.

    All five suggestion types: flag_duplicate, reclassify_strategic_relevance,
    set_maturity_level, assign_domain, propose_new_capability.
    """
    parsed = _extract_json_content(response)
    raw_suggestions = parsed.get("suggestions") or []
    if not isinstance(raw_suggestions, list):
        return []

    capability = context.capability
    cap_lookup = {c.id: c.name for c in context.same_level_siblings}
    domain_lookup = {d.id: d.name for d in context.assignable_domains}
    stage_lookup = {s.stage_id: s.stage_name for s in context.uncovered_stages}

    async def _capability_exists(entity_id: str) -> bool:
        return entity_id in cap_lookup

    async def _domain_exists(entity_id: str) -> bool:
        return entity_id in domain_lookup

    async def _stage_exists(entity_id: str) -> bool:
        return entity_id in stage_lookup

    suggestions: list[CapabilitySuggestion] = []
    ungrounded: list[tuple[CapabilitySuggestion, GroundingCitation]] = []

    for raw in raw_suggestions:
        if not isinstance(raw, dict):
            continue
        suggestion_type = raw.get("type")
        if suggestion_type == "flag_duplicate":
            built = _build_flag_duplicate_suggestion(raw, capability.id, cap_lookup)
            if built is not None:
                ungrounded.append(built)
        elif suggestion_type == "reclassify_strategic_relevance":
            suggestion = _build_reclassify_strategic_relevance_suggestion(raw, capability)
            if suggestion is not None:
                suggestions.append(suggestion)
        elif suggestion_type == "set_maturity_level":
            suggestion = _build_set_maturity_level_suggestion(raw, capability)
            if suggestion is not None:
                suggestions.append(suggestion)
        elif suggestion_type == "assign_domain":
            built = _build_assign_domain_suggestion(raw, capability)
            if built is not None:
                ungrounded.append(built)
        elif suggestion_type == "propose_new_capability":
            built = _build_propose_new_capability_suggestion(raw)
            if built is not None:
                ungrounded.append(built)

    for suggestion, citation in ungrounded:
        grounding = await verify_references(
            [citation],
            lookups={
                "business_capability": _capability_exists,
                "business_domain": _domain_exists,
                "value_stream_stage": _stage_exists,
            },
        )
        suggestions.append(suggestion.model_copy(update={"advisory": not grounding.fully_grounded}))

    return suggestions


# ── Portfolio-scope review (ADP-SPEC-040) ─────────────────────────────────────
# Reviews the ENTIRE capability tree at once rather than one capability's
# direct links. Only two suggestion types apply at this scope:
# propose_new_capability (reused verbatim from per-capability scope) and
# flag_capability_for_removal (portfolio-only -- there's no single "reviewed
# capability" whose siblings/duplicates would make flag_duplicate meaningful
# here; reclassify/maturity/domain-assignment stay per-capability only, since
# those target one specific capability's own fields by design).

@dataclass(frozen=True)
class PortfolioContext:
    """The whole capability tree plus every uncovered value-stream stage,
    portfolio-wide (contrast CapabilityContext's direct-links-only scope)."""

    capabilities: list[BusinessCapability]
    uncovered_stages: list[bstore.CapabilityStageRef]


async def assemble_portfolio_context(biz_session: Any) -> PortfolioContext:
    """Assemble the whole-portfolio review context. Unlike assemble_context,
    this can never return None -- an empty portfolio is still a valid (if
    unremarkable) thing to review."""
    capabilities = await bstore.list_capabilities(biz_session)
    uncovered_stages = await bstore.list_all_uncovered_stages(biz_session)
    return PortfolioContext(capabilities=capabilities, uncovered_stages=uncovered_stages)


def _build_portfolio_user_prompt(context: PortfolioContext) -> str:
    lines = ["Review this organization's entire business capability portfolio:", ""]

    by_level: dict[int, list[BusinessCapability]] = {1: [], 2: [], 3: []}
    for cap in context.capabilities:
        by_level.setdefault(cap.level, []).append(cap)

    for level in (1, 2, 3):
        caps = by_level.get(level, [])
        if not caps:
            continue
        lines.append(f"L{level} capabilities:")
        for cap in caps:
            parent_note = f", parent_id={cap.parent_id}" if cap.parent_id else ""
            lines.append(
                f"  - {cap.name} (id={cap.id}{parent_note}): "
                f"{cap.description or '(no description)'}"
            )
        lines.append("")

    if context.uncovered_stages:
        lines.append(
            "Value-stream stages with NO capability coverage at all "
            "(potential capability gaps):"
        )
        for stage in context.uncovered_stages:
            lines.append(
                f"  - {stage.stage_name} in {stage.value_stream_name} (id={stage.stage_id})"
            )
        lines.append("")

    task_lines = [
        "Tasks -- propose zero or more of the following, each as one object in a "
        '"suggestions" list. Respond with ONLY a JSON object: {"suggestions": [...]}.\n',
    ]
    if context.uncovered_stages:
        task_lines.append(
            "1. propose_new_capability -- does an uncovered stage above imply a "
            "capability that doesn't exist yet? Propose a new capability with a level "
            "and parent_id consistent with the existing hierarchy above (a level-1 "
            "capability has no parent_id; level-2/3 must reference a real parent id "
            "from the lists above at the level directly above it). "
            '{"type": "propose_new_capability", "proposed_name": "<name>", '
            '"proposed_description": "<description>", "proposed_level": <1-3>, '
            '"proposed_parent_id": "<parent id from the lists above, or null for a '
            'level-1 capability>", "supporting_stage_id": "<id from the uncovered-'
            'stages list above>", "rationale": "<why, citing the specific uncovered '
            'stage>"}. Only cite a stage id from that list -- never invent one.\n'
        )
    task_lines.append(
        "2. flag_capability_for_removal -- is any capability above clearly obsolete, "
        "redundant, or no longer meaningful (e.g. no description, a placeholder-looking "
        "name, or fully superseded by another capability)? Flag at most a few, and only "
        "with clear justification -- removal is destructive and should be rare. "
        '{"type": "flag_capability_for_removal", '
        '"target_capability_id": "<id from the lists above>", '
        '"rationale": "<why this specific capability should be removed>"}. Only cite '
        "an id from the lists above -- never invent one. Do not flag a capability that "
        "has children (it cannot be removed while children exist).\n"
    )
    task_lines.append(
        'If none apply, return {"suggestions": []} rather than a low-confidence guess.'
    )
    lines.append("\n".join(task_lines))
    return "\n".join(lines)


async def _parse_portfolio_suggestions(
    response: dict[str, Any], context: PortfolioContext
) -> list[CapabilitySuggestion]:
    """Parse the LLM's JSON response into grounded CapabilitySuggestions,
    portfolio scope: propose_new_capability and flag_capability_for_removal
    only."""
    parsed = _extract_json_content(response)
    raw_suggestions = parsed.get("suggestions") or []
    if not isinstance(raw_suggestions, list):
        return []

    cap_lookup = {c.id: c.name for c in context.capabilities}
    stage_lookup = {s.stage_id: s.stage_name for s in context.uncovered_stages}

    async def _capability_exists(entity_id: str) -> bool:
        return entity_id in cap_lookup

    async def _stage_exists(entity_id: str) -> bool:
        return entity_id in stage_lookup

    suggestions: list[CapabilitySuggestion] = []
    ungrounded: list[tuple[CapabilitySuggestion, GroundingCitation]] = []

    for raw in raw_suggestions:
        if not isinstance(raw, dict):
            continue
        suggestion_type = raw.get("type")
        if suggestion_type == "propose_new_capability":
            built = _build_propose_new_capability_suggestion(raw)
            if built is not None:
                ungrounded.append(built)
        elif suggestion_type == "flag_capability_for_removal":
            built = _build_flag_capability_for_removal_suggestion(raw)
            if built is not None:
                ungrounded.append(built)

    for suggestion, citation in ungrounded:
        grounding = await verify_references(
            [citation],
            lookups={
                "business_capability": _capability_exists,
                "value_stream_stage": _stage_exists,
            },
        )
        suggestions.append(suggestion.model_copy(update={"advisory": not grounding.fully_grounded}))

    return suggestions


async def run_portfolio_review(
    *,
    operation_id: str,
    biz_session: Any,
    llm_client: Any,
    op_store: Any,
) -> None:
    """Background job: portfolio-scope sibling of run_review below -- same
    span/reasoning/failure-handling shape, different context assembly and
    parsing (see the "Portfolio-scope review" section above)."""
    try:
        with ai_step_span("agent_review", operation_id=operation_id) as span:
            span.set_attribute("adp.capability_id", "PORTFOLIO")

            await op_store.update(operation_id, status="running")

            context = await assemble_portfolio_context(biz_session)

            # ADP-SPEC-042: resolve via the admin-editable registry (falls
            # back to _load_system_prompt() -- file, then _FALLBACK_SYSTEM_PROMPT
            # -- when no admin override exists).
            system_prompt = (
                await prompt_registry.get_effective_prompt("agent_review_business_capability")
            ).text
            user_prompt = _build_portfolio_user_prompt(context)
            response = await llm_client.chat(
                system=system_prompt, user=user_prompt, correlation_id=operation_id
            )

            suggestions = await _parse_portfolio_suggestions(response, context)

            usage = response.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            span.set_attribute("adp.input_tokens", input_tokens)
            span.set_attribute("adp.output_tokens", output_tokens)

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
        logger.exception("agent_review.run_portfolio_review failed")
        await op_store.update(
            operation_id,
            status="failed",
            payload_patch={"error_description": str(exc)[:500]},
        )


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

            # ADP-SPEC-042: resolve via the admin-editable registry (falls
            # back to _load_system_prompt() -- file, then _FALLBACK_SYSTEM_PROMPT
            # -- when no admin override exists).
            system_prompt = (
                await prompt_registry.get_effective_prompt("agent_review_business_capability")
            ).text
            user_prompt = _build_user_prompt(context)
            response = await llm_client.chat(
                system=system_prompt, user=user_prompt, correlation_id=operation_id
            )

            suggestions = await _parse_suggestions(response, context)

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
