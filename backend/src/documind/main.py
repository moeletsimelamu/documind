"""Application factory.

Run locally with ``uvicorn documind.main:create_app --factory`` (binds to 127.0.0.1 by default).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from documind import __version__
from documind.answering.openai_compatible import OpenAICompatibleModel
from documind.answering.provider import LanguageModel
from documind.api import ask, documents, health, search
from documind.config import Settings
from documind.db import create_db_engine, create_session_factory, init_schema
from documind.errors import register_error_handlers
from documind.ingestion.pipeline import DocumentProcessor, too_large_message
from documind.logging_setup import configure_logging
from documind.middleware import (
    HostAndOriginGuardMiddleware,
    RequestContextMiddleware,
    UploadSizeLimitMiddleware,
)
from documind.spa import register_spa
from documind.storage import LocalFileStorage

logger = logging.getLogger(__name__)


def build_language_model(settings: Settings) -> LanguageModel | None:
    """The configured model client, or None when AI answers are off."""
    if settings.llm_model_name is None:
        return None
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return OpenAICompatibleModel(
        base_url=settings.llm_base_url,
        model=settings.llm_model_name,
        api_key=api_key or None,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_path)
    session_factory = create_session_factory(engine)
    storage = LocalFileStorage(settings.uploads_dir)
    processor = DocumentProcessor(session_factory, storage, settings)
    language_model = build_language_model(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        settings.ensure_directories()
        init_schema(engine)
        processor.recover_after_restart()
        logger.info(
            "DocuMind %s started: data directory %s, AI answers %s",
            __version__,
            settings.data_dir.resolve(),
            "on" if settings.llm_enabled else "off",
        )
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="DocuMind API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.api_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.api_docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.storage = storage
    app.state.processor = processor
    app.state.language_model = language_model

    register_error_handlers(app)
    # RequestContextMiddleware is added last so it is outermost: request IDs and security
    # headers also apply to responses produced by the size limiter.
    app.add_middleware(
        UploadSizeLimitMiddleware,
        path="/api/documents",
        max_file_bytes=settings.max_upload_bytes,
        message=too_large_message(settings),
    )
    # Before reading any body: refuse unknown hosts and cross-site writes.
    app.add_middleware(HostAndOriginGuardMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(ask.router, prefix="/api")
    if settings.static_dir is not None:
        register_spa(app, settings.static_dir)  # last: it matches every remaining GET path
    return app
