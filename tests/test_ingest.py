"""Tests for Phase 1 data ingestion pipeline."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.data.ingest import (
    BUDGET_TIERS,
    TABLE_NAME,
    _assign_budget_tiers,
    _parse_cost,
    _parse_rating,
    _split_cuisines,
    normalize_dataframe,
    persist_to_sqlite,
    verify_database,
)


class TestParsingHelpers:
    def test_parse_rating_formats(self):
        assert _parse_rating("4.1/5") == 4.1
        assert _parse_rating("NEW") is None
        assert _parse_rating("-") is None

    def test_parse_cost_formats(self):
        assert _parse_cost("1,200") == 1200
        assert _parse_cost("300-400") == 350

    def test_split_cuisines(self):
        assert _split_cuisines("North Indian, Chinese") == [
            "North Indian",
            "Chinese",
        ]


class TestBudgetTierMapping:
    def test_assign_budget_tiers_uses_percentiles(self):
        costs = pd.Series([100, 200, 300, 400, 500, 600, 700, 800, 900])
        tiers = _assign_budget_tiers(costs)
        assert set(tiers.unique()).issubset(set(BUDGET_TIERS))
        assert tiers.iloc[0] == "low"
        assert tiers.iloc[-1] == "high"

    def test_missing_cost_defaults_to_medium(self):
        costs = pd.Series([None, None])
        tiers = _assign_budget_tiers(costs)
        assert list(tiers) == ["medium", "medium"]


class TestNormalizeDataframe:
    def test_drops_invalid_rows(self, sample_raw_df: pd.DataFrame):
        normalized, dropped = normalize_dataframe(sample_raw_df)
        assert dropped >= 2  # no rating + empty name
        assert len(normalized) == 2
        assert set(normalized.columns) >= {
            "id",
            "name",
            "city",
            "cuisines",
            "rating",
            "budget_tier",
        }

    def test_city_from_address(self):
        df = pd.DataFrame(
            [
                {
                    "name": "Addr Test",
                    "listed_in(city)": "Banashankari",
                    "location": "Banashankari",
                    "address": "21st Main, Banashankari, Bangalore",
                    "cuisines": "Indian",
                    "rate": "4.0/5",
                    "approx_cost(for two people)": "500",
                }
            ]
        )
        normalized, _ = normalize_dataframe(df)
        assert normalized.iloc[0]["city"] == "Banashankari"

    def test_required_fields_present(self, sample_raw_df: pd.DataFrame):
        normalized, _ = normalize_dataframe(sample_raw_df)
        assert normalized["name"].notna().all()
        assert normalized["city"].notna().all()
        assert normalized["rating"].notna().all()
        assert normalized["budget_tier"].isin(BUDGET_TIERS).all()

    def test_cuisines_stored_as_json_list(self, sample_raw_df: pd.DataFrame):
        normalized, _ = normalize_dataframe(sample_raw_df)
        cuisines = json.loads(normalized.iloc[0]["cuisines"])
        assert "Italian" in cuisines


class TestPersistAndVerify:
    def test_persist_idempotent_replace(self, sample_raw_df: pd.DataFrame):
        normalized, _ = normalize_dataframe(sample_raw_df)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            persist_to_sqlite(normalized, db_path)
            first_count = verify_database(db_path)["row_count"]
            persist_to_sqlite(normalized, db_path)
            second_count = verify_database(db_path)["row_count"]
            assert first_count == second_count == len(normalized)

    def test_verify_database_checks(self, sample_raw_df: pd.DataFrame):
        normalized, _ = normalize_dataframe(sample_raw_df)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            persist_to_sqlite(normalized, db_path)
            result = verify_database(db_path)
            assert result["ok"] is True
            assert result["row_count"] > 0

            with sqlite3.connect(db_path) as conn:
                tiers = {
                    row[0]
                    for row in conn.execute(
                        f"SELECT DISTINCT budget_tier FROM {TABLE_NAME}"
                    )
                }
            assert tiers.issubset(set(BUDGET_TIERS))


class TestIngestionThreshold:
    """Integration test against real DB if present (optional)."""

    @pytest.mark.integration
    def test_production_db_row_count(self):
        from src.config import DATABASE_PATH

        if not DATABASE_PATH.exists():
            pytest.skip("Run scripts/ingest_dataset.py first")
        result = verify_database(DATABASE_PATH)
        assert result["row_count"] > 1000
