"""User preference validation (Phase 3)."""

from __future__ import annotations

import difflib
from typing import Any, Union

from pydantic import ValidationError as PydanticValidationError

from src.data.models import BudgetTier, UserPreferences
from src.data.repository import RestaurantRepository, normalize_location
from src.services.exceptions import PreferenceValidationError

MAX_ADDITIONAL_LENGTH = 500
MAX_TOP_K = 20
MIN_TOP_K = 1


class PreferenceValidator:
    """Validate and normalize user preferences against the restaurant store."""

    def __init__(self, repository: RestaurantRepository) -> None:
        self.repository = repository
        self._known_cities = repository.list_cities()

    def validate(
        self,
        preferences: Union[UserPreferences, dict[str, Any]],
    ) -> UserPreferences:
        """
        Validate preferences and return a normalized UserPreferences instance.

        Raises:
            PreferenceValidationError: field-level validation failures.
        """
        errors: dict[str, str] = {}

        try:
            if isinstance(preferences, dict):
                prefs = UserPreferences.model_validate(preferences)
            else:
                prefs = preferences
        except PydanticValidationError as exc:
            for err in exc.errors():
                loc = err.get("loc", ())
                field = str(loc[0]) if loc else "preferences"
                errors[field] = err.get("msg", "Invalid value")
            raise PreferenceValidationError(errors) from exc

        normalized_location = normalize_location(prefs.location)
        matched_city = None
        if normalized_location:
            for city in self._known_cities:
                if city.casefold() == normalized_location.casefold():
                    matched_city = city
                    break

        if not normalized_location:
            errors["location"] = "Location is required."
        elif not matched_city:
            suggestion = self._suggest_city(normalized_location)
            if suggestion:
                errors["location"] = (
                    f"City '{prefs.location}' not found. Did you mean '{suggestion}'?"
                )
            else:
                available = ", ".join(self._known_cities[:8])
                suffix = "..." if len(self._known_cities) > 8 else ""
                errors["location"] = (
                    f"City '{prefs.location}' is not in the dataset. "
                    f"Available cities include: {available}{suffix}"
                )
        else:
            normalized_location = matched_city

        if prefs.top_k < MIN_TOP_K or prefs.top_k > MAX_TOP_K:
            errors["top_k"] = f"top_k must be between {MIN_TOP_K} and {MAX_TOP_K}."

        if prefs.min_rating < 0.0 or prefs.min_rating > 5.0:
            errors["min_rating"] = "min_rating must be between 0.0 and 5.0."

        cuisine = (prefs.cuisine or "").strip()
        if not cuisine:
            errors["cuisine"] = "Cuisine is required. Use 'any' to skip cuisine filtering."

        combined_additional = " ".join(prefs.additional)
        if len(combined_additional) > MAX_ADDITIONAL_LENGTH:
            errors["additional"] = (
                f"Additional preferences must be at most {MAX_ADDITIONAL_LENGTH} characters."
            )

        if errors:
            raise PreferenceValidationError(errors)

        return prefs.model_copy(
            update={
                "location": normalized_location,
                "cuisine": cuisine,
            }
        )

    def _city_known(self, normalized_city: str) -> bool:
        known_lower = {c.casefold() for c in self._known_cities}
        return normalized_city.casefold() in known_lower

    def _suggest_city(self, location: str) -> str | None:
        if not self._known_cities:
            return None
        matches = difflib.get_close_matches(
            location,
            self._known_cities,
            n=1,
            cutoff=0.6,
        )
        return matches[0] if matches else None
