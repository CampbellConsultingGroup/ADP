"""LLM critic functions for the validation pipeline (ADP-SPEC-008).

Critic order: structural (pre-check) → standards, principles, pattern_fit, consistency (LLM).
All LLM critics follow the same pattern: retrieve → prompt → parse → emit span.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

from adp.knowledge.schema import CitationRef, RetrievalQuery
from adp.validation.models import (
    CriticOutput,
    Finding,
    FindingSeverity,
)
from adp.validation.prompts import (
    CONSISTENCY_SYSTEM,
    PATTERN_FIT_SYSTEM,
    PRINCIPLES_SYSTEM,
    STANDARDS_SYSTEM,
    consistency_user_prompt,
    pattern_fit_user_prompt,
    principles_user_prompt,
    standards_user_prompt,
)

if TYPE_CHECKING:
    from adp.knowledge import KnowledgeRetrieval
    from adp.llm.client import LLMClient
    from adp.validation.telemetry import ValidationTelemetry

_logger = logging.getLogger("adp.validation")

# Score → severity mapping (deterministic — no LLM involvement)
_SCORE_SEVERITY: list[tuple[float, FindingSeverity]] = [
    (0.1, FindingSeverity.CRITICAL),   # score <= 0.1 → critical
    (0.4, FindingSeverity.MAJOR),      # score <= 0.4 → major
    (0.6, FindingSeverity.MAJOR),      # score <= 0.6 → major
    (0.9, FindingSeverity.MINOR),      # score <= 0.9 → minor
]


def _severity_from_score(score: float) -> FindingSeverity:
    for threshold, severity in _SCORE_SEVERITY:
        if score <= threshold:
            return severity
    return FindingSeverity.MINOR


async def _llm_critic(
    critic_name: str,
    system_prompt: str,
    user_prompt: str,
    knowledge_entries: list,  # type: ignore[type-arg]
    operation_id: str,
    llm: "LLMClient",
    telemetry: "ValidationTelemetry",
    correlation_id: str | None = None,
) -> CriticOutput:
    """Common LLM critic logic — call LLM, parse findings, emit span."""
    start = time.perf_counter()
    knowledge_refs = [
        f"{e.citation.item_id}@{e.citation.item_version}" for e in knowledge_entries
    ]
    knowledge_id_set = {e.citation.item_id for e in knowledge_entries}
    knowledge_version_map = {
        e.citation.item_id: e.citation.item_version for e in knowledge_entries
    }

    input_tokens = output_tokens = 0
    findings: list[Finding] = []
    score: float | None = None
    error_msg: str | None = None

    try:
        combined = f"SYSTEM: {system_prompt}\n\nUSER: {user_prompt}"
        raw = await llm.extract(combined, correlation_id)

        usage = raw.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        data = json.loads(content) if isinstance(content, str) else content

        raw_score = float(data.get("score", 1.0))
        score = max(0.0, min(1.0, raw_score))

        if score < 1.0:
            severity = _severity_from_score(score)
            for item in data.get("findings", []):
                cited_id = str(item.get("cited_id", "")) or None
                citation: CitationRef | None = None
                actual_severity = severity

                if cited_id and cited_id in knowledge_id_set:
                    citation = CitationRef(
                        item_id=cited_id,
                        item_version=knowledge_version_map.get(cited_id, "unknown"),
                    )
                elif cited_id:
                    # Unresolvable citation → advisory
                    actual_severity = FindingSeverity.ADVISORY
                    _logger.warning(
                        "Critic %s cited unknown item %r — marking advisory",
                        critic_name, cited_id,
                    )

                findings.append(Finding(
                    finding_id=str(uuid.uuid4()),
                    operation_id=operation_id,
                    critic_name=critic_name,
                    severity=actual_severity,
                    description=str(item.get("description", ""))[:400],
                    element_id=item.get("element_id") or None,
                    citation=citation,
                    score=score,
                ))

    except Exception as exc:
        error_msg = str(exc)
        _logger.error("Critic %s failed: %s", critic_name, exc)

    latency = (time.perf_counter() - start) * 1000
    output = CriticOutput(
        critic_name=critic_name,
        score=score,
        findings=findings,
        retrieved_knowledge_refs=knowledge_refs,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency,
        error=error_msg,
    )
    telemetry.emit_span(output, correlation_id)
    return output


# ── Structural critic (pure Python, no LLM) ──────────────────────────────────


def structural_critic(
    design: Any,
    operation_id: str,
    telemetry: "ValidationTelemetry",
    correlation_id: str | None = None,
) -> CriticOutput:
    """Detect orphan elements and dangling relationship references (FR-005 / QG-16)."""
    start = time.perf_counter()
    findings: list[Finding] = []
    elements = getattr(design, "elements", [])
    relationships = getattr(design, "relationships", [])
    element_ids = {e.id for e in elements}

    for element in elements:
        satisfies = getattr(element, "satisfies", None) or []
        if not satisfies:
            findings.append(Finding(
                finding_id=str(uuid.uuid4()),
                operation_id=operation_id,
                critic_name="structural",
                severity=FindingSeverity.CRITICAL,
                description="Orphan element — satisfies list is empty; no requirement satisfied",
                element_id=element.id,
                citation=None,
            ))

    for rel in relationships:
        target = getattr(rel, "target", None)
        if target and target not in element_ids:
            findings.append(Finding(
                finding_id=str(uuid.uuid4()),
                operation_id=operation_id,
                critic_name="structural",
                severity=FindingSeverity.CRITICAL,
                description=(
                    f"Dangling reference — Relationship {rel.id!r}"
                    f" targets {target!r} which does not exist"
                ),
                element_id=None,
                citation=None,
            ))

    latency = (time.perf_counter() - start) * 1000
    output = CriticOutput(
        critic_name="structural",
        score=None,
        findings=findings,
        latency_ms=latency,
    )
    telemetry.emit_span(output, correlation_id)
    return output


# ── LLM critics ───────────────────────────────────────────────────────────────


async def standards_critic(
    design: Any,
    knowledge_retrieval: "KnowledgeRetrieval",
    llm: "LLMClient",
    telemetry: "ValidationTelemetry",
    operation_id: str,
    correlation_id: str | None = None,
) -> CriticOutput:

    entries = []
    try:
        result = await knowledge_retrieval.hybrid_search(
            RetrievalQuery(query_text="standards compliance", limit=10)
        )
        entries = [e for e in result.items if getattr(e.item, "kind", "") == "standard"]
    except Exception as exc:
        _logger.warning("Standards retrieval failed: %s", exc)

    return await _llm_critic(
        critic_name="standards",
        system_prompt=STANDARDS_SYSTEM,
        user_prompt=standards_user_prompt(design, entries),
        knowledge_entries=entries,
        operation_id=operation_id,
        llm=llm,
        telemetry=telemetry,
        correlation_id=correlation_id,
    )


async def principles_critic(
    design: Any,
    knowledge_retrieval: "KnowledgeRetrieval",
    llm: "LLMClient",
    telemetry: "ValidationTelemetry",
    operation_id: str,
    correlation_id: str | None = None,
) -> CriticOutput:
    entries = []
    try:
        result = await knowledge_retrieval.hybrid_search(
            RetrievalQuery(query_text="architecture principles", limit=10)
        )
        entries = [e for e in result.items if getattr(e.item, "kind", "") == "principle"]
    except Exception as exc:
        _logger.warning("Principles retrieval failed: %s", exc)

    return await _llm_critic(
        critic_name="principles",
        system_prompt=PRINCIPLES_SYSTEM,
        user_prompt=principles_user_prompt(design, entries),
        knowledge_entries=entries,
        operation_id=operation_id,
        llm=llm,
        telemetry=telemetry,
        correlation_id=correlation_id,
    )


async def pattern_fit_critic(
    design: Any,
    knowledge_retrieval: "KnowledgeRetrieval",
    llm: "LLMClient",
    telemetry: "ValidationTelemetry",
    operation_id: str,
    correlation_id: str | None = None,
) -> CriticOutput:
    entries = []
    try:
        result = await knowledge_retrieval.hybrid_search(
            RetrievalQuery(query_text="architecture patterns", limit=10)
        )
        entries = [e for e in result.items if getattr(e.item, "kind", "") == "pattern"]
    except Exception as exc:
        _logger.warning("Pattern retrieval failed: %s", exc)

    return await _llm_critic(
        critic_name="pattern_fit",
        system_prompt=PATTERN_FIT_SYSTEM,
        user_prompt=pattern_fit_user_prompt(design, entries),
        knowledge_entries=entries,
        operation_id=operation_id,
        llm=llm,
        telemetry=telemetry,
        correlation_id=correlation_id,
    )


async def consistency_critic(
    design: Any,
    knowledge_retrieval: "KnowledgeRetrieval",
    llm: "LLMClient",
    telemetry: "ValidationTelemetry",
    operation_id: str,
    correlation_id: str | None = None,
) -> CriticOutput:
    entries = []
    try:
        result = await knowledge_retrieval.hybrid_search(
            RetrievalQuery(query_text="approved solutions prior", limit=10)
        )
        entries = [e for e in result.items if getattr(e.item, "kind", "") == "prior_solution"]
    except Exception as exc:
        _logger.warning("Consistency retrieval failed: %s", exc)

    return await _llm_critic(
        critic_name="consistency",
        system_prompt=CONSISTENCY_SYSTEM,
        user_prompt=consistency_user_prompt(design, entries),
        knowledge_entries=entries,
        operation_id=operation_id,
        llm=llm,
        telemetry=telemetry,
        correlation_id=correlation_id,
    )
