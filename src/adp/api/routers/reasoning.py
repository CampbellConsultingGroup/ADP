"""LLM Reasoning read API — ADP-SPEC-027.

GET /api/v1/reasoning?operation_id=&option_id=  → list reasoning records

prompt_hash is intentionally excluded from responses — it is an internal audit field.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/v1/reasoning", tags=["reasoning"])


async def _get_reasoning_store():  # type: ignore[return]
    from adp.api.deps import get_reasoning_store
    return await get_reasoning_store()


class ReasoningResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    option_id: str | None
    step_name: str
    model_id: str
    reasoning_text: str
    truncated: bool
    input_tokens: int
    output_tokens: int
    created_at: datetime


class ReasoningListResponse(BaseModel):
    records: list[ReasoningResponse]


@router.get("", response_model=ReasoningListResponse, status_code=200)
async def list_reasoning(
    operation_id: str = Query(..., description="Filter by operation ID"),
    option_id: str | None = Query(default=None, description="Optionally filter by option ID"),
    store=Depends(_get_reasoning_store),
) -> ReasoningListResponse:
    """Return immutable reasoning records for an operation (ADP-SPEC-027 FR-008/009).

    Records are sorted by created_at ascending.
    prompt_hash is excluded from the response — it is an internal audit field.
    """
    rows = await store.list_for_operation(operation_id, option_id=option_id)
    return ReasoningListResponse(
        records=[ReasoningResponse(**r) for r in rows]
    )
