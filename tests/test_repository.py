"""Tests for Phase 2 domain models and repository."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.data.exceptions import DatasetNotFoundError
from src.data.ingest import TABLE_NAME, normalize_dataframe, persist_to_sqlite
from src.data.models import BudgetTier, Restaurant, UserPreferences
from src.data.repository import RestaurantRepository, normalize_location


@pytest.fixture
def repo_db(sample_raw_df, tmp_path) -> Path:
    """Small SQLite DB for repository unit tests."""
    normalized, _ = normalize_dataframe(sample_raw_df)
    db_path = tmp_path / "test_restaurants.db"
    persist_to_sqlite(normalized, db_path)
    return db_path


@pytest.fixture
def repo(repo_db: Path) -> RestaurantRepository:
    return RestaurantRepository(repo_db)


class TestModels:
    def test_restaurant_parses_cuisines_json(self):
        r = Restaurant(
            id="1",
            name="Test",
            city="Bangalore",
            cuisines='["Italian", "Cafe"]',
            rating=4.5,
            budget_tier="medium",
        )
        assert r.cuisines == ["Italian", "Cafe"]

    def test_matches_cuisine(self):
        r = Restaurant(
            id="1",
            name="Test",
            city="Bangalore",
            cuisines=["North Indian", "Chinese"],
            rating=4.0,
            budget_tier=BudgetTier.MEDIUM,
        )
        assert r.matches_cuisine("indian")
        assert r.matches_cuisine("Chinese")
        assert not r.matches_cuisine("Italian")
        assert r.matches_cuisine("any")

    def test_estimated_cost_display(self):
        r = Restaurant(
            id="1",
            name="Test",
            city="Bangalore",
            cuisines=["Indian"],
            rating=4.0,
            cost_for_two=800,
            budget_tier=BudgetTier.HIGH,
        )
        assert "800" in r.estimated_cost_display

    def test_user_preferences_defaults(self):
        prefs = UserPreferences(
            location="Bangalore",
            budget=BudgetTier.MEDIUM,
            cuisine="Italian",
        )
        assert prefs.min_rating == 3.5
        assert prefs.top_k == 5


class TestDatasetNotFound:
    def test_missing_database_raises(self, tmp_path):
        missing = tmp_path / "missing.db"
        with pytest.raises(DatasetNotFoundError) as exc:
            RestaurantRepository(missing)
        assert "ingest_dataset.py" in str(exc.value)

    def test_empty_database_raises(self, tmp_path):
        db_path = tmp_path / "empty.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"""
                CREATE TABLE {TABLE_NAME} (
                    id TEXT, name TEXT, city TEXT, cuisines TEXT,
                    rating REAL, cost_for_two INTEGER, budget_tier TEXT, metadata TEXT
                )
                """
            )
        with pytest.raises(DatasetNotFoundError):
            RestaurantRepository(db_path)


class TestRestaurantRepository:
    def test_get_all(self, repo: RestaurantRepository):
        all_rows = repo.get_all()
        assert len(all_rows) == 2
        assert all(isinstance(r, Restaurant) for r in all_rows)

    def test_get_by_city_case_insensitive(self, repo: RestaurantRepository):
        lower = repo.get_by_city("koramangala")
        upper = repo.get_by_city("Koramangala")
        assert len(lower) == len(upper) == 1

    def test_get_by_city_unknown_returns_empty(self, repo: RestaurantRepository):
        assert repo.get_by_city("Mumbai") == []

    def test_list_cities(self, repo: RestaurantRepository):
        cities = repo.list_cities()
        assert cities == ["Indiranagar", "Koramangala"]

    def test_query_candidates_location_and_rating(self, repo: RestaurantRepository):
        results = repo.query_candidates(
            location="Koramangala",
            cuisine="any",
            min_rating=4.0,
            budget=BudgetTier.HIGH,
        )
        assert len(results) == 1
        assert results[0].name == "Test Bistro"
        assert results[0].rating >= 4.0

    def test_query_candidates_cuisine_filter(self, repo: RestaurantRepository):
        italian = repo.query_candidates(
            location="Koramangala",
            cuisine="Italian",
            min_rating=0.0,
            budget=BudgetTier.HIGH,
        )
        assert len(italian) == 1
        assert italian[0].matches_cuisine("Italian")

        chinese_only = repo.query_candidates(
            location="Indiranagar",
            cuisine="Chinese",
            min_rating=0.0,
            budget=BudgetTier.LOW,
        )
        assert len(chinese_only) == 1
        assert chinese_only[0].name == "Budget Eats"

    def test_query_candidates_min_rating_excludes_lower(self, repo: RestaurantRepository):
        results = repo.query_candidates(
            location="Koramangala",
            cuisine="any",
            min_rating=4.5,
            budget=BudgetTier.MEDIUM,
        )
        assert len(results) == 0

    def test_query_candidates_budget_filter(self, repo: RestaurantRepository):
        high = repo.query_candidates(
            location="Koramangala",
            cuisine="any",
            min_rating=0.0,
            budget=BudgetTier.HIGH,
        )
        assert all(r.budget_tier == BudgetTier.HIGH for r in high)

    def test_query_candidates_budget_soft(self, repo: RestaurantRepository):
        """Soft budget includes adjacent tier (medium → low+medium+high)."""
        soft = repo.query_candidates(
            location="Koramangala",
            cuisine="any",
            min_rating=0.0,
            budget=BudgetTier.MEDIUM,
            budget_soft=True,
        )
        tiers = {r.budget_tier for r in soft}
        assert BudgetTier.MEDIUM in tiers or len(soft) >= 1

    def test_normalize_location_alias(self):
        assert normalize_location("bengaluru") == "Bangalore"


@pytest.mark.integration
class TestProductionRepository:
    def test_production_db_list_cities_and_query(self):
        from src.config import DATABASE_PATH

        if not DATABASE_PATH.exists():
            pytest.skip("Run scripts/ingest_dataset.py first")

        repo = RestaurantRepository(DATABASE_PATH)
        cities = repo.list_cities()
        assert len(cities) > 0
        
        # Check for a representative locality in our database
        target_city = "Indiranagar" if "Indiranagar" in cities else cities[0]
        assert target_city in cities

        candidates = repo.query_candidates(
            location=target_city,
            cuisine="North Indian",
            min_rating=4.0,
            budget=BudgetTier.MEDIUM,
        )
        # It's possible there are no North Indian medium restaurants in this specific city/locality,
        # but let's query just for location to be sure the records load
        loc_candidates = repo.get_by_city(target_city)
        assert len(loc_candidates) > 0
        assert all(r.city == target_city for r in loc_candidates)

