#!/usr/bin/env python3
"""Smoke test: filter + Groq LLM ranking (Phase 4)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.repository import RestaurantRepository
from src.services.exceptions import PreferenceValidationError
from src.services.filter import RestaurantFilterService
from src.services.llm import LLMProviderError, MockLLMProvider
from src.services.ranker import LLMRankingService


def main() -> int:
    parser = argparse.ArgumentParser(description="Test filter + Groq LLM ranking")
    parser.add_argument("--location", default="Bangalore")
    parser.add_argument("--budget", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--cuisine", default="North Indian")
    parser.add_argument("--min-rating", type=float, default=4.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mock", action="store_true", help="Use MockLLMProvider (no API key)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    prefs = {
        "location": args.location,
        "budget": args.budget,
        "cuisine": args.cuisine,
        "min_rating": args.min_rating,
        "top_k": args.top_k,
    }

    try:
        repo = RestaurantRepository()
        filter_result = RestaurantFilterService(repo).filter(prefs)
        if filter_result.is_empty:
            print("No candidates after filter.")
            for h in filter_result.empty_hints:
                print(f"  - {h}")
            return 0

        if args.mock:
            mock_json = json.dumps(
                {
                    "ranked": [
                        {
                            "restaurant_id": filter_result.candidates[0].id,
                            "rank": 1,
                            "explanation": "Mock explanation for smoke test.",
                        }
                    ],
                    "summary": "Mock summary.",
                }
            )
            ranker = LLMRankingService(provider=MockLLMProvider(mock_json))
        else:
            ranker = LLMRankingService()

        ranking = ranker.rank(filter_result.preferences, filter_result.candidates)

    except PreferenceValidationError as exc:
        for field, msg in exc.errors.items():
            print(f"{field}: {msg}", file=sys.stderr)
        return 1
    except LLMProviderError as exc:
        print(f"Groq error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        out = {
            "summary": ranking.summary,
            "meta": ranking.meta,
            "recommendations": [
                {
                    "rank": r["rank"],
                    "name": r["restaurant"].name,
                    "rating": r["restaurant"].rating,
                    "explanation": r["explanation"],
                }
                for r in ranking.recommendations
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    print(f"Provider: {ranking.meta.get('llm_provider')} / {ranking.meta.get('llm_model')}")
    print(f"Fallback: {ranking.meta.get('llm_fallback')}")
    if ranking.summary:
        print(f"\nSummary: {ranking.summary}\n")
    for rec in ranking.recommendations:
        r = rec["restaurant"]
        print(f"#{rec['rank']} {r.name} ({r.rating}) — {rec['explanation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
