# Zomato AI Restaurant Recommendation System

AI-powered restaurant recommendations using the Zomato Hugging Face dataset and an LLM.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Phase 1: Ingest dataset

Downloads [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) and writes `data/restaurants.db`.

```bash
python scripts/ingest_dataset.py
```

Options:

- `--dataset` — override Hugging Face dataset id
- `--database` — override output SQLite path
- `-v` — verbose logging

## Phase 4: Groq LLM ranking

Set `GROQ_API_KEY` in `.env` (see `.env.example`). Then:

```bash
pip install -r requirements.txt
python scripts/test_llm_rank.py --mock          # no API key needed
python scripts/test_llm_rank.py                 # live Groq call
python scripts/test_llm_rank.py --json --mock
```

## Phase 3: Filter service

Validate preferences and get capped candidates (no LLM yet):

```python
from src.data import RestaurantRepository
from src.services import RestaurantFilterService

repo = RestaurantRepository()
service = RestaurantFilterService(repo)
result = service.filter({
    "location": "Bangalore",
    "budget": "medium",
    "cuisine": "North Indian",
    "min_rating": 4.0,
})
```

CLI smoke test:

```bash
python scripts/test_filter.py --location Bangalore --cuisine "North Indian" --min-rating 4.0
python scripts/test_filter.py --json
```

## Phase 2: Repository

Query restaurants from the local SQLite database:

```python
from src.data import RestaurantRepository, BudgetTier

repo = RestaurantRepository()
cities = repo.list_cities()
candidates = repo.query_candidates(
    location="Bangalore",
    cuisine="North Indian",
    min_rating=4.0,
    budget=BudgetTier.MEDIUM,
)
```

## Tests

```bash
pytest tests/ -v -m "not integration"
```

Integration tests (require ingested DB):

```bash
pytest tests/ -m integration -v
```

## Documentation

See `docs/` for context, architecture, implementation plan, and edge cases.
