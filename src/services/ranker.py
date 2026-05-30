"""Orchestrate Groq ranking with retry and fallback (Phase 4)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.data.models import Restaurant, UserPreferences
from src.services.llm import LLMProvider, LLMProviderError, get_default_provider
from src.services.parser import (
    LLMParseError,
    build_fallback_recommendations,
    merge_ranked_response,
    parse_llm_response,
)
from src.services.prompt import build_ranking_messages, build_repair_messages

logger = logging.getLogger(__name__)


@dataclass
class LLMRankingResult:
    """Result of LLM ranking pass."""

    preferences: UserPreferences
    recommendations: list[dict] = field(default_factory=list)
    summary: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


class LLMRankingService:
    """
    Rank filtered candidates via Groq with parse retry and rating fallback.
    """

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider

    def _get_provider(self) -> LLMProvider:
        if self.provider is not None:
            return self.provider
        return get_default_provider()

    def rank(
        self,
        preferences: UserPreferences,
        candidates: list[Restaurant],
    ) -> LLMRankingResult:
        if not candidates:
            return LLMRankingResult(
                preferences=preferences,
                recommendations=[],
                summary=None,
                meta={"llm_fallback": False, "candidates_count": 0},
            )

        provider = self._get_provider()
        messages = build_ranking_messages(preferences, candidates)
        meta: dict[str, Any] = {
            "llm_provider": provider.provider_name,
            "llm_model": provider.model_name,
            "candidates_count": len(candidates),
            "llm_fallback": False,
        }

        raw_content: Optional[str] = None
        total_latency = 0.0

        for attempt in range(2):
            try:
                completion = provider.complete(messages)
                raw_content = completion.content
                total_latency += completion.latency_ms
                meta["llm_latency_ms"] = total_latency

                parsed = parse_llm_response(raw_content)
                recommendations, summary = merge_ranked_response(
                    parsed, candidates, preferences
                )
                if recommendations:
                    meta["llm_retries"] = attempt
                    return LLMRankingResult(
                        preferences=preferences,
                        recommendations=_cap_top_k(recommendations, preferences.top_k),
                        summary=summary,
                        meta=meta,
                    )
                logger.warning("Parsed LLM response had no valid restaurant ids")
                if attempt == 0 and raw_content:
                    messages = build_repair_messages(
                        preferences, candidates, raw_content
                    )
                    continue

            except LLMProviderError as exc:
                logger.warning("LLM provider error (attempt %d): %s", attempt + 1, exc)
                if not exc.retryable or attempt == 1:
                    break
                time.sleep(1.0)
                continue

            except LLMParseError as exc:
                logger.warning("LLM parse error (attempt %d): %s", attempt + 1, exc)
                if attempt == 0 and raw_content:
                    messages = build_repair_messages(
                        preferences, candidates, raw_content
                    )
                    continue
                break

        # Fallback path
        recommendations, summary = build_fallback_recommendations(
            preferences, candidates
        )
        meta["llm_fallback"] = True
        meta["llm_retries"] = 2
        return LLMRankingResult(
            preferences=preferences,
            recommendations=recommendations,
            summary=summary,
            meta=meta,
        )


def _cap_top_k(recommendations: list[dict], top_k: int) -> list[dict]:
    capped = recommendations[:top_k]
    for i, rec in enumerate(capped, start=1):
        rec["rank"] = i
    return capped
