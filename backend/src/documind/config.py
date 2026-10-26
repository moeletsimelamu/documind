"""Application settings, read from environment variables prefixed with ``DOCUMIND_``."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_FILE_TYPES: tuple[str, ...] = ("pdf", "txt")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    data_dir: Path = Path("data")
    # Built frontend to serve from this process (production / container). Unset in development,
    # where the Angular dev server is used instead.
    static_dir: Path | None = None

    # Resource limits
    max_upload_mb: int = Field(default=20, ge=1, le=200)
    max_pdf_pages: int = Field(default=500, ge=1, le=5000)
    max_extracted_chars: int = Field(default=2_000_000, ge=1_000)
    max_concurrent_processing: int = Field(default=2, ge=1, le=8)
    extraction_timeout_seconds: float = Field(default=120.0, gt=0, le=3600)
    max_query_chars: int = Field(default=300, ge=10, le=2000)
    max_question_chars: int = Field(default=1000, ge=10, le=4000)

    # Optional AI answers through an OpenAI-compatible chat API. Off unless a model is set.
    llm_model: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    llm_max_output_tokens: int = Field(default=700, ge=50, le=4000)

    # Operations
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_docs: bool = True

    @property
    def llm_enabled(self) -> bool:
        return self.llm_model_name is not None

    @property
    def llm_model_name(self) -> str | None:
        """The configured model, or None when AI answers are off."""
        name = (self.llm_model or "").strip()
        return name or None

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def database_path(self) -> Path:
        return self.data_dir / "documind.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    def ensure_directories(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
