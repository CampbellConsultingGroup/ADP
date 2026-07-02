"""LLM configuration endpoints — available models and active model selection.

GET /api/v1/config/models   — list all available Anthropic models
GET /api/v1/config/llm      — get current LLM configuration
PUT /api/v1/config/llm      — update active model(s) for extraction and recommendations
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

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

# ── In-process LLM config store ───────────────────────────────────────────────
# Defaults read from environment; overridable via PUT /api/v1/config/llm

_llm_config: dict[str, str] = {
    "endpoint": os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com"),
    "extraction_model": os.environ.get("ADP_LLM_MODEL", "claude-sonnet-4-6"),
    "recommendation_model": os.environ.get("ADP_LLM_RECOMMENDATION_MODEL", "claude-sonnet-4-6"),
}


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
    api_key_configured: bool
    provider: Literal["anthropic", "openai_compatible", "not_configured"]


class LLMConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    extraction_model: str | None = None
    recommendation_model: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/models", response_model=ModelsResponse)
async def get_available_models() -> ModelsResponse:
    """Return available Anthropic models for extraction and recommendations."""
    endpoint = _llm_config["endpoint"]
    api_key_configured = bool(os.environ.get("ADP_LLM_API_KEY", ""))
    return ModelsResponse(
        models=[ModelInfo(**m) for m in ANTHROPIC_MODELS],
        provider="Anthropic",
        endpoint=endpoint,
        api_key_configured=api_key_configured,
    )


@router.get("/llm", response_model=LLMConfigResponse)
async def get_llm_config() -> LLMConfigResponse:
    """Return current LLM configuration (active models and connection status)."""
    endpoint = _llm_config["endpoint"]
    api_key_configured = bool(os.environ.get("ADP_LLM_API_KEY", ""))

    if not endpoint or not api_key_configured:
        provider: Literal["anthropic", "openai_compatible", "not_configured"] = "not_configured"
    elif "anthropic.com" in endpoint.lower():
        provider = "anthropic"
    else:
        provider = "openai_compatible"

    return LLMConfigResponse(
        endpoint=endpoint,
        extraction_model=_llm_config["extraction_model"],
        recommendation_model=_llm_config["recommendation_model"],
        api_key_configured=api_key_configured,
        provider=provider,
    )


@router.put("/llm", response_model=LLMConfigResponse)
async def update_llm_config(update: LLMConfigUpdate) -> LLMConfigResponse:
    """Update active model selection for extraction and/or recommendations."""
    if update.extraction_model is not None:
        valid_ids = {m["id"] for m in ANTHROPIC_MODELS}
        if update.extraction_model not in valid_ids:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown model '{update.extraction_model}'. Valid: {sorted(valid_ids)}",
            )
        _llm_config["extraction_model"] = update.extraction_model

    if update.recommendation_model is not None:
        valid_ids = {m["id"] for m in ANTHROPIC_MODELS}
        if update.recommendation_model not in valid_ids:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown model '{update.recommendation_model}'. Valid: {sorted(valid_ids)}",
            )
        _llm_config["recommendation_model"] = update.recommendation_model

    return await get_llm_config()


def get_extraction_model() -> str:
    """Return the currently configured extraction model ID."""
    return _llm_config["extraction_model"]


def get_recommendation_model() -> str:
    """Return the currently configured recommendation model ID."""
    return _llm_config["recommendation_model"]
