"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from documind.models import DocumentStatus

CheckResult = Literal["ok", "error"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessChecks(BaseModel):
    database: CheckResult
    storage: CheckResult


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


class ClientConfig(BaseModel):
    """Settings the browser needs. Never contains credentials or server paths."""

    llm_enabled: bool
    allowed_file_types: list[str]
    max_upload_bytes: int
    max_pdf_pages: int
    max_query_chars: int
    max_question_chars: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str = Field(validation_alias="display_name")
    file_type: str
    size_bytes: int
    status: DocumentStatus
    failure_code: str | None
    failure_message: str | None
    page_count: int | None
    empty_page_count: int | None
    chunk_count: int
    char_count: int
    created_at: datetime
    processed_at: datetime | None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordinal: int
    page: int | None
    line_start: int | None
    line_end: int | None
    text: str


class ChunkPage(BaseModel):
    document_id: str
    total: int
    offset: int
    limit: int
    items: list[ChunkOut]
