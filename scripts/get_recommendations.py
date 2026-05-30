#!/usr/bin/env python3
"""CLI tool: Get end-to-end restaurant recommendations (Phase 5)."""

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
from src.services.llm import LLMProviderError, MockLLMProvider
from src.services.ranker import LLMRankingService
from src.services.recommender import RecommendationService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Get AI-powered restaurant recommendations E2E"
    )
    parser.add_argument("--location", default="Bangalore")
    parser.add_argument(
        "--budget", default="medium", choices=["low", "medium", "high"]
    )
    parser.add_argument("--cuisine", default="North Indian")
    parser.add_argument("--min-rating", type=float, default=4.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--additional",
        action="append",
        default=[],
        help="Additional preference keywords or notes (can repeat)",
    )
    parser.add_argument(
        "--mock", action="store_true", help="Use MockLLMProvider (no API key)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print raw response JSON"
    )
    args = parser.parse_args()

    prefs = {
        "location": args.location,
        "budget": args.budget,
        "cuisine": args.cuisine,
        "min_rating": args.min_rating,
        "top_k": args.top_k,
        "additional": args.additional,
    }

    try:
        repo = RestaurantRepository()

        if args.mock:
            # Construct a clean mock response matching standard format
            mock_json = json.dumps(
                {
                    "ranked": [
                        {
                            "restaurant_id": "r1",  # Will get matched in mock logic or fallback
                            "rank": 1,
                            "explanation": "Mock explanation for get_recommendations CLI smoke test.",
                        }
                    ],
                    "summary": "Mock recommendation summary.",
                }
            )
            provider = MockLLMProvider(mock_json)
            ranking_service = LLMRankingService(provider=provider)
        else:
            ranking_service = LLMRankingService()

        service = RecommendationService(
            repository=repo,
            ranking_service=ranking_service,
        )
        response = service.recommend(prefs)

    except PreferenceValidationError as exc:
        print("Validation Error:", file=sys.stderr)
        for field, msg in exc.errors.items():
            print(f"  {field}: {msg}", file=sys.stderr)
        return 1
    except LLMProviderError as exc:
        print(f"LLM Provider Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(response.model_dump_json(indent=2))
        return 0

    print("=" * 60)
    print(
        f"AI RECOMMENDATIONS FOR {response.preferences.location.upper()} ({response.preferences.cuisine.title()})"
    )
    print("=" * 60)
    print(f"Preferences  : Rating >= {response.preferences.min_rating} | Budget: {response.preferences.budget.value.title()}")
    if response.preferences.additional:
        print(f"Additional   : {', '.join(response.preferences.additional)}")
    print(f"LLM Details  : {response.meta.llm_provider} ({response.meta.llm_model}) [Fallback: {response.meta.llm_fallback}]")
    print(f"Latency      : {f'{response.meta.llm_latency_ms:.0f} ms' if response.meta.llm_latency_ms else 'N/A'}")
    print(f"Candidates Considered: {response.meta.candidates_considered}")
    print("-" * 60)

    if response.summary:
        print(f"Summary      : {response.summary}")
        print("-" * 60)

    if not response.recommendations:
        print("No matching restaurants found based on your filters.")
        return 0

    for rec in response.recommendations:
        r = rec.restaurant
        print(f"#{rec.rank} {r.name} ({r.rating} ★) — {r.estimated_cost_display}")
        print(f"   Cuisines: {', '.join(r.cuisines)}")
        print(f"   AI Note : {rec.explanation}")
        print("-" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
