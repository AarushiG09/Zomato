"""FastAPI Server to serve React SPA and handle recommendations (Phase 6 React)."""

import sys
from pathlib import Path
from typing import Any

# Add project root to sys.path explicitly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from src.config import DATABASE_PATH
from src.data.models import BudgetTier
from src.data.repository import RestaurantRepository
from src.services.exceptions import PreferenceValidationError
from src.services.llm import MockLLMProvider
from src.services.ranker import LLMRankingService
from src.services.recommender import RecommendationService

app = FastAPI(title="Zomato AI Recommendation System")

# Enable CORS for frontend API calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReactRecommendationRequest(BaseModel):
    """Extended request schema supporting mock toggles."""
    location: str
    budget: BudgetTier
    cuisine: str = ""
    min_rating: float = 3.5
    additional: list[str] = []
    top_k: int = 5
    use_mock: bool = False


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    """Serve the single-page React app."""
    index_path = Path(__file__).resolve().parent / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path)


@app.get("/api/v1/cities")
def get_cities():
    """List unique localities for the search dropdown."""
    try:
        repo = RestaurantRepository(DATABASE_PATH)
        return repo.list_cities()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/api/v1/recommendations")
def get_recommendations(req: ReactRecommendationRequest):
    """Retrieve filtered and AI-ranked dining recommendations."""
    try:
        repo = RestaurantRepository(DATABASE_PATH)

        # 1. Setup ranking service (Mock vs Live)
        if req.use_mock:
            import json
            mock_json = json.dumps({
                "ranked": [
                    {
                        "restaurant_id": "r1",
                        "rank": 1,
                        "explanation": f"A stellar choice in {req.location} matching your {req.cuisine} preference perfectly."
                    }
                ],
                "summary": f"Based on your preference for {req.cuisine} and your location in {req.location}, I have evaluated the local venues. We prioritized authentic options and evening ambiance within your budget."
            })
            provider = MockLLMProvider(mock_json)
            ranking_service = LLMRankingService(provider=provider)
        else:
            ranking_service = LLMRankingService()

        # 2. Coordinate with RecommendationService
        service = RecommendationService(
            repository=repo,
            ranking_service=ranking_service
        )

        response = service.recommend({
            "location": req.location,
            "budget": req.budget.value.lower(),
            "cuisine": req.cuisine,
            "min_rating": req.min_rating,
            "top_k": req.top_k,
            "additional": req.additional,
        })
        return response

    except PreferenceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
