"""Shared pytest fixtures."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": "Test Bistro",
                "listed_in(city)": "Koramangala",
                "location": "Koramangala",
                "cuisines": "Italian, Cafe",
                "rate": "4.5/5",
                "approx_cost(for two people)": "800",
                "address": "123 Main St, Koramangala, Bangalore",
                "votes": 100,
            },
            {
                "name": "Budget Eats",
                "listed_in(city)": "Indiranagar",
                "location": "Indiranagar",
                "cuisines": "Chinese",
                "rate": "3.8/5",
                "approx_cost(for two people)": "200",
                "address": "100 12th Main, Indiranagar, Bengaluru",
            },
            {
                "name": "No Rating Place",
                "listed_in(city)": "Bangalore",
                "cuisines": "Indian",
                "rate": "-",
                "approx_cost(for two people)": "500",
            },
            {
                "name": "",
                "listed_in(city)": "Bangalore",
                "rate": "4.0/5",
                "approx_cost(for two people)": "600",
            },
        ]
    )
