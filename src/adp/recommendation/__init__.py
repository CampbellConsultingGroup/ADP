"""ADP AI recommendation engine — grounded solution option generation (ADP-SPEC-007)."""

from adp.recommendation.models import (
    ProposedElement,
    RecommendationStep,
    SolutionOption,
    TradeOffEntry,
    TradeOffStance,
)
from adp.recommendation.orchestrator import RecommendationOrchestrator

__all__ = [
    "RecommendationOrchestrator",
    "SolutionOption",
    "TradeOffEntry",
    "TradeOffStance",
    "ProposedElement",
    "RecommendationStep",
]
