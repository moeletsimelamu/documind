import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from documind.config import Settings
from documind.main import create_app
from tests.conftest import make_settings


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_creates_data_directories(client: TestClient, settings: Settings) -> None:
    assert settings.uploads_dir.is_dir()
    assert settings.database_path.is_file()


def test_ready_when_database_and_storage_are_usable(client: TestClient) -> None:
    response = client.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "storage": "ok"}}


def test_not_ready_when_storage_is_missing(client: TestClient, settings: Settings) -> None:
    shutil.rmtree(settings.uploads_dir)
    settings.uploads_dir.write_text("not a directory")

    response = client.get("/api/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "storage": "error"},
    }


def test_config_reports_limits_and_ai_off_by_default(client: TestClient) -> None:
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "llm_enabled": False,
        "llm_model": None,
        "allowed_file_types": ["pdf", "txt"],
        "max_upload_bytes": 20 * 1024 * 1024,
        "max_pdf_pages": 500,
        "max_query_chars": 300,
        "max_question_chars": 1000,
    }


def test_config_never_exposes_credentials_or_endpoint(tmp_path: Path) -> None:
    settings = make_settings(
        tmp_path,
        llm_model="test-model",
        llm_base_url="http://llm.internal.example/v1",
        llm_api_key=SecretStr("sk-test-very-secret"),
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/config")

    assert response.json()["llm_enabled"] is True
    assert response.json()["llm_model"] == "test-model"
    assert "sk-test-very-secret" not in response.text
    assert "llm.internal.example" not in response.text
