"""Pydantic schemas for LLM JSON responses."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RankedItemSchema(BaseModel):
    restaurant_id: str
    rank: int = Field(ge=1)
    explanation: str = ""


class LLMResponseSchema(BaseModel):
    ranked: list[RankedItemSchema] = Field(default_factory=list)
    summary: Optional[str] = None
