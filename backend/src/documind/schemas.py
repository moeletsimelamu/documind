"""Pydantic models for API requests and responses."""

import uuid
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
    # The model name only; the provider address and credentials are never sent to the browser.
    llm_model: str | None
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


class SearchHit(BaseModel):
    chunk_id: int
    document_id: str
    document_name: str
    file_type: str
    ordinal: int
    page: int | None
    line_start: int | None
    line_end: int | None
    excerpt: str
    # [start, end) character offsets into ``excerpt`` of the words that matched the query.
    highlights: list[tuple[int, int]]
    excerpt_starts_mid_text: bool
    excerpt_ends_mid_text: bool


class SearchResponse(BaseModel):
    query: str
    # The words and phrases actually searched for, after common words were dropped.
    searched_for: list[str]
    total_passages: int
    total_documents: int
    results: list[SearchHit]


class ChunkDetail(BaseModel):
    id: int
    document_id: str
    document_name: str
    ordinal: int
    page: int | None
    line_start: int | None
    line_end: int | None
    text: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)


class GenerationError(BaseModel):
    code: str
    message: str


class AskResponse(BaseModel):
    mode: Literal["generated", "retrieval_only", "insufficient_evidence"]
    question: str
    searched_for: list[str]
    # Generated text with [S1]-style citations; always null unless mode is "generated".
    answer: str | None = None
    # Ids of the passages the answer cites. Passage n (1-based) in ``passages`` is "S<n>".
    cited: list[str] = Field(default_factory=list)
    # The retrieved passages the response is based on, best first.
    passages: list[SearchHit]
    # Set when AI answers are on but the provider failed; the passages are still returned.
    generation_error: GenerationError | None = None
    # The model that produced the answer, when one was asked.
    model: str | None = None
