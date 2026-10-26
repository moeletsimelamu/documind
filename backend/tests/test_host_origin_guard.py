from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from documind.config import Settings
from documind.main import create_app
from documind.middleware import _host_name
from tests.conftest import make_settings

NOTE = {"file": ("note.txt", b"A short note about the warehouse audit.")}


def documents(client: TestClient) -> list[str]:
    return [d["name"] for d in client.get("/api/documents").json()]


# --- DNS rebinding: only configured host names are served ----------------------------------


@pytest.mark.parametrize("host", ["attacker.example", "attacker.example:8000", "192.168.1.20"])
def test_requests_for_other_host_names_are_refused(client: TestClient, host: str) -> None:
    response = client.get("/api/documents", headers={"Host": host})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_host"
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("host", ["localhost:8000", "LOCALHOST", "127.0.0.1:8000", "testserver"])
def test_configured_host_names_are_served_with_or_without_a_port(
    client: TestClient, host: str
) -> None:
    assert client.get("/api/health", headers={"Host": host}).status_code == 200


def test_ipv6_loopback_is_served(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data", allowed_hosts=["[::1]"])
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health", headers={"Host": "[::1]:8000"}).status_code == 200


def test_wildcard_turns_the_host_check_off(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data", allowed_hosts=["*"])
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health", headers={"Host": "anything.example"}).status_code == 200


def test_allowed_hosts_can_be_configured_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCUMIND_ALLOWED_HOSTS", '["documind.example.org", "localhost"]')

    assert Settings(_env_file=None).allowed_hosts == ["documind.example.org", "localhost"]


def test_default_hosts_are_loopback_only() -> None:
    assert Settings(_env_file=None).allowed_hosts == ["localhost", "127.0.0.1", "[::1]"]


@pytest.mark.parametrize(
    ("header", "name"),
    [("localhost:8000", "localhost"), ("[::1]:8000", "[::1]"), ("Example.ORG", "example.org")],
)
def test_host_name_parsing(header: str, name: str) -> None:
    assert _host_name(header) == name


# --- Cross-site requests: other websites cannot change anything -----------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver:9999"},  # same host, different port: another origin
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},  # e.g. another app on localhost
    ],
)
def test_cross_site_uploads_are_refused(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post("/api/documents", files=NOTE, headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "cross_origin_request"
    assert documents(client) == []


def test_cross_site_delete_is_refused(client: TestClient) -> None:
    document = client.post("/api/documents", files=NOTE).json()

    response = client.delete(
        f"/api/documents/{document['id']}", headers={"Origin": "https://evil.example"}
    )

    assert response.status_code == 403
    assert documents(client) == ["note.txt"]


@pytest.mark.parametrize(
    "headers",
    [
        {},  # curl, scripts: not a browser cross-site request
        {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},  # this app's own pages
        {"Sec-Fetch-Site": "none"},  # user-initiated
    ],
)
def test_same_origin_and_non_browser_writes_are_allowed(
    client: TestClient, headers: dict[str, str]
) -> None:
    assert client.post("/api/documents", files=NOTE, headers=headers).status_code == 202


def test_reads_are_not_blocked_by_origin(client: TestClient) -> None:
    # Cross-site pages cannot read responses anyway: the API sends no CORS headers.
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings(tmp_path / "data"))) as test_client:
        yield test_client
