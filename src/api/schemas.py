"""API Request and Response schemas (Phase 5)."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from src.data.models import BudgetTier


class RecommendationRequest(BaseModel):
    """API Request schema matching UserPreferences."""

    location: str
    budget: BudgetTier
    cuisine: str = ""
    min_rating: float = Field(default=3.5, ge=0.0, le=5.0)
    additional: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class RestaurantDetail(BaseModel):
    """Detailed restaurant representation in response."""

    id: str
    name: str
    city: str
    cuisines: list[str]
    rating: float = Field(ge=0.0, le=5.0)
    cost_for_two: Optional[int] = None
    budget_tier: BudgetTier
    estimated_cost_display: str


class RecommendationItem(BaseModel):
    """A single recommendation entry."""

    rank: int
    restaurant: RestaurantDetail
    explanation: str


class ResponseMeta(BaseModel):
    """Metadata about the recommendation run."""

    candidates_considered: int
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_fallback: bool = False
    llm_latency_ms: Optional[float] = None
    llm_retries: Optional[int] = None


class RecommendationResponse(BaseModel):
    """Full API Response schema."""

    preferences: RecommendationRequest
    summary: Optional[str] = None
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    meta: ResponseMeta
