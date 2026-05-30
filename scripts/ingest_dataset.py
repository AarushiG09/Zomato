#!/usr/bin/env python3
"""CLI entry point for dataset ingestion (Phase 1)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Allow running as: python scripts/ingest_dataset.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Use project-local Hugging Face cache (avoids permission issues in restricted envs)
_hf_cache = PROJECT_ROOT / ".hf_cache"
_hf_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(_hf_cache))
os.environ.setdefault("HF_DATASETS_CACHE", str(_hf_cache))

from src.data.ingest import run_ingestion, verify_database


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Zomato restaurant data from Hugging Face into SQLite."
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Hugging Face dataset id (default: HF_DATASET_NAME env)",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Output SQLite path (default: DATABASE_PATH env)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        stats = run_ingestion(
            dataset_name=args.dataset,
            database_path=args.database,
        )
        check = verify_database(stats.database_path)

        print("\n=== Ingestion Summary ===")
        print(f"Raw rows loaded:     {stats.raw_rows}")
        print(f"Rows dropped:        {stats.dropped_rows}")
        print(f"Rows persisted:      {stats.persisted_rows}")
        print(f"Distinct cities:     {stats.cities_count}")
        print(f"Database path:       {stats.database_path}")
        print(f"Verification OK:     {check['ok']}")

        if not check["ok"]:
            print(f"Verification details: {check}")
            return 1
        return 0
    except Exception as exc:
        logging.exception("Ingestion failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
