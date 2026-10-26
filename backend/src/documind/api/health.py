"""Liveness, readiness and public client configuration."""

import logging
import tempfile

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from documind.api.deps import SessionDep, SettingsDep
from documind.config import ALLOWED_FILE_TYPES
from documind.models import schema_meta
from documind.schemas import (
    CheckResult,
    ClientConfig,
    HealthResponse,
    ReadinessChecks,
    ReadinessResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """The process is up and serving requests."""
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready(session: SessionDep, settings: SettingsDep) -> JSONResponse:
    """The database (including the search index) and file storage are usable."""
    database: CheckResult = "ok"
    try:
        has_index = session.execute(
            text("SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'chunks_fts'")
        ).scalar_one()
        version = session.execute(
            select(schema_meta.c.value).where(schema_meta.c.key == "schema_version")
        ).scalar_one_or_none()
        if has_index != 1 or version is None:
            database = "error"
    except SQLAlchemyError:
        logger.exception("Readiness check: database unavailable")
        database = "error"

    storage: CheckResult = "ok"
    try:
        with tempfile.NamedTemporaryFile(dir=settings.uploads_dir, prefix=".ready-"):
            pass
    except OSError:
        logger.exception("Readiness check: upload storage is not writable")
        storage = "error"

    checks = ReadinessChecks(database=database, storage=storage)
    is_ready = database == "ok" and storage == "ok"
    body = ReadinessResponse(status="ready" if is_ready else "not_ready", checks=checks)
    return JSONResponse(status_code=200 if is_ready else 503, content=body.model_dump())


@router.get("/config", response_model=ClientConfig)
def client_config(settings: SettingsDep) -> ClientConfig:
    return ClientConfig(
        llm_enabled=settings.llm_enabled,
        llm_model=settings.llm_model_name,
        allowed_file_types=list(ALLOWED_FILE_TYPES),
        max_upload_bytes=settings.max_upload_bytes,
        max_pdf_pages=settings.max_pdf_pages,
        max_query_chars=settings.max_query_chars,
        max_question_chars=settings.max_question_chars,
    )
