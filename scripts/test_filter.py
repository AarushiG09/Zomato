#!/usr/bin/env python3
"""Manual smoke test for Phase 3 filter service."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.models import BudgetTier
from src.data.repository import RestaurantRepository
from src.services.exceptions import PreferenceValidationError
from src.services.filter import RestaurantFilterService


def main() -> int:
    parser = argparse.ArgumentParser(description="Test restaurant filter service")
    parser.add_argument("--location", default="Bangalore", help="City")
    parser.add_argument(
        "--budget",
        default="medium",
        choices=["low", "medium", "high"],
        help="Budget tier",
    )
    parser.add_argument("--cuisine", default="North Indian", help="Cuisine or 'any'")
    parser.add_argument("--min-rating", type=float, default=4.0, help="Minimum rating")
    parser.add_argument("--top-k", type=int, default=5, help="Top K (for prefs only)")
    parser.add_argument(
        "--additional",
        nargs="*",
        default=[],
        help="Additional preference tags",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full result as JSON",
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
        service = RestaurantFilterService(repo)
        result = service.filter(prefs)
    except PreferenceValidationError as exc:
        print("Validation failed:", file=sys.stderr)
        for field, msg in exc.errors.items():
            print(f"  {field}: {msg}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "is_empty": result.is_empty,
            "total_matched": result.total_matched,
            "returned": len(result.candidates),
            "capped": result.capped,
            "empty_hints": result.empty_hints,
            "preferences": result.preferences.model_dump(),
            "candidates": [
                {
                    "id": r.id,
                    "name": r.name,
                    "city": r.city,
                    "cuisines": r.cuisines,
                    "rating": r.rating,
                    "budget_tier": r.budget_tier.value,
                    "cost_display": r.estimated_cost_display,
                }
                for r in result.candidates
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Location: {result.preferences.location}")
    print(f"Cuisine:  {result.preferences.cuisine}")
    print(f"Budget:   {result.preferences.budget.value}")
    print(f"Matched:  {result.total_matched} (returning {len(result.candidates)})")
    if result.capped:
        print(f"(capped to {service.max_candidates} for LLM)")
    if result.is_empty:
        print("\nNo matches. Suggestions:")
        for hint in result.empty_hints:
            print(f"  - {hint}")
        return 0

    print("\nTop candidates:")
    for i, r in enumerate(result.candidates[:10], start=1):
        cuisines = ", ".join(r.cuisines[:3])
        print(
            f"  {i}. {r.name} | {r.rating} | {r.budget_tier.value} | "
            f"{cuisines} | {r.estimated_cost_display}"
        )
    if len(result.candidates) > 10:
        print(f"  ... and {len(result.candidates) - 10} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
