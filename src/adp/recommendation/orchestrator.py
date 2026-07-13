"""RecommendationOrchestrator — LangGraph pipeline for ADP solution option generation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from adp.recommendation.models import (
    RecommendationState,
    SolutionOption,
)
from adp.recommendation.steps import (
    analyze_tradeoffs_step,
    generate_step,
    rank_step,
    retrieve_step,
    validate_citations_step,
)
from adp.recommendation.telemetry import RecommendationTelemetry

if TYPE_CHECKING:
    from adp.knowledge import KnowledgeRetrieval
    from adp.llm.client import LLMClient
    from adp.models import Element
    from adp.store import DesignStore

_logger = logging.getLogger("adp.recommendation")


class RecommendationOrchestrator:
    """Coordinates the five-step LangGraph recommendation pipeline."""

    def __init__(
        self,
        llm: "LLMClient",
        knowledge_retrieval: "KnowledgeRetrieval",
        design_store: "DesignStore",
        option_count: int = 3,
        ranking_weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
        telemetry: RecommendationTelemetry | None = None,
    ) -> None:
        self._llm = llm
        self._knowledge = knowledge_retrieval
        self._store = design_store
        self._option_count = option_count
        self._ranking_weights = ranking_weights
        self._telemetry = telemetry or RecommendationTelemetry()
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph StateGraph (4 nodes; analyze_tradeoffs added later)."""
        from langgraph.graph import END, StateGraph

        t = self._telemetry
        kr = self._knowledge
        llm = self._llm
        oc = self._option_count
        rw = self._ranking_weights

        async def _retrieve(state: RecommendationState) -> RecommendationState:
            return await retrieve_step(state, knowledge_retrieval=kr, telemetry=t)

        async def _generate(state: RecommendationState) -> RecommendationState:
            return await generate_step(state, llm=llm, telemetry=t, option_count=oc)

        async def _tradeoffs(state: RecommendationState) -> RecommendationState:
            return await analyze_tradeoffs_step(state, llm=llm, telemetry=t)

        def _rank(state: RecommendationState) -> RecommendationState:
            # Bind ranking_weights into state so rank_step can read them
            state = {**state, "ranking_weights": rw}
            return rank_step(state, telemetry=t)

        async def _validate(state: RecommendationState) -> RecommendationState:
            return await validate_citations_step(state, knowledge_retrieval=kr, telemetry=t)

        graph = StateGraph(RecommendationState)
        graph.add_node("retrieve", _retrieve)
        graph.add_node("generate", _generate)
        graph.add_node("analyze_tradeoffs", _tradeoffs)
        graph.add_node("rank", _rank)
        graph.add_node("validate_citations", _validate)

        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", "analyze_tradeoffs")
        graph.add_edge("analyze_tradeoffs", "rank")
        graph.add_edge("rank", "validate_citations")
        graph.add_edge("validate_citations", END)

        return graph.compile()

    async def run(
        self,
        operation_id: str,
        design_id: str,
        requirement_ids: list[str],
        operation_store: Any,
        correlation_id: str | None = None,
    ) -> None:
        """Execute the five-step pipeline as a background task (ADP-SPEC-024).

        operation_store is an OperationStore instance.
        """
        from adp.api.routers.recommend import _option_to_dict

        await operation_store.update(operation_id, status="running")

        validated_options: list[SolutionOption] = []
        error_msg: str | None = None

        try:
            design = await self._store.get(design_id)
            req_id_set = set(requirement_ids)
            requirements = [r for r in design.requirements if r.id in req_id_set]

            initial_state: RecommendationState = {
                "operation_id": operation_id,
                "design_id": design_id,
                "requirement_ids": requirement_ids,
                "requirements": requirements,
                "retrieved_knowledge": [],
                "candidate_options": [],
                "ranked_options": [],
                "validated_options": [],
                "correlation_id": correlation_id,
                "error": None,
                "option_count": self._option_count,
                "ranking_weights": self._ranking_weights,
            }

            final_state = await self._graph.ainvoke(initial_state)
            validated_options = final_state.get("validated_options", [])
            pipeline_error = final_state.get("error")

            if pipeline_error:
                raise RuntimeError(pipeline_error)

            citations_present = any(not opt.advisory for opt in validated_options)
            suffix = "s" if len(validated_options) != 1 else ""
            result_summary = f"{len(validated_options)} option{suffix} generated"

            # Serialize SolutionOption objects for persistent storage (ADP-SPEC-024)
            serialized_options = {opt.option_id: _option_to_dict(opt) for opt in validated_options}
            await operation_store.update(operation_id, status="completed", payload_patch={
                "options": serialized_options,
                "result_summary": result_summary,
                "citations_present": citations_present,
            })

        except Exception as exc:
            error_msg = str(exc)
            await operation_store.update(operation_id, status="failed", payload_patch={
                "error_description": error_msg,
                "citations_present": False,
            })
            _logger.error(
                json.dumps({
                    "operation": "recommendation.pipeline_failed",
                    "operation_id": operation_id,
                    "error": error_msg,
                })
            )
        finally:
            current_op = await operation_store.get(operation_id) or {}
            _logger.info(
                json.dumps({
                    "operation": "recommendation.pipeline",
                    "operation_id": operation_id,
                    "option_count": len(validated_options),
                    "advisory_count": sum(1 for o in validated_options if o.advisory),
                    "status": current_op.get("status"),
                })
            )

    async def materialize_option(
        self,
        option_id: str,
        operation_id: str,
        accepting_actor: str,
        operation_store: Any,
        design_id: str,
        *,
        advisory_acknowledged: bool = False,
    ) -> list["Element"]:
        """Accept one option and materialize its ProposedElements into the design store."""
        from adp.api.routers.recommend import _dict_to_option
        from adp.models import Element

        op = await operation_store.get(operation_id) or {}
        options_raw: dict = op.get("options", {})
        option_raw = options_raw.get(option_id)

        if option_raw is None:
            raise ValueError(f"Option {option_id!r} not found in operation {operation_id!r}")

        # Reconstruct SolutionOption from stored dict (ADP-SPEC-024)
        option = _dict_to_option(option_raw) if isinstance(option_raw, dict) else option_raw

        if option.status != "pending":
            raise ValueError(f"Option {option_id!r} is not pending (status={option.status})")
        if option.advisory and not advisory_acknowledged:
            raise ValueError(
                f"Option {option_id!r} is advisory — pass advisory_acknowledged=True to confirm"
            )

        design = await self._store.get(design_id)

        created_elements: list[Element] = []
        for proposed in option.proposed_elements:
            elm_id = f"ELM-{len(design.elements) + len(created_elements) + 1:03d}"
            element = Element(
                id=elm_id,
                name=proposed.name,
                kind=proposed.kind,
                description=proposed.description,
                satisfies=proposed.satisfies,
                provenance=option_id,
            )
            design.elements.append(element)
            created_elements.append(element)

        # Write audit entry (QG-13 / FR-004)
        from adp.audit.writer import next_audit_id as _next_audit_id
        audit_entry_id = _next_audit_id(design)
        from adp.models import AuditEntry as _AE

        audit_entry = _AE(
            id=audit_entry_id,
            actor=accepting_actor,
            action="accept-recommendation",
            affected_entity=option_id,
            summary=f"Accepted recommendation option {option_id}: {option.title[:60]}",
            timestamp=datetime.now(timezone.utc),
            origin="human",
        )
        design.audit_log.append(audit_entry)
        await self._store.save(design, actor=accepting_actor)

        # Update option status via OperationStore (ADP-SPEC-024)
        await operation_store.update_option_status(operation_id, option_id, "accepted")

        _logger.info(
            json.dumps({
                "operation": "recommendation.accept_option",
                "option_id": option_id,
                "element_count": len(created_elements),
                "actor": accepting_actor,
            })
        )
        return created_elements
