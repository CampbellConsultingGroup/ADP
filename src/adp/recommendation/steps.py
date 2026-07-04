"""Five LangGraph step functions for the recommendation pipeline (ADP-SPEC-007).

Step order: retrieve → generate → analyze_tradeoffs → rank → validate_citations
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from adp.knowledge.schema import CitationRef, RetrievalQuery
from adp.models import ElementKind
from adp.recommendation.models import (
    ProposedElement,
    RecommendationState,
    RecommendationStep,
    SolutionOption,
    TradeOffEntry,
    TradeOffStance,
)
from adp.recommendation.prompts import (
    GENERATION_SYSTEM_PROMPT,
    GENERATION_SYSTEM_PROMPT_NO_KB,
    TRADEOFF_SYSTEM_PROMPT,
    generation_user_prompt,
    tradeoff_user_prompt,
)

if TYPE_CHECKING:
    from adp.knowledge import KnowledgeRetrieval
    from adp.llm.client import LLMClient
    from adp.recommendation.telemetry import RecommendationTelemetry

_logger = logging.getLogger("adp.recommendation")


def _parse_json_with_repair(content: str) -> dict:
    """Parse JSON; on failure attempt to recover a partial options array.

    Claude may truncate mid-JSON when output is large. We try to salvage any
    fully-formed options that appear before the truncation point.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        _logger.warning("JSON parse failed (%s); attempting partial recovery", exc)

    # Strategy: find the last complete '}' that closes an option object inside
    # the options array, then close the array and root object manually.
    bracket = content.find('"options"')
    if bracket == -1:
        return {}
    arr_start = content.find("[", bracket)
    if arr_start == -1:
        return {}

    # Walk backwards from the truncation point to find the last valid object close
    snippet = content[arr_start:]
    depth = 0
    last_complete = -1
    for i, ch in enumerate(snippet):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_complete = i
    if last_complete == -1:
        return {}

    repaired = snippet[: last_complete + 1] + "]}"
    try:
        recovered = json.loads('{"options": ' + repaired[1:])
        _logger.info("Partial recovery succeeded: %d option(s)", len(recovered.get("options", [])))
        return recovered
    except json.JSONDecodeError:
        return {}


_QUALITY_KEYWORDS = frozenset({
    "performance", "security", "scalability", "reliability",
    "availability", "latency", "throughput", "resilience",
})


def _is_quality_requirement(description: str) -> bool:
    return any(kw in description.lower() for kw in _QUALITY_KEYWORDS)


def _knowledge_summary(entries: list[Any]) -> str:
    lines = []
    for e in entries:
        item = e.item
        excerpt = (item.full_text or "")[:120].replace("\n", " ")
        lines.append(f"[{e.citation.item_id}@{e.citation.item_version}] "
                     f"{item.kind}: \"{item.title}\" — {excerpt}")
    return "\n".join(lines) or "(no knowledge items retrieved)"


async def retrieve_step(
    state: RecommendationState,
    *,
    knowledge_retrieval: "KnowledgeRetrieval",
    telemetry: "RecommendationTelemetry",
) -> RecommendationState:
    """Step 1: Retrieve relevant knowledge for all input requirements."""
    start = time.perf_counter()
    requirements = state.get("requirements", [])
    seen_ids: set[str] = set()
    merged: list[Any] = []

    for req in requirements:
        desc = getattr(req, "description", "") or getattr(req, "title", "")
        try:
            result = await knowledge_retrieval.hybrid_search(
                RetrievalQuery(
                    query_text=desc,
                    kinds=None,  # all types; retrieval will surface patterns/standards/principles
                    limit=5,
                )
            )
            for entry in result.items:
                iid = entry.citation.item_id
                if iid not in seen_ids:
                    seen_ids.add(iid)
                    merged.append(entry)
        except Exception as exc:
            _logger.warning("Retrieval failed for requirement %s: %s", getattr(req, "id", "?"), exc)

    latency = (time.perf_counter() - start) * 1000
    telemetry.emit_step_span(RecommendationStep(
        operation_id=state["operation_id"],
        step_name="retrieve",
        correlation_id=state.get("correlation_id"),
        retrieved_knowledge_refs=[
            f"{e.citation.item_id}@{e.citation.item_version}" for e in merged
        ],
        latency_ms=latency,
    ))

    return {**state, "retrieved_knowledge": merged}


async def generate_step(
    state: RecommendationState,
    *,
    llm: "LLMClient",
    telemetry: "RecommendationTelemetry",
    option_count: int = 3,
) -> RecommendationState:
    """Step 2: Generate candidate SolutionOptions grounded in retrieved knowledge."""
    start = time.perf_counter()
    requirements = state.get("requirements", [])
    retrieved = state.get("retrieved_knowledge", [])

    req_list = "\n".join(
        f"- [{getattr(r, 'id', '?')}] {getattr(r, 'description', getattr(r, 'title', ''))}"
        for r in requirements
    )
    knowledge_summary = _knowledge_summary(retrieved)
    req_ids = [getattr(r, "id", str(i)) for i, r in enumerate(requirements)]

    # ADP-SPEC-019: use requirements-only prompt when KB is empty
    has_knowledge = bool(retrieved)
    if has_knowledge:
        system = GENERATION_SYSTEM_PROMPT.format(option_count=option_count)
    else:
        system = GENERATION_SYSTEM_PROMPT_NO_KB.format(option_count=option_count)
    user = generation_user_prompt(
        req_list, knowledge_summary, option_count, has_knowledge=has_knowledge
    )

    input_tokens = 0
    output_tokens = 0
    candidates: list[SolutionOption] = []
    error_msg = None

    try:
        raw = await llm.chat(system, user, correlation_id=state.get("correlation_id"))

        usage = raw.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        data = _parse_json_with_repair(content) if isinstance(content, str) else content
        raw_options = data.get("options", [])[:option_count]  # cap at option_count

        for item in raw_options:
            elements: list[ProposedElement] = []
            for pe in item.get("proposed_elements", []):
                try:
                    kind = ElementKind(pe.get("kind", "component"))
                except ValueError:
                    kind = ElementKind.COMPONENT
                    _logger.warning(
                        "Invalid element kind %r; defaulting to component", pe.get("kind")
                    )
                elements.append(ProposedElement(
                    name=str(pe.get("name", "")),
                    kind=kind,
                    description=pe.get("description"),
                    satisfies=list(pe.get("satisfies", [])),
                ))

            # Version is resolved in validate_citations step; use placeholder for now
            grounded = [
                CitationRef(item_id=str(cid), item_version="unknown")
                for cid in item.get("grounded_on", [])
            ]

            candidates.append(SolutionOption(
                option_id=str(uuid.uuid4()),
                operation_id=state["operation_id"],
                title=str(item.get("title", ""))[:120],
                rationale=str(item.get("rationale", ""))[:400],
                grounded_on=grounded,
                satisfies=list(item.get("satisfies", req_ids)),
                proposed_elements=elements,
                advisory=False,
                knowledge_source="knowledge_base" if has_knowledge else "requirements_only",
            ))

    except Exception as exc:
        error_msg = str(exc)
        _logger.error("Generation step failed: %s", exc)

    latency = (time.perf_counter() - start) * 1000
    telemetry.emit_step_span(RecommendationStep(
        operation_id=state["operation_id"],
        step_name="generate",
        correlation_id=state.get("correlation_id"),
        retrieved_knowledge_refs=[f"{e.citation.item_id}@{e.citation.item_version}"
                                   for e in retrieved],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        option_count=len(candidates),
        latency_ms=latency,
        error=error_msg,
    ))

    if error_msg:
        return {**state, "candidate_options": [], "error": error_msg}
    return {**state, "candidate_options": candidates}


async def analyze_tradeoffs_step(
    state: RecommendationState,
    *,
    llm: "LLMClient",
    telemetry: "RecommendationTelemetry",
) -> RecommendationState:
    """Step 3: Analyze trade-offs per option against applicable NFRs and principles."""
    start = time.perf_counter()
    candidates = state.get("candidate_options", [])
    requirements = state.get("requirements", [])
    retrieved = state.get("retrieved_knowledge", [])

    # Applicable NFRs: requirements with quality-attribute keywords
    nfr_criteria = [
        f"[{getattr(r, 'id', '?')}] {getattr(r, 'description', getattr(r, 'title', ''))}"
        for r in requirements
        if _is_quality_requirement(
            getattr(r, "description", getattr(r, "title", ""))
        )
    ]
    # Applicable principles from retrieved knowledge
    principle_criteria = [
        f"{e.item.title}"
        for e in retrieved
        if getattr(e.item, "kind", "") == "principle"
    ]

    all_criteria = nfr_criteria + principle_criteria
    criteria_list = "\n".join(f"- {c}" for c in all_criteria) or "- No specific criteria identified"

    total_input = 0
    total_output = 0

    for option in candidates:
        element_names = ", ".join(pe.name for pe in option.proposed_elements) or "none"
        system = TRADEOFF_SYSTEM_PROMPT
        user = tradeoff_user_prompt(
            option.title, option.rationale, element_names, criteria_list
        )
        try:
            raw = await llm.chat(
                system, user, correlation_id=state.get("correlation_id")
            )
            usage = raw.get("usage", {})
            total_input += usage.get("prompt_tokens", 0)
            total_output += usage.get("completion_tokens", 0)

            content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            data = json.loads(content) if isinstance(content, str) else content
            entries: list[TradeOffEntry] = []
            for te in data.get("trade_offs", []):
                try:
                    stance = TradeOffStance(te.get("stance", "partially_meets"))
                except ValueError:
                    stance = TradeOffStance.PARTIALLY_MEETS
                entries.append(TradeOffEntry(
                    criterion=str(te.get("criterion", "unknown")),
                    stance=stance,
                    rationale=str(te.get("rationale", ""))[:200],
                ))
            option.trade_offs = entries

        except Exception as exc:
            _logger.warning("Trade-off analysis failed for option %s: %s", option.option_id, exc)
            option.trade_offs = []  # empty list; pipeline continues

    latency = (time.perf_counter() - start) * 1000
    telemetry.emit_step_span(RecommendationStep(
        operation_id=state["operation_id"],
        step_name="analyze_tradeoffs",
        correlation_id=state.get("correlation_id"),
        input_tokens=total_input,
        output_tokens=total_output,
        latency_ms=latency,
    ))

    return {**state, "candidate_options": candidates}


def rank_step(
    state: RecommendationState,
    *,
    telemetry: "RecommendationTelemetry",
) -> RecommendationState:
    """Step 4: Deterministic weighted-sum ranking — no LLM call."""
    start = time.perf_counter()
    candidates = state.get("candidate_options", [])
    retrieved = state.get("retrieved_knowledge", [])
    req_ids = set(state.get("requirement_ids", []))
    weights = state.get("ranking_weights", (0.4, 0.3, 0.3))
    w_req, w_principle, w_tradeoff = weights

    principle_ids = {
        e.citation.item_id
        for e in retrieved
        if getattr(e.item, "kind", "") == "principle"
    }

    for option in candidates:
        # Coverage score: fraction of input requirements in option.satisfies
        covered = len(set(option.satisfies) & req_ids)
        option.coverage_score = covered / max(1, len(req_ids))

        # Principle alignment: mean relevance of cited principle items
        option_cited = {ref.item_id for ref in option.grounded_on}
        matching = [
            e.relevance_score for e in retrieved
            if e.citation.item_id in option_cited and e.citation.item_id in principle_ids
        ]
        option.principle_score = sum(matching) / max(1, len(matching)) if matching else 0.0

        # Trade-off score: fraction of assessments that are "meets"
        if option.trade_offs:
            meets = sum(1 for t in option.trade_offs if t.stance == TradeOffStance.MEETS)
            option.tradeoff_score = meets / len(option.trade_offs)
        else:
            option.tradeoff_score = 0.5  # neutral when no trade-offs assessed

        option.ranking_score = (
            w_req * option.coverage_score
            + w_principle * option.principle_score
            + w_tradeoff * option.tradeoff_score
        )

    sorted_candidates = sorted(candidates, key=lambda o: o.ranking_score, reverse=True)
    for i, opt in enumerate(sorted_candidates, 1):
        opt.rank = i

    latency = (time.perf_counter() - start) * 1000
    telemetry.emit_step_span(RecommendationStep(
        operation_id=state["operation_id"],
        step_name="rank",
        correlation_id=state.get("correlation_id"),
        option_count=len(sorted_candidates),
        latency_ms=latency,
    ))

    return {**state, "ranked_options": sorted_candidates}


async def validate_citations_step(
    state: RecommendationState,
    *,
    knowledge_retrieval: "KnowledgeRetrieval",
    telemetry: "RecommendationTelemetry",
) -> RecommendationState:
    """Step 5: Verify citations; mark options advisory if any citation unresolvable."""
    start = time.perf_counter()
    ranked = state.get("ranked_options", [])
    advisory_count = 0

    for option in ranked:
        # ADP-SPEC-019: requirements_only options are never advisory — skip citation check
        if getattr(option, "knowledge_source", "knowledge_base") == "requirements_only":
            continue

        if not option.grounded_on:
            option.advisory = True
            advisory_count += 1
            continue

        all_valid = True
        validated_refs: list[CitationRef] = []
        for ref in option.grounded_on:
            try:
                resolved = await knowledge_retrieval.resolve_citation(ref)
                if resolved is None:
                    all_valid = False
                    _logger.warning(
                        "Citation %s@%s not found in knowledge index",
                        ref.item_id, ref.item_version
                    )
                else:
                    # Use actual version from resolved item
                    validated_refs.append(
                        CitationRef(item_id=ref.item_id, item_version=resolved.version)
                    )
            except Exception as exc:
                _logger.warning("Citation resolution failed for %s: %s", ref.item_id, exc)
                all_valid = False

        if not all_valid:
            option.advisory = True
            advisory_count += 1
        else:
            option.grounded_on = validated_refs

    latency = (time.perf_counter() - start) * 1000
    telemetry.emit_step_span(RecommendationStep(
        operation_id=state["operation_id"],
        step_name="validate_citations",
        correlation_id=state.get("correlation_id"),
        advisory_count=advisory_count,
        latency_ms=latency,
    ))

    return {**state, "validated_options": ranked}
