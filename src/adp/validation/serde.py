"""Serialization helpers for Verdict/Finding (ADP-SPEC-008).

Lives in the domain package (not a router) so both `ValidationOrchestrator`
and the `validate` router import from here — deliberately unlike
`adp.api.routers.recommend`'s `_option_to_dict`/`_dict_to_option`, which are
router-hosted and force `adp.recommendation.orchestrator` to import from its
own router.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from adp.knowledge.schema import CitationRef
from adp.validation.models import (
    CriticOutput,
    Finding,
    FindingSeverity,
    GatingThreshold,
    Verdict,
    VerdictStatus,
)


def finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "finding_id": f.finding_id,
        "operation_id": f.operation_id,
        "critic_name": f.critic_name,
        "severity": f.severity.value,
        "description": f.description,
        "element_id": f.element_id,
        "citation": (
            {"item_id": f.citation.item_id, "item_version": f.citation.item_version}
            if f.citation else None
        ),
        "score": f.score,
    }


def dict_to_finding(d: dict[str, Any]) -> Finding:
    citation = None
    if d.get("citation"):
        citation = CitationRef(
            item_id=d["citation"]["item_id"], item_version=d["citation"]["item_version"]
        )
    return Finding(
        finding_id=d["finding_id"],
        operation_id=d["operation_id"],
        critic_name=d["critic_name"],
        severity=FindingSeverity(d["severity"]),
        description=d["description"],
        element_id=d.get("element_id"),
        citation=citation,
        score=d.get("score"),
    )


def critic_output_to_dict(c: CriticOutput) -> dict[str, Any]:
    return {
        "critic_name": c.critic_name,
        "score": c.score,
        "findings": [finding_to_dict(f) for f in c.findings],
        "retrieved_knowledge_refs": list(c.retrieved_knowledge_refs or []),
        "input_tokens": c.input_tokens,
        "output_tokens": c.output_tokens,
        "cost_usd": c.cost_usd,
        "latency_ms": c.latency_ms,
        "error": c.error,
    }


def dict_to_critic_output(d: dict[str, Any]) -> CriticOutput:
    return CriticOutput(
        critic_name=d["critic_name"],
        score=d.get("score"),
        findings=[dict_to_finding(f) for f in d.get("findings", [])],
        retrieved_knowledge_refs=list(d.get("retrieved_knowledge_refs", [])),
        input_tokens=d.get("input_tokens", 0),
        output_tokens=d.get("output_tokens", 0),
        cost_usd=d.get("cost_usd", 0.0),
        latency_ms=d.get("latency_ms", 0.0),
        error=d.get("error"),
    )


def thresholds_to_dict(t: GatingThreshold) -> dict[str, Any]:
    return {
        "max_critical": t.max_critical,
        "max_major": t.max_major,
        "max_minor": t.max_minor,
        "version": t.version,
    }


def dict_to_thresholds(d: dict[str, Any]) -> GatingThreshold:
    return GatingThreshold(
        max_critical=d.get("max_critical", 0),
        max_major=d.get("max_major", 3),
        max_minor=d.get("max_minor", 10),
        version=d.get("version", "1.0.0"),
    )


def verdict_to_dict(v: Verdict) -> dict[str, Any]:
    return {
        "verdict_id": v.verdict_id,
        "operation_id": v.operation_id,
        "design_id": v.design_id,
        "design_version": v.design_version,
        "status": v.status.value,
        "composite_score": v.composite_score,
        "findings": [finding_to_dict(f) for f in v.findings],
        "thresholds_snapshot": thresholds_to_dict(v.thresholds_snapshot),
        "critic_outputs": [critic_output_to_dict(c) for c in v.critic_outputs],
        "citations_present": v.citations_present,
        "overridden_by": v.overridden_by,
        "override_at": v.override_at.isoformat() if v.override_at else None,
        "override_justification": v.override_justification,
        "audit_entry_id": v.audit_entry_id,
    }


def dict_to_verdict(d: dict[str, Any]) -> Verdict:
    override_at = datetime.fromisoformat(d["override_at"]) if d.get("override_at") else None
    return Verdict(
        verdict_id=d["verdict_id"],
        operation_id=d["operation_id"],
        design_id=d["design_id"],
        design_version=d["design_version"],
        status=VerdictStatus(d["status"]),
        composite_score=d.get("composite_score"),
        findings=[dict_to_finding(f) for f in d.get("findings", [])],
        thresholds_snapshot=dict_to_thresholds(d.get("thresholds_snapshot", {})),
        critic_outputs=[dict_to_critic_output(c) for c in d.get("critic_outputs", [])],
        citations_present=d.get("citations_present", False),
        overridden_by=d.get("overridden_by"),
        override_at=override_at,
        override_justification=d.get("override_justification"),
        audit_entry_id=d.get("audit_entry_id"),
    )
