"""Tests for Phase 3 validation and filter service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import MAX_CANDIDATES_FOR_LLM
from src.data.ingest import normalize_dataframe, persist_to_sqlite
from src.data.models import BudgetTier, Restaurant, UserPreferences
from src.data.repository import RestaurantRepository
from src.services.exceptions import PreferenceValidationError
from src.services.filter import RestaurantFilterService
from src.services.validation import PreferenceValidator


@pytest.fixture
def repo_db(sample_raw_df, tmp_path) -> Path:
    normalized, _ = normalize_dataframe(sample_raw_df)
    db_path = tmp_path / "test_restaurants.db"
    persist_to_sqlite(normalized, db_path)
    return db_path


@pytest.fixture
def repo(repo_db: Path) -> RestaurantRepository:
    return RestaurantRepository(repo_db)


@pytest.fixture
def filter_service(repo: RestaurantRepository) -> RestaurantFilterService:
    return RestaurantFilterService(repo, max_candidates=5, budget_soft=True)


class TestPreferenceValidator:
    def test_valid_preferences(self, repo: RestaurantRepository):
        validator = PreferenceValidator(repo)
        prefs = validator.validate(
            {
                "location": "koramangala",
                "budget": "medium",
                "cuisine": "Italian",
                "min_rating": 4.0,
            }
        )
        assert prefs.location == "Koramangala"
        assert prefs.budget == BudgetTier.MEDIUM

    def test_empty_location_raises(self, repo: RestaurantRepository):
        validator = PreferenceValidator(repo)
        with pytest.raises(PreferenceValidationError) as exc:
            validator.validate(
                {
                    "location": "  ",
                    "budget": "medium",
                    "cuisine": "Italian",
                }
            )
        assert "location" in exc.value.errors

    def test_unknown_city_raises(self, repo: RestaurantRepository):
        validator = PreferenceValidator(repo)
        with pytest.raises(PreferenceValidationError) as exc:
            validator.validate(
                {
                    "location": "Tokyo",
                    "budget": "medium",
                    "cuisine": "Italian",
                }
            )
        assert "location" in exc.value.errors

    def test_missing_cuisine_raises(self, repo: RestaurantRepository):
        validator = PreferenceValidator(repo)
        with pytest.raises(PreferenceValidationError) as exc:
            validator.validate(
                {
                    "location": "Koramangala",
                    "budget": "medium",
                    "cuisine": "",
                }
            )
        assert "cuisine" in exc.value.errors

    def test_invalid_budget_raises(self):
        with pytest.raises(PreferenceValidationError):
            PreferenceValidator(MagicMock(list_cities=MagicMock(return_value=["Koramangala"]))).validate(
                {
                    "location": "Koramangala",
                    "budget": "expensive",
                    "cuisine": "any",
                }
            )

    def test_top_k_out_of_range(self, repo: RestaurantRepository):
        validator = PreferenceValidator(repo)
        with pytest.raises(PreferenceValidationError) as exc:
            validator.validate(
                {
                    "location": "Koramangala",
                    "budget": "medium",
                    "cuisine": "any",
                    "top_k": 50,
                }
            )
        assert "top_k" in exc.value.errors

    def test_additional_too_long(self, repo: RestaurantRepository):
        validator = PreferenceValidator(repo)
        with pytest.raises(PreferenceValidationError) as exc:
            validator.validate(
                {
                    "location": "Koramangala",
                    "budget": "medium",
                    "cuisine": "any",
                    "additional": ["x" * 501],
                }
            )
        assert "additional" in exc.value.errors


class TestRestaurantFilterService:
    def test_valid_combo_returns_candidates(self, filter_service: RestaurantFilterService):
        result = filter_service.filter(
            {
                "location": "Koramangala",
                "budget": "high",
                "cuisine": "Italian",
                "min_rating": 4.0,
            }
        )
        assert not result.is_empty
        assert len(result.candidates) >= 1
        assert result.candidates[0].name == "Test Bistro"
        assert all(r.rating >= 4.0 for r in result.candidates)

    def test_impossible_combo_returns_empty_without_exception(
        self, filter_service: RestaurantFilterService
    ):
        result = filter_service.filter(
            {
                "location": "Koramangala",
                "budget": "low",
                "cuisine": "Mexican",
                "min_rating": 5.0,
            }
        )
        assert result.is_empty
        assert result.candidates == []
        assert len(result.empty_hints) > 0

    def test_output_capped_to_max(self, filter_service: RestaurantFilterService):
        result = filter_service.filter(
            {
                "location": "Koramangala",
                "budget": "high",
                "cuisine": "any",
                "min_rating": 0.0,
            }
        )
        assert len(result.candidates) <= 5
        if result.total_matched > 5:
            assert result.capped is True

    def test_sort_by_rating_then_budget(self, repo: RestaurantRepository):
        service = RestaurantFilterService(
            repo, max_candidates=10, budget_soft=True
        )
        result = service.filter(
            {
                "location": "Koramangala",
                "budget": "high",
                "cuisine": "any",
                "min_rating": 0.0,
            }
        )
        ratings = [r.rating for r in result.candidates]
        assert ratings == sorted(ratings, reverse=True)

    def test_cuisine_any_skips_cuisine_filter(self, filter_service: RestaurantFilterService):
        """'any' cuisine should not exclude restaurants by cuisine type."""
        result = filter_service.filter(
            {
                "location": "Koramangala",
                "budget": "high",
                "cuisine": "any",
                "min_rating": 0.0,
            }
        )
        assert not result.is_empty
        assert result.total_matched >= 1
        cuisines = {c for r in result.candidates for c in r.cuisines}
        assert "Italian" in cuisines or "Chinese" in cuisines

    def test_invalid_preferences_propagate(self, filter_service: RestaurantFilterService):
        with pytest.raises(PreferenceValidationError):
            filter_service.filter(
                {
                    "location": "UnknownCity",
                    "budget": "medium",
                    "cuisine": "Italian",
                }
            )


class TestFilterCapConfig:
    def test_default_max_candidates(self, repo: RestaurantRepository):
        service = RestaurantFilterService(repo, budget_soft=True)
        assert service.max_candidates == MAX_CANDIDATES_FOR_LLM


@pytest.mark.integration
class TestFilterIntegration:
    def test_bangalore_north_indian_rating_4(self):
        from src.config import DATABASE_PATH

        if not DATABASE_PATH.exists():
            pytest.skip("Run scripts/ingest_dataset.py first")

        service = RestaurantFilterService(RestaurantRepository(DATABASE_PATH))
        result = service.filter(
            {
                "location": "Indiranagar",
                "budget": "medium",
                "cuisine": "North Indian",
                "min_rating": 4.0,
            }
        )
        assert not result.is_empty
        assert len(result.candidates) <= MAX_CANDIDATES_FOR_LLM
        assert all(r.rating >= 4.0 for r in result.candidates)
        assert all(r.matches_cuisine("North Indian") for r in result.candidates)
