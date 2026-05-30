"""LLM provider abstraction — Groq implementation (Phase 4)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from src.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when the LLM provider fails after retries."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class LLMCompletionResult:
    content: str
    provider: str
    model: str
    latency_ms: float


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for chat-completion providers."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMCompletionResult: ...


class GroqProvider:
    """Groq chat completions via the official groq SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = LLM_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or GROQ_API_KEY
        self._model = model or GROQ_MODEL
        self._base_url = base_url or GROQ_BASE_URL
        self._timeout = timeout
        if not self._api_key:
            raise LLMProviderError(
                "GROQ_API_KEY is not set. Add it to your .env file.",
                retryable=False,
            )

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMCompletionResult:
        try:
            from groq import Groq
        except ImportError as exc:
            raise LLMProviderError(
                "groq package not installed. Run: pip install groq",
                retryable=False,
            ) from exc

        client = Groq(api_key=self._api_key, base_url=self._base_url)
        temp = temperature if temperature is not None else LLM_TEMPERATURE
        tokens = max_tokens if max_tokens is not None else LLM_MAX_TOKENS

        start = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
                timeout=self._timeout,
            )
        except Exception as exc:
            retryable = _is_retryable_groq_error(exc)
            logger.warning("Groq API error: %s", exc)
            raise LLMProviderError(str(exc), retryable=retryable) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        content = response.choices[0].message.content or ""
        logger.info(
            "Groq completion: model=%s latency_ms=%.0f chars=%d",
            self._model,
            latency_ms,
            len(content),
        )
        return LLMCompletionResult(
            content=content,
            provider=self.provider_name,
            model=self._model,
            latency_ms=latency_ms,
        )


class MockLLMProvider:
    """Returns a fixed JSON response for tests."""

    def __init__(
        self,
        response_content: str,
        *,
        provider_name: str = "mock",
        model_name: str = "mock-model",
    ) -> None:
        self._response_content = response_content
        self._provider_name = provider_name
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMCompletionResult:
        return LLMCompletionResult(
            content=self._response_content,
            provider=self._provider_name,
            model=self._model_name,
            latency_ms=1.0,
        )


def _is_retryable_groq_error(exc: Exception) -> bool:
    """Classify Groq/API errors for a single retry."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "rate" in message or "429" in message:
        return True
    if "timeout" in message or "timed out" in name:
        return True
    if "503" in message or "502" in message or "500" in message:
        return True
    if "connection" in message:
        return True
    return False


def get_default_provider() -> LLMProvider:
    """Factory: Groq in production, raises if key missing."""
    return GroqProvider()
