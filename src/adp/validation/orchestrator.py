"""ValidationOrchestrator — fan-out validation pipeline (ADP-SPEC-008).

Architecture:
  structural_critic (pre-check, pure Python)
  → asyncio.gather(standards, principles, pattern_fit, consistency)
  → aggregate()
  → gate()
  → Verdict stored in operation_store

`operation_store` is a real, DB-backed OperationStore instance (ADP-SPEC-024),
matching the intake/recommendation orchestrators' contract — not a raw dict.
Long-term verdict persistence (NFR-002) is provided by ADP-3ei's
`validation_verdicts`/`validation_findings` tables via `capture_store`, which
survive the 24h operation TTL (durable, design-linked, queryable).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from adp.validation.aggregator import aggregate
from adp.validation.critics import (
    consistency_critic,
    pattern_fit_critic,
    principles_critic,
    standards_critic,
    structural_critic,
)
from adp.validation.gate import gate
from adp.validation.models import (
    CriticOutput,
    GatingThreshold,
    Verdict,
    VerdictStatus,
)
from adp.validation.serde import dict_to_verdict, verdict_to_dict
from adp.validation.telemetry import ValidationTelemetry

if TYPE_CHECKING:
    from adp.knowledge import KnowledgeRetrieval
    from adp.llm.client import LLMClient
    from adp.store import DesignStore

_logger = logging.getLogger("adp.validation")


class ValidationOrchestrator:
    """Coordinates the full validation pipeline."""

    def __init__(
        self,
        llm: "LLMClient",
        knowledge_retrieval: "KnowledgeRetrieval",
        design_store: "DesignStore",
        thresholds: GatingThreshold | None = None,
        telemetry: ValidationTelemetry | None = None,
        capture_store: Any | None = None,
    ) -> None:
        self._llm = llm
        self._knowledge = knowledge_retrieval
        self._store = design_store
        self._thresholds = thresholds or GatingThreshold()
        self._telemetry = telemetry or ValidationTelemetry()
        self._capture = capture_store

    async def run(
        self,
        operation_id: str,
        design_id: str,
        operation_store: Any,
        design_version: int | None = None,
        correlation_id: str | None = None,
        actor: str = "system",
    ) -> None:
        """Execute the full validation pipeline as a background task (ADP-SPEC-024).

        operation_store is an OperationStore instance.
        """
        await operation_store.update(operation_id, status="running")

        verdict: Verdict | None = None
        error_msg: str | None = None
        payload_patch: dict[str, Any] = {}
        final_status = "running"

        try:
            design = await self._store.get(design_id, version=design_version)

            # Get design version number from store
            versions = await self._store.list_versions(design_id)
            ver_num = len(versions) if versions else 1

            critic_outputs: list[CriticOutput] = []

            # Step 1: Structural pre-check (pure Python, no LLM)
            struct_output = structural_critic(
                design, operation_id, self._telemetry, correlation_id
            )
            critic_outputs.append(struct_output)
            structural_passed = not any(True for f in struct_output.findings)

            # Step 2: LLM critics (fan-out, only if structural passed)
            llm_critics_ran_successfully = False
            if structural_passed:
                kr, llm, tel, oid, cid = (
                    self._knowledge, self._llm, self._telemetry, operation_id, correlation_id
                )
                llm_outputs = await asyncio.gather(
                    standards_critic(design, kr, llm, tel, oid, cid),
                    principles_critic(design, kr, llm, tel, oid, cid),
                    pattern_fit_critic(design, kr, llm, tel, oid, cid),
                    consistency_critic(design, kr, llm, tel, oid, cid),
                    return_exceptions=False,
                )
                critic_outputs.extend(llm_outputs)
                llm_critics_ran_successfully = True

            # Step 3: Aggregate
            # structural failure → treat as "ran" (gate on structural findings)
            # LLM all-failed → indeterminate; structural failed → fail
            llm_critics_ran = structural_passed and llm_critics_ran_successfully
            all_findings, composite_score, citations_present = aggregate(
                critic_outputs, operation_id, self._telemetry, correlation_id
            )

            # Step 4: Gate (pure function, deterministic — ART-X / QG-15)
            # If structural failed, skip LLM critics but still gate on structural findings
            # (structural failures always produce critical findings → gate returns "fail")
            # Only "indeterminate" when LLM critics were expected but ALL failed at runtime
            gate_result = gate(
                all_findings,
                self._thresholds,
                llm_critics_ran=True if not structural_passed else llm_critics_ran,
            )

            # Emit gate telemetry span
            gate_output = CriticOutput(
                critic_name="gate",
                score=composite_score,
                latency_ms=0.0,
            )
            if gate_result == "indeterminate":
                final_status = "failed"
                payload_patch["error_description"] = (
                    "All LLM critics failed to run; verdict is indeterminate"
                )
            self._telemetry.emit_span(gate_output, correlation_id)

            # Build verdict
            status_map = {
                "pass": VerdictStatus.PASS,
                "fail": VerdictStatus.FAIL,
                "indeterminate": VerdictStatus.INDETERMINATE,
            }
            verdict = Verdict(
                verdict_id=str(uuid.uuid4()),
                operation_id=operation_id,
                design_id=design_id,
                design_version=ver_num,
                status=status_map[gate_result],
                composite_score=composite_score,
                findings=all_findings,
                thresholds_snapshot=self._thresholds,
                critic_outputs=critic_outputs,
                citations_present=citations_present,
            )

            # Bridge citations_present to ADP-SPEC-003 ART-VII gate
            payload_patch["span"] = {"citations_present": citations_present}
            payload_patch["verdict"] = verdict_to_dict(verdict)
            if gate_result != "indeterminate":
                final_status = "completed"
            suffix = "pass" if gate_result == "pass" else gate_result.upper()
            finding_count = len([f for f in all_findings if f.severity.value != "advisory"])
            payload_patch["result_summary"] = f"{suffix} — {finding_count} blocking findings"

            await operation_store.update(
                operation_id, status=final_status, payload_patch=payload_patch,
            )

            # ADP-3ei: durable, design-linked capture of the verdict + findings
            if self._capture is not None:
                model_id = getattr(self._llm, "_model", None)
                await self._capture.record_verdict(
                    verdict, design_id=design_id, actor=actor, model_id=model_id,
                )

        except Exception as exc:
            error_msg = str(exc)
            await operation_store.update(operation_id, status="failed", payload_patch={
                "error_description": error_msg,
            })
            _logger.error(
                json.dumps({
                    "operation": "validation.pipeline_failed",
                    "operation_id": operation_id,
                    "error": error_msg,
                })
            )
        finally:
            current_op = await operation_store.get(operation_id) or {}
            _logger.info(
                json.dumps({
                    "operation": "validation.pipeline",
                    "operation_id": operation_id,
                    "design_id": design_id,
                    "status": current_op.get("status"),
                    "finding_count": len(verdict.findings) if verdict else 0,
                    "citations_present": current_op.get("span", {}).get("citations_present", False),
                })
            )

    async def override_verdict(
        self,
        verdict_id: str,
        operation_id: str,
        reviewing_actor: str,
        justification: str,
        operation_store: Any,
        design_id: str,
    ) -> None:
        """Override a failing verdict with recorded justification (FR-006 / QG-13)."""
        from adp.audit.writer import next_audit_id as _next_audit_id
        from adp.models import AuditEntry as _AE

        op = await operation_store.get(operation_id) or {}
        verdict_data = op.get("verdict")
        verdict: Verdict | None = (
            dict_to_verdict(verdict_data) if isinstance(verdict_data, dict) else verdict_data
        )

        if verdict is None:
            raise ValueError(f"No verdict found in operation {operation_id!r}")
        if verdict.status != VerdictStatus.FAIL:
            raise ValueError(
                f"Only 'fail' verdicts can be overridden; "
                f"current status is {verdict.status!r}"
            )
        if not justification or not justification.strip():
            raise ValueError("override justification must be non-empty (FR-006)")

        verdict.status = VerdictStatus.OVERRIDDEN
        verdict.overridden_by = reviewing_actor
        verdict.override_at = datetime.now(timezone.utc)
        verdict.override_justification = justification.strip()

        # Write audit entry (QG-13 / FR-006)
        design = await self._store.get(design_id)
        audit_entry_id = _next_audit_id(design)
        audit_entry = _AE(
            id=audit_entry_id,
            actor=reviewing_actor,
            action="override-validation-verdict",
            affected_entity=verdict.verdict_id,
            summary=f"Override verdict {verdict.verdict_id[:8]}: {justification[:100]}",
            timestamp=datetime.now(timezone.utc),
            origin="human",
        )
        design.audit_log.append(audit_entry)
        await self._store.save(design, actor=reviewing_actor)

        verdict.audit_entry_id = audit_entry_id

        await operation_store.update(
            operation_id, payload_patch={"verdict": verdict_to_dict(verdict)},
        )

        # ADP-3ei: durable override capture — awaited inline, raises on failure
        # (a decision-path write, not fire-and-forget).
        if self._capture is not None:
            await self._capture.record_override(
                verdict.verdict_id,
                overridden_by=reviewing_actor,
                override_at=verdict.override_at,
                justification=verdict.override_justification,
                audit_entry_id=audit_entry_id,
            )

        _logger.info(
            json.dumps({
                "operation": "validation.override_verdict",
                "verdict_id": verdict.verdict_id,
                "actor": reviewing_actor,
            })
        )
