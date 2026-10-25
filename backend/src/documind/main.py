"""Application factory.

Run locally with ``uvicorn documind.main:create_app --factory`` (binds to 127.0.0.1 by default).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from documind import __version__
from documind.api import health
from documind.config import Settings
from documind.db import create_db_engine, create_session_factory, init_schema
from documind.errors import register_error_handlers
from documind.logging_setup import configure_logging
from documind.middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        settings.ensure_directories()
        init_schema(engine)
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
    app.state.session_factory = create_session_factory(engine)

    register_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router, prefix="/api")
    return app
