"""Shared provenance helpers for the Agent Review toolkit (ADP-SPEC-039, ART-IX/ART-XI).

Business capabilities (and applications) have no `design_id` -- `write_audit_record`
requires a real `ArchitectureDescription` + `DesignStore`, neither of which exists
for a capability. Consistent with the rest of `adp.business`/`adp.application`
(ART-IX is SHOULD there, satisfied by structured logging), `write_suggestion_audit`
writes a structured log line, not a real `AuditEntry`. The durable, queryable
provenance record for an accepted suggestion is `write_suggestion_reasoning`'s
`llm_reasoning_log` row -- a genuine append-only database record.
"""

from __future__ import annotations

import logging


def write_suggestion_audit(
    logger: logging.Logger,
    *,
    actor: str,
    action: str,
    affected_entity: str,
    summary: str,
    operation_id: str,
    suggestion_id: str,
) -> None:
    """Structured log line for an accepted suggestion's write.

    Mirrors adp.business.router's existing logger.info() convention
    (e.g. "business.capability.update id=%s actor=%s") with origin=ai and
    the operation/suggestion id added for traceability (ART-XI).
    """
    logger.info(
        "%s id=%s actor=%s origin=ai operation_id=%s suggestion_id=%s summary=%r",
        action,
        affected_entity,
        actor,
        operation_id,
        suggestion_id,
        summary,
    )


async def write_suggestion_reasoning(
    *,
    operation_id: str,
    suggestion_id: str,
    step_name: str,
    model_id: str,
    reasoning_text: str,
    prompt: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Write one llm_reasoning_log row for an accepted suggestion's rationale.

    Fire-and-forget: callers should wrap this in asyncio.create_task(), mirroring
    adp.recommendation.steps._fire_reasoning_write. Silently swallows errors so
    DB latency/failure on this durable-but-secondary trail never blocks acceptance.
    """
    try:
        from adp.api.deps import get_reasoning_store
        from adp.store.reasoning import ReasoningRecord, _hash_prompt

        store = await get_reasoning_store()
        await store.write(
            ReasoningRecord(
                operation_id=operation_id,
                option_id=suggestion_id,
                step_name=step_name,
                model_id=model_id,
                reasoning_text=reasoning_text,
                prompt_hash=_hash_prompt(prompt),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )
    except Exception as exc:  # noqa: BLE001 -- fire-and-forget, never block acceptance
        logging.getLogger("adp.agents.provenance").debug("reasoning write skipped: %s", exc)
