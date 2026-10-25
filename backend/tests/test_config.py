from pathlib import Path

import pytest
from pydantic import ValidationError

from documind.config import Settings


def test_reads_prefixed_environment_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DOCUMIND_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DOCUMIND_MAX_UPLOAD_MB", "5")
    monkeypatch.setenv("DOCUMIND_LLM_MODEL", "local-model")

    settings = Settings(_env_file=None)

    assert settings.data_dir == tmp_path
    assert settings.max_upload_bytes == 5 * 1024 * 1024
    assert settings.llm_enabled is True
    assert settings.database_path == tmp_path / "documind.db"


def test_ai_answers_are_off_without_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMIND_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("DOCUMIND_LLM_MODEL", "   ")

    assert Settings(_env_file=None).llm_enabled is False


def test_api_key_is_hidden_in_representations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMIND_LLM_API_KEY", "sk-test-hidden")

    settings = Settings(_env_file=None)

    assert "sk-test-hidden" not in repr(settings)
    assert "sk-test-hidden" not in settings.model_dump_json()
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "sk-test-hidden"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DOCUMIND_MAX_UPLOAD_MB", "0"),
        ("DOCUMIND_MAX_UPLOAD_MB", "lots"),
        ("DOCUMIND_LLM_TIMEOUT_SECONDS", "-1"),
        ("DOCUMIND_LOG_LEVEL", "VERBOSE"),
    ],
)
def test_invalid_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
