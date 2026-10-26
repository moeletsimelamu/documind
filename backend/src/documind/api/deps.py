"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from documind.answering.provider import LanguageModel
from documind.config import Settings
from documind.ingestion.pipeline import DocumentProcessor
from documind.storage import LocalFileStorage


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    """A session per request. Endpoints commit explicitly; closing rolls back anything else."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_storage(request: Request) -> LocalFileStorage:
    storage: LocalFileStorage = request.app.state.storage
    return storage


def get_processor(request: Request) -> DocumentProcessor:
    processor: DocumentProcessor = request.app.state.processor
    return processor


def get_language_model(request: Request) -> LanguageModel | None:
    model: LanguageModel | None = request.app.state.language_model
    return model


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[LocalFileStorage, Depends(get_storage)]
ProcessorDep = Annotated[DocumentProcessor, Depends(get_processor)]
LanguageModelDep = Annotated[LanguageModel | None, Depends(get_language_model)]
