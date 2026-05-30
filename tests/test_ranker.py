"""Tests for Phase 4 LLM ranking service."""

from __future__ import annotations

import json

import pytest

from src.data.models import BudgetTier, Restaurant, UserPreferences
from src.services.llm import LLMCompletionResult, MockLLMProvider
from src.services.ranker import LLMRankingService


def _prefs() -> UserPreferences:
    return UserPreferences(
        location="Bangalore",
        budget=BudgetTier.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
        top_k=2,
    )


def _candidates() -> list[Restaurant]:
    return [
        Restaurant(
            id="r1",
            name="Italian Place",
            city="Bangalore",
            cuisines=["Italian"],
            rating=4.5,
            budget_tier=BudgetTier.MEDIUM,
        ),
        Restaurant(
            id="r2",
            name="Other Place",
            city="Bangalore",
            cuisines=["Chinese"],
            rating=4.0,
            budget_tier=BudgetTier.LOW,
        ),
    ]


def _valid_mock_response() -> str:
    return json.dumps(
        {
            "ranked": [
                {
                    "restaurant_id": "r1",
                    "rank": 1,
                    "explanation": "Best Italian match for your preferences.",
                }
            ],
            "summary": "Top pick for Italian in Bangalore.",
        }
    )


class TestLLMRankingService:
    def test_mock_provider_success(self):
        provider = MockLLMProvider(_valid_mock_response())
        service = LLMRankingService(provider=provider)
        result = service.rank(_prefs(), _candidates())

        assert len(result.recommendations) == 1
        assert result.recommendations[0]["restaurant"].id == "r1"
        assert result.meta["llm_provider"] == "mock"
        assert result.meta["llm_fallback"] is False
        assert result.summary == "Top pick for Italian in Bangalore."

    def test_invalid_json_then_fallback(self):
        provider = MockLLMProvider("not valid json at all")
        service = LLMRankingService(provider=provider)
        result = service.rank(_prefs(), _candidates())

        assert result.meta["llm_fallback"] is True
        assert len(result.recommendations) == 2
        assert result.recommendations[0]["restaurant"].rating >= 4.0

    def test_empty_candidates(self):
        service = LLMRankingService(
            provider=MockLLMProvider(_valid_mock_response())
        )
        result = service.rank(_prefs(), [])
        assert result.recommendations == []

    def test_respects_top_k(self):
        response = json.dumps(
            {
                "ranked": [
                    {"restaurant_id": "r1", "rank": 1, "explanation": "a"},
                    {"restaurant_id": "r2", "rank": 2, "explanation": "b"},
                ],
                "summary": "both",
            }
        )
        provider = MockLLMProvider(response)
        service = LLMRankingService(provider=provider)
        result = service.rank(_prefs(), _candidates())
        assert len(result.recommendations) <= 2

    def test_repair_succeeds_on_second_format(self):
        calls = []

        class FlakyMock:
            provider_name = "mock"
            model_name = "flaky"

            def complete(self, messages, **kwargs):
                calls.append(len(messages))
                if len(calls) == 1:
                    return LLMCompletionResult(
                        content="broken",
                        provider="mock",
                        model="flaky",
                        latency_ms=1.0,
                    )
                return LLMCompletionResult(
                    content=_valid_mock_response(),
                    provider="mock",
                    model="flaky",
                    latency_ms=1.0,
                )

        service = LLMRankingService(provider=FlakyMock())
        result = service.rank(_prefs(), _candidates())
        assert len(calls) == 2
        assert result.meta["llm_fallback"] is False
        assert len(result.recommendations) == 1


@pytest.mark.integration
class TestGroqIntegration:
    def test_live_groq_ranking(self):
        import os

        if os.getenv("RUN_LLM_TESTS") != "1":
            pytest.skip("Set RUN_LLM_TESTS=1 to run live Groq tests")
        if not os.getenv("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set")

        from src.services.llm import GroqProvider

        service = LLMRankingService(provider=GroqProvider())
        result = service.rank(_prefs(), _candidates())
        assert len(result.recommendations) >= 1
        assert result.meta["llm_provider"] == "groq"
