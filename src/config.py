"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root explicitly (reliable across CWDs)
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

HF_DATASET_NAME: str = os.getenv(
    "HF_DATASET_NAME", "ManikaSaini/zomato-restaurant-recommendation"
)
DATABASE_PATH: Path = Path(
    os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "restaurants.db"))
)
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = PROJECT_ROOT / DATABASE_PATH

# Groq LLM (Phase 4+)
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
GROQ_MODEL: str = os.getenv(
    "GROQ_MODEL", os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
)
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com")

MAX_CANDIDATES_FOR_LLM: int = int(os.getenv("MAX_CANDIDATES_FOR_LLM", "30"))
DEFAULT_TOP_K: int = int(os.getenv("DEFAULT_TOP_K", "5"))

LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# Budget tier percentiles (used during ingestion)
BUDGET_LOW_PERCENTILE: float = float(os.getenv("BUDGET_LOW_PERCENTILE", "33"))
BUDGET_HIGH_PERCENTILE: float = float(os.getenv("BUDGET_HIGH_PERCENTILE", "67"))
