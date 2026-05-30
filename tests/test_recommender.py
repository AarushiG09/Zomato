"""Tests for RecommendationService orchestrator (Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.data.ingest import normalize_dataframe, persist_to_sqlite
from src.data.models import BudgetTier
from src.data.repository import RestaurantRepository
from src.services.exceptions import PreferenceValidationError
from src.services.llm import MockLLMProvider
from src.services.ranker import LLMRankingService
from src.services.recommender import RecommendationService
from src.api.schemas import RecommendationRequest, RecommendationResponse


@pytest.fixture
def test_db(sample_raw_df, tmp_path) -> Path:
    normalized, _ = normalize_dataframe(sample_raw_df)
    db_path = tmp_path / "test_restaurants.db"
    persist_to_sqlite(normalized, db_path)
    return db_path


@pytest.fixture
def test_repo(test_db: Path) -> RestaurantRepository:
    return RestaurantRepository(test_db)


class TestRecommendationService:
    def test_recommend_success_flow(self, test_repo):
        # Query database to get real dynamic ingested IDs
        restaurants = test_repo.get_all()
        assert len(restaurants) >= 2
        r_id = restaurants[0].id
        r_name = restaurants[0].name

        mock_response = json.dumps(
            {
                "ranked": [
                    {
                        "restaurant_id": r_id,
                        "rank": 1,
                        "explanation": "Highly rated bistro match.",
                    }
                ],
                "summary": "Best options.",
            }
        )

        provider = MockLLMProvider(mock_response)
        ranker = LLMRankingService(provider=provider)
        service = RecommendationService(test_repo, ranking_service=ranker)

        prefs = RecommendationRequest(
            location="Koramangala",
            budget=BudgetTier.HIGH,
            cuisine="Italian",
            min_rating=4.0,
            top_k=2,
        )

        response = service.recommend(prefs)

        assert isinstance(response, RecommendationResponse)
        assert response.preferences.location == "Koramangala"
        assert response.meta.candidates_considered == 1
        assert response.meta.llm_provider == "mock"
        assert len(response.recommendations) == 1
        assert response.recommendations[0].restaurant.id == r_id
        assert response.recommendations[0].restaurant.name == r_name
        assert response.recommendations[0].explanation == "Highly rated bistro match."
        assert response.summary == "Best options."

    def test_recommend_empty_candidates(self, test_repo):
        provider = MockLLMProvider("not used")
        ranker = LLMRankingService(provider=provider)
        service = RecommendationService(test_repo, ranking_service=ranker)

        prefs = {
            "location": "Koramangala",
            "budget": BudgetTier.LOW,
            "cuisine": "Mexican",  # No Mexican cuisines exist in test_repo
            "min_rating": 4.0,
        }

        response = service.recommend(prefs)

        assert response.meta.candidates_considered == 0
        assert response.meta.llm_provider is None
        assert response.recommendations == []
        assert "No matching restaurants found" in response.summary

    def test_recommend_validation_failure(self, test_repo):
        service = RecommendationService(test_repo)

        # Invalid city (not in listed list of cities)
        prefs = {
            "location": "Invalid City",
            "budget": BudgetTier.LOW,
            "cuisine": "Italian",
        }

        with pytest.raises(PreferenceValidationError):
            service.recommend(prefs)
