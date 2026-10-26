from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from documind.main import create_app
from tests.conftest import make_settings

INDEX = "<!doctype html><title>DocuMind</title><dm-root></dm-root>"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    build = tmp_path / "build"
    (build / "media").mkdir(parents=True)
    (build / "index.html").write_text(INDEX, encoding="utf-8")
    (build / "main-35JR6M3P.js").write_text("console.log('app')", encoding="utf-8")
    (build / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (build / "media" / "font-QJ4BPJSY.woff2").write_bytes(b"wOF2")
    (tmp_path / "secret.txt").write_text("outside the build directory", encoding="utf-8")
    return build


@pytest.fixture
def client(tmp_path: Path, static_dir: Path) -> Iterator[TestClient]:
    settings = make_settings(tmp_path / "data", static_dir=static_dir)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/library", "/documents/abc?chunk=3", "/ask"])
def test_app_routes_get_the_app_shell(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"
    csp = response.headers["content-security-policy"]
    assert "script-src" not in csp  # falls back to default-src 'self': no inline scripts
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_hashed_bundles_are_cached_for_good(client: TestClient) -> None:
    response = client.get("/main-35JR6M3P.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "javascript" in response.headers["content-type"]
    assert client.get("/media/font-QJ4BPJSY.woff2").headers["cache-control"].endswith("immutable")


def test_unhashed_files_are_revalidated(client: TestClient) -> None:
    assert client.get("/favicon.svg").headers["cache-control"] == "no-cache"


def test_missing_assets_are_404_not_the_app_shell(client: TestClient) -> None:
    response = client.get("/chunk-MISSING1.js")

    assert response.status_code == 404
    assert INDEX not in response.text


def test_api_paths_never_fall_back_to_the_app(client: TestClient) -> None:
    response = client.get("/api/not-a-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path",
    ["/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/media/..%2f..%2fsecret.txt"],
)
def test_files_outside_the_build_directory_are_not_served(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert "outside the build directory" not in response.text


def test_uploaded_documents_are_not_reachable_through_the_app_route(client: TestClient) -> None:
    upload = client.post("/api/documents", files={"file": ("notes.txt", b"private notes")})
    stored_name = f"{upload.json()['id']}.txt"

    for path in (f"/{stored_name}", f"/uploads/{stored_name}", f"/data/uploads/{stored_name}"):
        assert "private notes" not in client.get(path).text


def test_without_a_build_directory_nothing_is_served_at_the_root(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path / "data"))) as client:
        assert client.get("/").status_code == 404


def test_a_build_directory_without_index_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    with pytest.raises(RuntimeError, match=r"no index\.html"):
        create_app(make_settings(tmp_path / "data", static_dir=tmp_path / "empty"))
