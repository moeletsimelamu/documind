"""A client for OpenAI-compatible chat-completions APIs (OpenAI, Ollama, LM Studio, vLLM, ...).

Logs record status codes and timings only: never the API key, the question or document text.
"""

import logging
import time
from typing import Any

import httpx2

from documind.answering.provider import (
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderRejectedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

_UNREADABLE = "The AI provider sent a reply DocuMind could not read."


class OpenAICompatibleModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: float,
        max_output_tokens: int,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx2.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
        )

    @property
    def model(self) -> str:
        return self._model

    def complete(self, system: str, user: str) -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": self._max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        started = time.perf_counter()
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx2.TimeoutException as exc:
            logger.warning("AI provider timed out after %.1f s", time.perf_counter() - started)
            raise ProviderTimeoutError("The AI provider did not respond in time.") from exc
        except httpx2.RequestError as exc:
            logger.warning("AI provider unreachable: %s", type(exc).__name__)
            raise ProviderUnavailableError("The AI provider could not be reached.") from exc

        status = response.status_code
        logger.info("AI provider answered %d in %.1f s", status, time.perf_counter() - started)
        if status in (401, 403):
            raise ProviderAuthError("The AI provider rejected the configured credentials.")
        if status == 404:
            raise ProviderRejectedError(
                "The AI provider does not recognise the configured model or address."
            )
        if status == 429:
            raise ProviderRejectedError(
                "The AI provider is rate-limiting requests. Try again later."
            )
        if status >= 500:
            raise ProviderUnavailableError("The AI provider had an internal error.")
        if status >= 400:
            raise ProviderRejectedError(f"The AI provider refused the request ({status}).")

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderBadResponseError(_UNREADABLE) from exc
        if not isinstance(content, str):
            raise ProviderBadResponseError(_UNREADABLE)
        return content
