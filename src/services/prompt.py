"""Prompt construction for Groq ranking (Phase 4)."""

from __future__ import annotations

import json
from typing import Any

from src.data.models import Restaurant, UserPreferences

SYSTEM_PROMPT = """You are an expert restaurant recommendation assistant for Indian cities.
You receive filtered candidate restaurants that already match the user's city, cuisine, rating, and budget constraints.
Your job is to rank the best options and explain why each fits the user's preferences.

RULES:
- Only rank restaurants from the provided RESTAURANTS_JSON list.
- Use restaurant_id values exactly as given — never invent ids or restaurants.
- Return ONLY valid JSON with no markdown fences or extra text.
- Rank from 1 (best) to N.
- Write 1-2 sentence explanations tied to the user's stated preferences.
"""

JSON_SCHEMA_HINT = """{
  "ranked": [
    {"restaurant_id": "<id from list>", "rank": 1, "explanation": "..."}
  ],
  "summary": "Optional one-paragraph overview of the picks."
}"""

REPAIR_PROMPT = """Your previous response was not valid JSON.
Return ONLY valid JSON matching this schema (no markdown, no commentary):
{"ranked": [{"restaurant_id": "...", "rank": 1, "explanation": "..."}], "summary": "..."}
"""


def _compact_restaurant(restaurant: Restaurant) -> dict[str, Any]:
    cuisines = restaurant.cuisines[:5]
    return {
        "restaurant_id": restaurant.id,
        "name": restaurant.name,
        "city": restaurant.city,
        "cuisines": cuisines,
        "rating": restaurant.rating,
        "budget_tier": restaurant.budget_tier.value,
        "cost_for_two": restaurant.cost_for_two,
    }


def _preferences_payload(preferences: UserPreferences) -> dict[str, Any]:
    return {
        "location": preferences.location,
        "budget": preferences.budget.value,
        "cuisine": preferences.cuisine,
        "min_rating": preferences.min_rating,
        "additional": preferences.additional,
        "top_k": preferences.top_k,
    }


def build_ranking_messages(
    preferences: UserPreferences,
    candidates: list[Restaurant],
) -> list[dict[str, str]]:
    """Build chat messages for Groq ranking."""
    restaurants_json = json.dumps(
        [_compact_restaurant(r) for r in candidates],
        ensure_ascii=False,
    )
    prefs_json = json.dumps(_preferences_payload(preferences), ensure_ascii=False)

    user_content = f"""USER_PREFERENCES:
{prefs_json}

RESTAURANTS_JSON:
{restaurants_json}

INSTRUCTIONS:
1. Select and rank the top {preferences.top_k} restaurants (rank 1 = best match).
2. For each, explain why it fits the user's location, budget, cuisine, rating, and additional notes.
3. Provide a brief summary of the overall recommendations.

Return JSON matching this schema:
{JSON_SCHEMA_HINT}
"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_repair_messages(
    preferences: UserPreferences,
    candidates: list[Restaurant],
    invalid_response: str,
) -> list[dict[str, str]]:
    """Build messages to repair invalid JSON from the LLM."""
    base = build_ranking_messages(preferences, candidates)
    truncated = invalid_response[:2000]
    base.append(
        {
            "role": "assistant",
            "content": truncated,
        }
    )
    base.append({"role": "user", "content": REPAIR_PROMPT})
    return base
