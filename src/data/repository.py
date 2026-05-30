"""SQLite repository for restaurant records."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.config import DATABASE_PATH
from src.data.exceptions import DatasetNotFoundError
from src.data.ingest import TABLE_NAME
from src.data.models import BudgetTier, Restaurant

# Align with ingest city normalization
CITY_ALIASES: dict[str, str] = {
    "bengaluru": "Bangalore",
    "bangalore": "Bangalore",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "delhi": "New Delhi",
    "new delhi": "New Delhi",
}


def normalize_location(location: str) -> str:
    """Normalize user/API location to canonical city name."""
    text = location.strip()
    if not text:
        return text
    return CITY_ALIASES.get(text.casefold(), text)


class RestaurantRepository:
    """Read-only access to persisted restaurant data."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or DATABASE_PATH
        self._ensure_database()

    def _ensure_database(self) -> None:
        if not self.database_path.exists():
            raise DatasetNotFoundError(str(self.database_path))
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (TABLE_NAME,),
            ).fetchone()
            if not row or row[0] == 0:
                raise DatasetNotFoundError(str(self.database_path))
            count = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
            if count == 0:
                raise DatasetNotFoundError(str(self.database_path))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def count_all(self) -> int:
        """Return the total number of restaurants in the database."""
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()
            return row[0] if row else 0


    @staticmethod
    def _row_to_restaurant(row: sqlite3.Row) -> Restaurant:
        return Restaurant(
            id=row["id"],
            name=row["name"],
            city=row["city"],
            cuisines=row["cuisines"],
            rating=row["rating"],
            cost_for_two=row["cost_for_two"],
            budget_tier=row["budget_tier"],
            metadata=row["metadata"],
        )

    def get_all(self) -> list[Restaurant]:
        """Return all restaurants ordered by rating descending."""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM {TABLE_NAME}
                ORDER BY rating DESC, name ASC
                """
            ).fetchall()
        return [self._row_to_restaurant(row) for row in rows]

    def get_by_city(self, city: str) -> list[Restaurant]:
        """Return restaurants in a city (case-insensitive)."""
        normalized = normalize_location(city)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM {TABLE_NAME}
                WHERE LOWER(city) = LOWER(?)
                ORDER BY rating DESC, name ASC
                """,
                (normalized,),
            ).fetchall()
        return [self._row_to_restaurant(row) for row in rows]

    def list_cities(self) -> list[str]:
        """Distinct cities in the database, sorted alphabetically."""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT city FROM {TABLE_NAME}
                ORDER BY city ASC
                """
            ).fetchall()
        return [row[0] for row in rows]

    def query_candidates(
        self,
        location: str,
        cuisine: str,
        min_rating: float,
        budget: BudgetTier | str,
        *,
        budget_soft: bool = False,
    ) -> list[Restaurant]:
        """
        Filter restaurants by location, cuisine, minimum rating, and budget.

        Args:
            location: City name (case-insensitive, alias-aware).
            cuisine: Cuisine to match; use "any" to skip cuisine filter.
            min_rating: Minimum rating inclusive.
            budget: Required budget tier.
            budget_soft: If True, also include adjacent budget tiers.
        """
        normalized_city = normalize_location(location)
        budget_value = (
            budget.value if isinstance(budget, BudgetTier) else str(budget).lower()
        )
        budget_tiers = _budget_tiers_for_query(budget_value, soft=budget_soft)

        placeholders = ",".join("?" for _ in budget_tiers)
        params: list[Any] = [normalized_city, min_rating, *budget_tiers]

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM {TABLE_NAME}
                WHERE LOWER(city) = LOWER(?)
                  AND rating >= ?
                  AND budget_tier IN ({placeholders})
                ORDER BY rating DESC, name ASC
                """,
                params,
            ).fetchall()

        restaurants = [self._row_to_restaurant(row) for row in rows]

        cuisine_query = cuisine.strip()
        if cuisine_query and cuisine_query.lower() != "any":
            restaurants = [r for r in restaurants if r.matches_cuisine(cuisine_query)]

        return restaurants


def _budget_tiers_for_query(budget: str, *, soft: bool) -> list[str]:
    """Exact tier or adjacent tiers for soft budget matching."""
    budget = budget.lower()
    if not soft:
        return [budget]

    order = [BudgetTier.LOW.value, BudgetTier.MEDIUM.value, BudgetTier.HIGH.value]
    if budget not in order:
        return [budget]
    idx = order.index(budget)
    tiers = [order[idx]]
    if idx > 0:
        tiers.append(order[idx - 1])
    if idx < len(order) - 1:
        tiers.append(order[idx + 1])
    return list(dict.fromkeys(tiers))
