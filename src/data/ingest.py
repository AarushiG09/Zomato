"""
Data ingestion pipeline for the Zomato restaurant dataset.

Raw Hugging Face schema (ManikaSaini/zomato-restaurant-recommendation):
  - name: restaurant name
  - location: locality / area within city
  - listed_in(city): city listing (e.g. Bangalore) — preferred for `city`
  - cuisines: comma-separated cuisine string
  - rate: rating string, often "4.1/5" or "-" or "NEW"
  - approx_cost(for two people): cost for two (may include commas, ranges)
  - address, votes, rest_type, etc. stored in metadata JSON
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset

from src.config import (
    BUDGET_HIGH_PERCENTILE,
    BUDGET_LOW_PERCENTILE,
    DATABASE_PATH,
    HF_DATASET_NAME,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)

TABLE_NAME = "restaurants"

# Column aliases: first match in the raw frame wins
COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["name", "restaurant_name"],
    "city": ["listed_in(city)", "listed_in_city", "city", "City"],
    "locality": ["location", "Location", "locality"],
    "cuisines": ["cuisines", "Cuisines"],
    "rate": ["rate", "rating", "Rating", "aggregate_rating"],
    "cost": [
        "approx_cost(for two people)",
        "approx_cost_for_two_people",
        "approx_cost",
        "average_cost_for_two",
        "cost_for_two",
    ],
}

CITY_ALIASES: dict[str, str] = {
    "bengaluru": "Bangalore",
    "bangalore": "Bangalore",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "delhi": "New Delhi",
    "new delhi": "New Delhi",
}

BUDGET_TIERS = ("low", "medium", "high")

METADATA_COLUMNS = (
    "address",
    "votes",
    "rest_type",
    "online_order",
    "book_table",
    "phone",
    "url",
    "dish_liked",
    "listed_in(type)",
    "listed_in_type",
)


@dataclass
class IngestionStats:
    raw_rows: int
    dropped_rows: int
    persisted_rows: int
    cities_count: int
    database_path: Path


def _resolve_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias in df.columns:
            return alias
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def _extract_city_from_address(address: Any) -> str | None:
    """Parse metro city from address (e.g. '..., Banashankari, Bangalore')."""
    if address is None or (isinstance(address, float) and pd.isna(address)):
        return None
    text = str(address)
    for token in reversed(re.split(r"[,;]", text)):
        token = token.strip()
        if not token:
            continue
        key = token.casefold()
        if key in CITY_ALIASES:
            return CITY_ALIASES[key]
        # Known metro names in title case
        if key in {k.casefold() for k in CITY_ALIASES.values()}:
            return CITY_ALIASES.get(key, token.title())
        if key in ("bangalore", "bengaluru", "mumbai", "delhi", "new delhi", "chennai", "hyderabad", "pune", "kolkata"):
            return CITY_ALIASES.get(key, token.title())
    return None


def _normalize_city(
    listed_city: Any,
    locality: Any | None = None,
    address: Any | None = None,
) -> str | None:
    """
    Resolve neighborhood / locality name (e.g. Indiranagar, Banashankari) for filtering.
    """
    for candidate in (listed_city, locality):
        if candidate is not None and not (isinstance(candidate, float) and pd.isna(candidate)):
            text = str(candidate).strip()
            if text:
                return text
    return None



def _parse_rating(value: Any) -> float | None:
    """Parse rating from formats like 4.1/5, 4.1, NEW, -."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text in {"-", "NEW", "new", "nan"}:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    rating = float(match.group(1))
    if "/5" in text and rating <= 5.0:
        return round(rating, 2)
    if rating > 5.0:
        return None
    return round(min(max(rating, 0.0), 5.0), 2)


def _parse_cost(value: Any) -> int | None:
    """Extract numeric cost for two; handles commas and simple ranges (300-400)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if not text or text in {"-", "nan"}:
        return None
    numbers = re.findall(r"\d+", text.replace(",", ""))
    if not numbers:
        return None
    nums = [int(n) for n in numbers]
    return int(sum(nums) / len(nums))


def _split_cuisines(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    parts = re.split(r"[,;]", str(value))
    return [p.strip() for p in parts if p.strip()]


def _assign_budget_tiers(costs: pd.Series) -> pd.Series:
    """Map numeric cost to low/medium/high using dataset percentiles."""
    valid = costs.dropna()
    if valid.empty:
        return pd.Series(["medium"] * len(costs), index=costs.index)

    low_cut = valid.quantile(BUDGET_LOW_PERCENTILE / 100.0)
    high_cut = valid.quantile(BUDGET_HIGH_PERCENTILE / 100.0)

    def tier(cost: Any) -> str:
        if cost is None or (isinstance(cost, float) and pd.isna(cost)):
            return "medium"
        if cost <= low_cut:
            return "low"
        if cost >= high_cut:
            return "high"
        return "medium"

    return costs.apply(tier)


def _build_metadata_row(row: pd.Series, raw_columns: list[str]) -> str:
    meta: dict[str, Any] = {}
    for col in raw_columns:
        if col in METADATA_COLUMNS or col not in {
            "name",
            "city",
            "cuisines",
            "rate",
            "cost",
        }:
            val = row.get(col)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                meta[col] = val if not isinstance(val, (dict, list)) else str(val)
    return json.dumps(meta, ensure_ascii=False)


def load_raw_dataset(dataset_name: str | None = None) -> pd.DataFrame:
    """Load the Hugging Face dataset into a pandas DataFrame."""
    name = dataset_name or HF_DATASET_NAME
    logger.info("Loading dataset from Hugging Face: %s", name)
    dataset = load_dataset(name, split="train")
    df = dataset.to_pandas()
    logger.info("Loaded %d raw rows", len(df))
    return df


def normalize_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Normalize raw dataset rows to the canonical restaurant schema.

    Returns:
        (normalized_df, dropped_count)
    """
    col_name = _resolve_column(df, COLUMN_ALIASES["name"])
    col_city = _resolve_column(df, COLUMN_ALIASES["city"])
    col_locality = _resolve_column(df, COLUMN_ALIASES["locality"])
    col_address = _resolve_column(df, ["address", "Address"])
    col_cuisines = _resolve_column(df, COLUMN_ALIASES["cuisines"])
    col_rate = _resolve_column(df, COLUMN_ALIASES["rate"])
    col_cost = _resolve_column(df, COLUMN_ALIASES["cost"])

    if not col_name:
        raise ValueError(
            f"Could not find restaurant name column. Available: {list(df.columns)}"
        )

    records: list[dict[str, Any]] = []
    dropped = 0

    for idx, row in df.iterrows():
        name_val = row.get(col_name)
        if name_val is None or (isinstance(name_val, float) and pd.isna(name_val)):
            dropped += 1
            continue
        name = str(name_val).strip()
        if not name:
            dropped += 1
            continue

        locality = row.get(col_locality) if col_locality else None
        city_val = row.get(col_city) if col_city else None
        address = row.get(col_address) if col_address else None
        city = _normalize_city(city_val, locality, address)
        if not city:
            dropped += 1
            continue

        rating = _parse_rating(row.get(col_rate) if col_rate else None)
        if rating is None:
            dropped += 1
            continue

        cuisines = _split_cuisines(row.get(col_cuisines) if col_cuisines else None)
        cost = _parse_cost(row.get(col_cost) if col_cost else None)

        records.append(
            {
                "name": name,
                "city": city,
                "cuisines": json.dumps(cuisines, ensure_ascii=False),
                "rating": rating,
                "cost_for_two": cost,
                "metadata": _build_metadata_row(row, list(df.columns)),
                "_source_index": int(idx),
            }
        )

    if not records:
        raise ValueError("No valid rows after normalization")

    out = pd.DataFrame(records)
    # Deduplicate by name and city/locality, keeping the highest rated entry
    out = out.sort_values(by="rating", ascending=False)
    out = out.drop_duplicates(subset=["name", "city"], keep="first")
    
    out["budget_tier"] = _assign_budget_tiers(out["cost_for_two"])
    out["id"] = out.apply(
        lambda r: f"zomato-{r['_source_index']}-{hash((r['name'], r['city'])) % 10**8}",
        axis=1,
    )
    out = out.drop(columns=["_source_index"])
    out = out[
        [
            "id",
            "name",
            "city",
            "cuisines",
            "rating",
            "cost_for_two",
            "budget_tier",
            "metadata",
        ]
    ]
    return out, dropped


def persist_to_sqlite(df: pd.DataFrame, database_path: Path | None = None) -> Path:
    """Persist restaurants to SQLite (idempotent: replaces table)."""
    db_path = database_path or DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        df.to_sql(TABLE_NAME, conn, if_exists="replace", index=False)
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_restaurants_city ON {TABLE_NAME}(city)"
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON {TABLE_NAME}(rating)"
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_restaurants_budget ON {TABLE_NAME}(budget_tier)"
        )
        conn.commit()

    logger.info("Persisted %d rows to %s", len(df), db_path)
    return db_path


def run_ingestion(
    dataset_name: str | None = None,
    database_path: Path | None = None,
) -> IngestionStats:
    """Full pipeline: load → normalize → persist."""
    raw_df = load_raw_dataset(dataset_name)
    raw_rows = len(raw_df)
    normalized_df, dropped = normalize_dataframe(raw_df)
    db_path = persist_to_sqlite(normalized_df, database_path)
    cities_count = normalized_df["city"].nunique()

    stats = IngestionStats(
        raw_rows=raw_rows,
        dropped_rows=dropped,
        persisted_rows=len(normalized_df),
        cities_count=cities_count,
        database_path=db_path,
    )

    logger.info(
        "Ingestion complete: raw=%d dropped=%d persisted=%d cities=%d db=%s",
        stats.raw_rows,
        stats.dropped_rows,
        stats.persisted_rows,
        stats.cities_count,
        stats.database_path,
    )
    return stats


def verify_database(database_path: Path | None = None) -> dict[str, Any]:
    """Verify persisted data meets Phase 1 acceptance criteria."""
    db_path = database_path or DATABASE_PATH
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        count = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
        nulls = conn.execute(
            f"""
            SELECT COUNT(*) FROM {TABLE_NAME}
            WHERE name IS NULL OR city IS NULL OR rating IS NULL
            """
        ).fetchone()[0]
        invalid_tiers = conn.execute(
            f"""
            SELECT COUNT(*) FROM {TABLE_NAME}
            WHERE budget_tier NOT IN ('low', 'medium', 'high')
            """
        ).fetchone()[0]

    return {
        "row_count": count,
        "null_required_fields": nulls,
        "invalid_budget_tiers": invalid_tiers,
        "ok": count > 0 and nulls == 0 and invalid_tiers == 0,
    }
