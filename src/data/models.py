"""Canonical domain models for the recommendation system."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from src.config import DEFAULT_TOP_K


class BudgetTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Restaurant(BaseModel):
    """Normalized restaurant record from the local store."""

    id: str
    name: str
    city: str
    cuisines: list[str]
    rating: float = Field(ge=0.0, le=5.0)
    cost_for_two: Optional[int] = None
    budget_tier: BudgetTier
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("cuisines", mode="before")
    @classmethod
    def parse_cuisines(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(c).strip() for c in value if str(c).strip()]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(c).strip() for c in parsed if str(c).strip()]
            except json.JSONDecodeError:
                pass
            return [c.strip() for c in value.split(",") if c.strip()]
        return []

    @field_validator("budget_tier", mode="before")
    @classmethod
    def parse_budget_tier(cls, value: Any) -> BudgetTier:
        if isinstance(value, BudgetTier):
            return value
        return BudgetTier(str(value).lower())

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def matches_cuisine(self, cuisine_query: str) -> bool:
        """True if any cuisine token matches the query (case-insensitive)."""
        if not cuisine_query or cuisine_query.strip().lower() == "any":
            return True
        needle = cuisine_query.strip().casefold()
        for cuisine in self.cuisines:
            hay = cuisine.casefold()
            if needle == hay or needle in hay or hay in needle:
                return True
        return False

    @property
    def estimated_cost_display(self) -> str:
        if self.cost_for_two is not None:
            return f"₹{self.cost_for_two:,} for two"
        return f"{self.budget_tier.value.title()} budget"


class UserPreferences(BaseModel):
    """User input for restaurant recommendations (validated in Phase 3)."""

    location: str
    budget: BudgetTier
    cuisine: str = ""
    min_rating: float = Field(default=3.5, ge=0.0, le=5.0)
    additional: list[str] = Field(default_factory=list)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20)

    @field_validator("location", "cuisine", mode="before")
    @classmethod
    def strip_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("additional", mode="before")
    @classmethod
    def normalize_additional(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [str(v).strip() for v in value if str(v).strip()]
