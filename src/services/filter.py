"""Pre-LLM restaurant filtering (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from src.config import MAX_CANDIDATES_FOR_LLM
from src.data.models import BudgetTier, Restaurant, UserPreferences
from src.data.repository import RestaurantRepository
from src.services.validation import PreferenceValidator

EMPTY_HINTS = [
    "No restaurants match your filters.",
    "Try a lower minimum rating.",
    "Try a different cuisine (or use 'any').",
    "Try another budget tier (low, medium, high).",
]

_BUDGET_ORDER = [BudgetTier.LOW, BudgetTier.MEDIUM, BudgetTier.HIGH]


@dataclass
class FilterResult:
    """Structured output from the filter service."""

    preferences: UserPreferences
    candidates: list[Restaurant] = field(default_factory=list)
    total_matched: int = 0
    capped: bool = False
    is_empty: bool = False
    empty_hints: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls, preferences: UserPreferences) -> FilterResult:
        return cls(
            preferences=preferences,
            candidates=[],
            total_matched=0,
            capped=False,
            is_empty=True,
            empty_hints=list(EMPTY_HINTS),
        )


class RestaurantFilterService:
    """Validate preferences, query repository, sort, and cap candidates."""

    def __init__(
        self,
        repository: RestaurantRepository,
        *,
        max_candidates: Optional[int] = None,
        budget_soft: bool = True,
    ) -> None:
        self.repository = repository
        self.validator = PreferenceValidator(repository)
        self.max_candidates = max_candidates or MAX_CANDIDATES_FOR_LLM
        self.budget_soft = budget_soft

    def filter(
        self,
        preferences: Union[UserPreferences, dict],
        *,
        skip_validation: bool = False,
    ) -> FilterResult:
        """
        Apply hard filters and return up to max_candidates restaurants.

        Does not call the LLM. Returns structured empty result when no matches.
        """
        prefs = (
            preferences
            if skip_validation and isinstance(preferences, UserPreferences)
            else self.validator.validate(preferences)
        )

        raw_matches = self.repository.query_candidates(
            location=prefs.location,
            cuisine=prefs.cuisine,
            min_rating=prefs.min_rating,
            budget=prefs.budget,
            budget_soft=self.budget_soft,
        )

        if not raw_matches:
            return FilterResult.empty(prefs)

        sorted_matches = sorted(
            raw_matches,
            key=lambda r: (
                -r.rating,
                _budget_distance(prefs.budget, r.budget_tier),
                r.name.lower(),
            ),
        )

        # Deduplicate candidates by restaurant name (case-insensitive) to prevent duplicates
        deduped_matches = []
        seen_names = set()
        for r in sorted_matches:
            name_lower = r.name.lower().strip()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                deduped_matches.append(r)
        sorted_matches = deduped_matches

        total_matched = len(sorted_matches)
        capped = total_matched > self.max_candidates
        candidates = sorted_matches[: self.max_candidates]

        return FilterResult(
            preferences=prefs,
            candidates=candidates,
            total_matched=total_matched,
            capped=capped,
            is_empty=False,
            empty_hints=[],
        )


def _budget_distance(preferred: BudgetTier, actual: BudgetTier) -> int:
    """Lower is better: 0 = exact tier match."""
    try:
        return abs(_BUDGET_ORDER.index(preferred) - _BUDGET_ORDER.index(actual))
    except ValueError:
        return 99
