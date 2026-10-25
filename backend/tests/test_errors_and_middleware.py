import logging
import time
from collections.abc import Iterator

import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from documind.errors import AppError, NotFoundError


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """The app plus test-only routes that raise each kind of error."""

    def raise_unexpected() -> None:
        raise RuntimeError("database password is hunter2")

    def raise_app_error() -> None:
        raise AppError("File type not supported.", code="unsupported_file_type", status_code=415)

    def raise_not_found() -> None:
        raise NotFoundError("Document not found.")

    def needs_int(limit: int) -> dict[str, int]:
        return {"limit": limit}

    app.add_api_route("/api/test/unexpected", raise_unexpected)
    app.add_api_route("/api/test/app-error", raise_app_error)
    app.add_api_route("/api/test/not-found", raise_not_found)
    app.add_api_route("/api/test/validate", needs_int)
    with TestClient(app) as test_client:
        yield test_client


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/nothing-here")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_wrong_method_uses_error_envelope(client: TestClient) -> None:
    response = client.delete("/api/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"


def test_app_error_keeps_its_status_code_and_message(client: TestClient) -> None:
    response = client.get("/api/test/app-error")

    assert response.status_code == 415
    error = response.json()["error"]
    assert error["code"] == "unsupported_file_type"
    assert error["message"] == "File type not supported."


def test_not_found_error(client: TestClient) -> None:
    response = client.get("/api/test/not-found")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Document not found."


def test_validation_error_does_not_echo_input(client: TestClient) -> None:
    response = client.get("/api/test/validate", params={"limit": "<script>alert(1)</script>"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"][0]["location"] == ["query", "limit"]
    assert "<script>" not in response.text


def test_unexpected_error_is_generic_for_client_and_logged_on_server(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="documind.errors"):
        response = client.get("/api/test/unexpected")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "hunter2" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    logged = [r for r in caplog.records if r.name == "documind.errors"]
    assert len(logged) == 1
    assert logged[0].exc_info is not None


def test_request_id_is_generated(client: TestClient) -> None:
    first = client.get("/api/health").headers["X-Request-ID"]
    second = client.get("/api/health").headers["X-Request-ID"]

    assert len(first) == 32
    assert first != second


def test_safe_incoming_request_id_is_kept(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"


def test_unsafe_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "bad id\twith spaces"})

    assert response.headers["X-Request-ID"] != "bad id\twith spaces"
    assert len(response.headers["X-Request-ID"]) == 32


def test_api_responses_have_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["Cache-Control"] == "no-store"


def test_access_log_omits_query_string(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="documind.access"):
        client.get("/api/health", params={"q": "confidential merger terms"})

    messages = [r.getMessage() for r in caplog.records if r.name == "documind.access"]
    assert messages == [messages[0]]
    assert messages[0].startswith("GET /api/health -> 200")
    assert "confidential" not in messages[0]


def test_access_log_time_excludes_background_work(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    def slow_background_job() -> None:
        time.sleep(1.5)

    def endpoint(background: BackgroundTasks) -> dict[str, str]:
        background.add_task(slow_background_job)
        return {"status": "accepted"}

    app.add_api_route("/api/test/background", endpoint)
    with TestClient(app) as client, caplog.at_level(logging.INFO, logger="documind.access"):
        client.get("/api/test/background")

    (record,) = [r for r in caplog.records if r.name == "documind.access"]
    # The message ends "(<elapsed> ms)".
    elapsed_ms = float(record.getMessage().rsplit("(", 1)[1].removesuffix(" ms)"))
    assert elapsed_ms < 1000
