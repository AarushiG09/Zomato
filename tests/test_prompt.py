"""Tests for Phase 4 prompt builder."""

from __future__ import annotations

import json

from src.data.models import BudgetTier, Restaurant, UserPreferences
from src.services.prompt import build_ranking_messages, build_repair_messages


def _sample_prefs() -> UserPreferences:
    return UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="North Indian",
        min_rating=4.0,
        additional=["family-friendly"],
        top_k=3,
    )


def _sample_candidates() -> list[Restaurant]:
    return [
        Restaurant(
            id="r1",
            name="Spice Villa",
            city="Bangalore",
            cuisines=["North Indian", "Chinese"],
            rating=4.5,
            cost_for_two=600,
            budget_tier=BudgetTier.MEDIUM,
        ),
        Restaurant(
            id="r2",
            name="Cafe Italiano",
            city="Bangalore",
            cuisines=["Italian"],
            rating=4.2,
            cost_for_two=800,
            budget_tier=BudgetTier.HIGH,
        ),
    ]


class TestPromptBuilder:
    def test_build_ranking_messages_structure(self):
        prefs = _sample_prefs()
        candidates = _sample_candidates()
        messages = build_ranking_messages(prefs, candidates)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "RESTAURANTS_JSON" in messages[1]["content"]
        assert "USER_PREFERENCES" in messages[1]["content"]
        assert "family-friendly" in messages[1]["content"]
        assert "top 3" in messages[1]["content"].lower() or "top 3" in messages[1]["content"]

    def test_restaurant_ids_in_prompt(self):
        messages = build_ranking_messages(_sample_prefs(), _sample_candidates())
        user = messages[1]["content"]
        assert "r1" in user
        assert "r2" in user
        assert "Spice Villa" in user

    def test_preferences_json_in_prompt(self):
        messages = build_ranking_messages(_sample_prefs(), _sample_candidates())
        assert '"location": "Bangalore"' in messages[1]["content"]
        assert '"budget": "medium"' in messages[1]["content"]

    def test_build_repair_messages_includes_invalid_response(self):
        prefs = _sample_prefs()
        candidates = _sample_candidates()
        invalid = "Here are my picks: not json"
        messages = build_repair_messages(prefs, candidates, invalid)

        assert messages[-1]["role"] == "user"
        assert "valid JSON" in messages[-1]["content"]
        assert messages[-2]["role"] == "assistant"
        assert "not json" in messages[-2]["content"]

    def test_compact_restaurant_limits_cuisines(self):
        from src.services.prompt import _compact_restaurant

        r = Restaurant(
            id="x",
            name="Many Cuisines",
            city="Bangalore",
            cuisines=["A", "B", "C", "D", "E", "F"],
            rating=4.0,
            budget_tier=BudgetTier.LOW,
        )
        compact = _compact_restaurant(r)
        assert len(compact["cuisines"]) <= 5
