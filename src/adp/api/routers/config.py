"""LLM configuration endpoints — available models and active model selection.

GET /api/v1/config/models   — list all available Anthropic models
GET /api/v1/config/llm      — get current LLM configuration
PUT /api/v1/config/llm      — choose the model for extraction, recommendations, validation

The model choices are stored in the database (ADP-blp.13); the API key is deploy-time only.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from adp.api.common import session_dependency
from adp.auth.actor import actor_of
from adp.llm import settings as llm_settings

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])

# ── Available Anthropic models ────────────────────────────────────────────────

ANTHROPIC_MODELS = [
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "description": "Fast, capable — best for most extraction and recommendation tasks.",
        "tier": "standard",
        "context_window": 200000,
        "recommended_for": ["extraction", "recommendations"],
    },
    {
        "id": "claude-opus-4-8",
        "name": "Claude Opus 4.8",
        "description": "Most capable model — highest quality for complex architectural reasoning.",
        "tier": "premium",
        "context_window": 200000,
        "recommended_for": ["recommendations"],
    },
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "description": "Fastest and most economical — ideal for simple extraction tasks.",
        "tier": "lite",
        "context_window": 200000,
        "recommended_for": ["extraction"],
    },
    {
        "id": "claude-fable-5",
        "name": "Claude Fable 5",
        "description": "Latest generation with enhanced reasoning capabilities.",
        "tier": "premium",
        "context_window": 200000,
        "recommended_for": ["recommendations"],
    },
]

# ── Where the settings live (ADP-blp.13) ──────────────────────────────────────
# The model choices are in the database (adp.llm.settings), so every worker agrees and a restart
# keeps them. The API key comes from the environment only and cannot be set through this API.

_get_session = session_dependency("adp.llm.settings")


# ── Pydantic models ───────────────────────────────────────────────────────────

class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str
    tier: str
    context_window: int
    recommended_for: list[str]


class ModelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[ModelInfo]
    provider: str
    endpoint: str
    api_key_configured: bool


class LLMConfigResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    extraction_model: str
    recommendation_model: str
    validation_model: str
    api_key_configured: bool
    provider: Literal["anthropic", "openai_compatible", "not_configured"]


class LLMConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction_model: str | None = None
    recommendation_model: str | None = None
    validation_model: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

def _provider(endpoint: str, api_key_configured: bool) -> Literal[
    "anthropic", "openai_compatible", "not_configured"
]:
    if not endpoint or not api_key_configured:
        return "not_configured"
    return "anthropic" if "anthropic.com" in endpoint.lower() else "openai_compatible"


def _response(models: dict[str, str]) -> LLMConfigResponse:
    endpoint = llm_settings.endpoint()
    configured = bool(llm_settings.api_key())
    return LLMConfigResponse(
        endpoint=endpoint,
        extraction_model=models["extraction_model"],
        recommendation_model=models["recommendation_model"],
        validation_model=models["validation_model"],
        api_key_configured=configured,
        provider=_provider(endpoint, configured),
    )


@router.get("/models", response_model=ModelsResponse)
async def get_available_models() -> ModelsResponse:
    """Return available Anthropic models for extraction and recommendations."""
    return ModelsResponse(
        models=[ModelInfo(**m) for m in ANTHROPIC_MODELS],  # type: ignore[arg-type]
        provider="Anthropic",
        endpoint=llm_settings.endpoint(),
        api_key_configured=bool(llm_settings.api_key()),
    )


@router.get("/llm", response_model=LLMConfigResponse)
async def get_llm_config() -> LLMConfigResponse:
    """Return current LLM configuration (active models and connection status)."""
    await llm_settings.refresh()
    return _response(llm_settings.current())


@router.put("/llm", response_model=LLMConfigResponse)
async def update_llm_config(
    update: LLMConfigUpdate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
) -> LLMConfigResponse:
    """Choose the model for extraction, recommendations and/or validation. Applies to every
    worker and survives a restart. (The API key is set at deploy time, not here.)"""
    changes = update.model_dump(exclude_none=True)
    valid_ids = sorted(m["id"] for m in ANTHROPIC_MODELS)  # type: ignore[type-var]
    for setting, model_id in changes.items():
        if model_id not in valid_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown model '{model_id}'. Valid: {valid_ids}",
            )
    actor = actor_of(request)
    models = await llm_settings.save(session, changes, actor)
    await session.commit()
    if changes:
        _logger.info("config.llm.update actor=%s changes=%s", actor, changes)
    return _response(models)


def get_extraction_model() -> str:
    """Return the currently configured extraction model ID."""
    return llm_settings.model_for("extraction_model")


def get_recommendation_model() -> str:
    """Return the currently configured recommendation model ID."""
    return llm_settings.model_for("recommendation_model")


def get_validation_model() -> str:
    """Return the currently configured LLM-as-Judge validation model ID."""
    return llm_settings.model_for("validation_model")


def get_api_key() -> str:
    """Return the LLM API key from the environment. NEVER log the return value."""
    return llm_settings.api_key()
