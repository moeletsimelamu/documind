import json
import logging
from collections.abc import Callable

import httpx2
import pytest

from documind.answering.openai_compatible import OpenAICompatibleModel
from documind.answering.provider import (
    ProviderAuthError,
    ProviderBadResponseError,
    ProviderError,
    ProviderRejectedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

Handler = Callable[[httpx2.Request], httpx2.Response]


def client(handler: Handler, api_key: str | None = "sk-test-secret") -> OpenAICompatibleModel:
    return OpenAICompatibleModel(
        base_url="http://llm.test/v1/",
        model="test-model",
        api_key=api_key,
        timeout_seconds=5,
        max_output_tokens=300,
        transport=httpx2.MockTransport(handler),
    )


def ok(content: object) -> Handler:
    return lambda request: httpx2.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


def test_sends_an_openai_style_chat_request() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return ok("reply")(request)

    assert client(handler).complete("system rules", "user text") == "reply"

    request = seen[0]
    assert str(request.url) == "http://llm.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer sk-test-secret"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["messages"] == [
        {"role": "system", "content": "system rules"},
        {"role": "user", "content": "user text"},
    ]
    assert body["temperature"] == 0
    assert body["max_tokens"] == 300
    assert body["response_format"] == {"type": "json_object"}


def test_no_authorization_header_without_a_key() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return ok("reply")(request)

    client(handler, api_key=None).complete("s", "u")

    assert "Authorization" not in seen[0].headers


def raises(exception: Exception) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise exception

    return handler


def status(code: int, body: object = None) -> Handler:
    return lambda request: httpx2.Response(code, json=body or {"error": {"message": "x"}})


@pytest.mark.parametrize(
    ("handler", "error_type", "message"),
    [
        (raises(httpx2.ReadTimeout("slow")), ProviderTimeoutError, "did not respond in time"),
        (raises(httpx2.ConnectError("refused")), ProviderUnavailableError, "could not be reached"),
        (status(401), ProviderAuthError, "rejected the configured credentials"),
        (status(403), ProviderAuthError, "rejected the configured credentials"),
        (status(404), ProviderRejectedError, "does not recognise the configured model"),
        (status(429), ProviderRejectedError, "rate-limiting"),
        (status(400), ProviderRejectedError, "refused the request (400)"),
        (status(503), ProviderUnavailableError, "internal error"),
        (
            lambda r: httpx2.Response(200, text="<html>not json</html>"),
            ProviderBadResponseError,
            "could not read",
        ),
        (status(200, {"choices": []}), ProviderBadResponseError, "could not read"),
        (ok(None), ProviderBadResponseError, "could not read"),
    ],
    ids=[
        "timeout",
        "unreachable",
        "401",
        "403",
        "404",
        "429",
        "400",
        "503",
        "html",
        "no-choices",
        "null",
    ],
)
def test_failures_become_provider_errors_with_safe_messages(
    handler: Handler, error_type: type[ProviderError], message: str
) -> None:
    with pytest.raises(error_type) as caught:
        client(handler).complete("s", "u")

    assert message in caught.value.message


def test_logs_contain_neither_the_key_nor_the_conversation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        client(ok("the answer text")).complete("system secret rules", "confidential question")
        with pytest.raises(ProviderAuthError):
            client(status(401)).complete("s", "confidential question")

    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "AI provider answered 200" in logged
    for secret in (
        "sk-test-secret",
        "confidential question",
        "system secret rules",
        "the answer text",
    ):
        assert secret not in logged
