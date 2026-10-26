"""The interface between answering and a language-model provider, and its errors."""

from typing import Protocol


class ProviderError(Exception):
    """The provider could not produce a usable reply. ``message`` is safe to show to the user."""

    code = "provider_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"


class ProviderAuthError(ProviderError):
    code = "provider_auth"


class ProviderRejectedError(ProviderError):
    """The provider refused the request: unknown model, rate limit, or invalid request."""

    code = "provider_rejected"


class ProviderBadResponseError(ProviderError):
    code = "provider_bad_response"


class LanguageModel(Protocol):
    """Anything that turns a trusted system prompt and a user message into a text reply."""

    @property
    def model(self) -> str: ...

    def complete(self, system: str, user: str) -> str:
        """Return the reply text, or raise a ProviderError."""
        ...
