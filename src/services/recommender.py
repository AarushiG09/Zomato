"""Orchestrator service for the recommendation system (Phase 5)."""

from __future__ import annotations

import logging
from typing import Any, Optional, Union

from src.data.models import UserPreferences
from src.data.repository import RestaurantRepository
from src.services.filter import RestaurantFilterService
from src.services.ranker import LLMRankingService
from src.api.schemas import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    ResponseMeta,
    RestaurantDetail,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Coordinates the full recommendation pipeline:
    Validate preferences -> Filter candidate restaurants -> Call LLM ranker -> Construct response.
    """

    def __init__(
        self,
        repository: RestaurantRepository,
        filter_service: Optional[RestaurantFilterService] = None,
        ranking_service: Optional[LLMRankingService] = None,
    ) -> None:
        self.repository = repository
        self.filter_service = filter_service or RestaurantFilterService(repository)
        self.ranking_service = ranking_service or LLMRankingService()

    def recommend(
        self,
        preferences: Union[UserPreferences, dict[str, Any], RecommendationRequest],
    ) -> RecommendationResponse:
        """
        Runs the end-to-end recommendation workflow.

        Raises:
            PreferenceValidationError: If input preferences are invalid.
        """
        # 1. Convert/validate preferences using the filter service (which uses PreferenceValidator)
        # Note: If validation fails, PreferenceValidationError is raised and propagates.
        filter_input = preferences
        if isinstance(preferences, RecommendationRequest):
            filter_input = preferences.model_dump()

        filter_result = self.filter_service.filter(filter_input)

        pref_req = RecommendationRequest(
            location=filter_result.preferences.location,
            budget=filter_result.preferences.budget,
            cuisine=filter_result.preferences.cuisine,
            min_rating=filter_result.preferences.min_rating,
            additional=filter_result.preferences.additional,
            top_k=filter_result.preferences.top_k,
        )

        # 2. If no candidates match, return a clean empty response without calling the LLM
        if filter_result.is_empty:
            logger.info(
                "No candidate restaurants matched preferences: location=%s, cuisine=%s",
                filter_result.preferences.location,
                filter_result.preferences.cuisine,
            )
            return RecommendationResponse(
                preferences=pref_req,
                summary="No matching restaurants found.",
                recommendations=[],
                meta=ResponseMeta(
                    candidates_considered=0,
                    llm_provider=None,
                    llm_model=None,
                    llm_fallback=False,
                    llm_latency_ms=None,
                    llm_retries=None,
                ),
            )

        # 3. Call LLM ranking service (which handles prompting, retries, and fallbacks)
        logger.info(
            "Ranking %d candidate restaurants for preferences: location=%s",
            len(filter_result.candidates),
            filter_result.preferences.location,
        )
        ranking_result = self.ranking_service.rank(
            filter_result.preferences,
            filter_result.candidates,
        )

        # 4. Map internal domain objects into standardized API schemas
        recommendations = []
        for rec in ranking_result.recommendations:
            rest = rec["restaurant"]
            detail = RestaurantDetail(
                id=rest.id,
                name=rest.name,
                city=rest.city,
                cuisines=rest.cuisines,
                rating=rest.rating,
                cost_for_two=rest.cost_for_two,
                budget_tier=rest.budget_tier,
                estimated_cost_display=rest.estimated_cost_display,
            )
            recommendations.append(
                RecommendationItem(
                    rank=rec["rank"],
                    restaurant=detail,
                    explanation=rec["explanation"],
                )
            )

        meta = ResponseMeta(
            candidates_considered=filter_result.total_matched,
            llm_provider=ranking_result.meta.get("llm_provider"),
            llm_model=ranking_result.meta.get("llm_model"),
            llm_fallback=ranking_result.meta.get("llm_fallback", False),
            llm_latency_ms=ranking_result.meta.get("llm_latency_ms"),
            llm_retries=ranking_result.meta.get("llm_retries"),
        )

        return RecommendationResponse(
            preferences=pref_req,
            summary=ranking_result.summary,
            recommendations=recommendations,
            meta=meta,
        )
