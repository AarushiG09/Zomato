"""Parse and validate Groq LLM ranking responses (Phase 4)."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from pydantic import ValidationError

from src.data.models import Restaurant, UserPreferences
from src.services.llm_schemas import LLMResponseSchema

logger = logging.getLogger(__name__)


class LLMParseError(ValueError):
    """Raised when LLM output cannot be parsed or validated."""


def extract_json_text(raw: str) -> str:
    """Strip markdown fences and extract JSON object from LLM text."""
    text = raw.strip()
    if not text:
        raise LLMParseError("Empty LLM response")

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMParseError("No JSON object found in LLM response")
    return text[start : end + 1]


def parse_llm_response(raw: str) -> LLMResponseSchema:
    """Parse raw LLM string into validated schema."""
    try:
        json_text = extract_json_text(raw)
        data = json.loads(json_text)
        return LLMResponseSchema.model_validate(data)
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"Invalid JSON: {exc}") from exc
    except ValidationError as exc:
        raise LLMParseError(f"Schema validation failed: {exc}") from exc


def merge_ranked_response(
    parsed: LLMResponseSchema,
    candidates: list[Restaurant],
    preferences: UserPreferences,
) -> tuple[list[dict], Optional[str]]:
    """
    Map parsed LLM output to recommendation dicts.

    Returns:
        (recommendations, summary) where each recommendation has rank, restaurant, explanation.
    Only includes restaurant_ids present in candidates (anti-hallucination).
    """
    by_id = {r.id: r for r in candidates}
    seen_ids: set[str] = set()
    recommendations: list[dict] = []

    sorted_items = sorted(parsed.ranked, key=lambda x: x.rank)
    for item in sorted_items:
        rid = item.restaurant_id
        if rid not in by_id or rid in seen_ids:
            if rid not in by_id:
                logger.warning("LLM returned unknown restaurant_id: %s", rid)
            continue
        seen_ids.add(rid)
        recommendations.append(
            {
                "rank": item.rank,
                "restaurant": by_id[rid],
                "explanation": item.explanation.strip()
                or _generic_explanation(by_id[rid], preferences),
            }
        )

    # Sort by rank and re-number if gaps
    recommendations.sort(key=lambda x: x["rank"])
    for i, rec in enumerate(recommendations, start=1):
        rec["rank"] = i

    return recommendations, parsed.summary


def build_fallback_recommendations(
    preferences: UserPreferences,
    candidates: list[Restaurant],
) -> tuple[list[dict], Optional[str]]:
    """Rating-sorted fallback when Groq or parsing fails."""
    sorted_candidates = sorted(
        candidates,
        key=lambda r: (-r.rating, r.name.lower()),
    )[: preferences.top_k]
    recommendations = [
        {
            "rank": i,
            "restaurant": r,
            "explanation": _generic_explanation(r, preferences),
        }
        for i, r in enumerate(sorted_candidates, start=1)
    ]
    summary = (
        "AI explanations are temporarily unavailable. "
        "Results are sorted by rating."
    )
    return recommendations, summary


def _generic_explanation(restaurant: Restaurant, preferences: UserPreferences) -> str:
    cuisines = ", ".join(restaurant.cuisines[:3]) or preferences.cuisine
    return (
        f"{restaurant.name} in {restaurant.city} serves {cuisines}, "
        f"rated {restaurant.rating}/5, matching your {preferences.budget.value} budget "
        f"and {preferences.cuisine} preference."
    )
