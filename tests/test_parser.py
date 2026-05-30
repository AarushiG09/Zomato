"""Tests for Phase 4 LLM response parser."""

from __future__ import annotations

import json

import pytest

from src.data.models import BudgetTier, Restaurant, UserPreferences
from src.services.parser import (
    LLMParseError,
    build_fallback_recommendations,
    extract_json_text,
    merge_ranked_response,
    parse_llm_response,
)
from src.services.llm_schemas import LLMResponseSchema


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
            name="A",
            city="Bangalore",
            cuisines=["Italian"],
            rating=4.5,
            budget_tier=BudgetTier.MEDIUM,
        ),
        Restaurant(
            id="r2",
            name="B",
            city="Bangalore",
            cuisines=["Chinese"],
            rating=4.0,
            budget_tier=BudgetTier.LOW,
        ),
    ]


VALID_JSON = json.dumps(
    {
        "ranked": [
            {
                "restaurant_id": "r2",
                "rank": 1,
                "explanation": "Great Chinese option.",
            },
            {
                "restaurant_id": "r1",
                "rank": 2,
                "explanation": "Solid Italian choice.",
            },
        ],
        "summary": "Two strong picks in Bangalore.",
    }
)


class TestExtractJson:
    def test_plain_json(self):
        assert extract_json_text('{"ranked": []}') == '{"ranked": []}'

    def test_markdown_fence(self):
        raw = '```json\n{"ranked": [], "summary": "ok"}\n```'
        parsed = json.loads(extract_json_text(raw))
        assert parsed["summary"] == "ok"

    def test_empty_raises(self):
        with pytest.raises(LLMParseError):
            extract_json_text("")


class TestParseLlmResponse:
    def test_valid_response(self):
        parsed = parse_llm_response(VALID_JSON)
        assert len(parsed.ranked) == 2
        assert parsed.summary == "Two strong picks in Bangalore."

    def test_malformed_json_raises(self):
        with pytest.raises(LLMParseError):
            parse_llm_response("{not json")

    def test_empty_ranked_parses(self):
        parsed = parse_llm_response('{"ranked": [], "summary": "only"}')
        assert parsed.ranked == []


class TestMergeRankedResponse:
    def test_maps_ids_to_restaurants(self):
        parsed = parse_llm_response(VALID_JSON)
        recs, summary = merge_ranked_response(parsed, _candidates(), _prefs())
        assert len(recs) == 2
        assert recs[0]["rank"] == 1
        assert recs[0]["restaurant"].id == "r2"
        assert "Chinese" in recs[0]["explanation"]
        assert summary == "Two strong picks in Bangalore."

    def test_unknown_id_skipped(self):
        parsed = LLMResponseSchema(
            ranked=[
                {"restaurant_id": "fake", "rank": 1, "explanation": "nope"},
                {"restaurant_id": "r1", "rank": 2, "explanation": "yes"},
            ]
        )
        recs, _ = merge_ranked_response(parsed, _candidates(), _prefs())
        assert len(recs) == 1
        assert recs[0]["restaurant"].id == "r1"


class TestFallback:
    def test_fallback_sorted_by_rating(self):
        recs, summary = build_fallback_recommendations(_prefs(), _candidates())
        assert len(recs) == 2
        assert recs[0]["restaurant"].rating >= recs[1]["restaurant"].rating
        assert "unavailable" in summary.lower()
