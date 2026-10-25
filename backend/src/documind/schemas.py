"""Pydantic models for API requests and responses."""

from typing import Literal

from pydantic import BaseModel

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
