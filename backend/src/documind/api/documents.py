"""Document library: upload, list, inspect, download and delete."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from documind.api.deps import ProcessorDep, SessionDep, SettingsDep, StorageDep
from documind.errors import NotFoundError
from documind.ingestion.pipeline import accept_upload
from documind.models import Chunk, Document, DocumentStatus
from documind.schemas import ChunkOut, ChunkPage, DocumentOut, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_MEDIA_TYPES = {"pdf": "application/pdf", "txt": "text/plain"}


def _get_document(session: SessionDep, document_id: uuid.UUID) -> Document:
    document = session.get(Document, str(document_id))
    if document is None:
        raise NotFoundError("Document not found. It may have been deleted.")
    return document


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[DocumentOut])
def list_documents(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200, description="Filter by name")] = None,
    status: DocumentStatus | None = None,
) -> list[Document]:
    statement = select(Document).order_by(Document.created_at.desc(), Document.id)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        statement = statement.where(Document.display_name.ilike(pattern, escape="\\"))
    if status is not None:
        statement = statement.where(Document.status == status)
    return list(session.scalars(statement))


@router.post(
    "",
    status_code=202,
    response_model=DocumentOut,
    responses={
        409: {"model": ErrorResponse, "description": "The same file is already in the library"},
        413: {"model": ErrorResponse, "description": "The file is larger than the limit"},
        415: {"model": ErrorResponse, "description": "Not a supported PDF or UTF-8 text file"},
        422: {"model": ErrorResponse, "description": "Empty file or malformed request"},
    },
)
def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
    processor: ProcessorDep,
) -> Document:
    """Accept one file. Processing continues in the background; poll the document for status."""
    document = accept_upload(
        session=session,
        storage=storage,
        settings=settings,
        filename=file.filename,
        source=file.file,
    )
    background.add_task(processor.process, document.id)
    return document


@router.get("/{document_id}", response_model=DocumentOut, responses={404: {"model": ErrorResponse}})
def get_document(session: SessionDep, document_id: uuid.UUID) -> Document:
    return _get_document(session, document_id)


@router.get(
    "/{document_id}/chunks", response_model=ChunkPage, responses={404: {"model": ErrorResponse}}
)
def list_chunks(
    session: SessionDep,
    document_id: uuid.UUID,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ChunkPage:
    """The extracted text of a document, in order, as indexed chunks."""
    document = _get_document(session, document_id)
    total = session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.document_id == document.id)
    )
    chunks = session.scalars(
        select(Chunk)
        .where(Chunk.document_id == document.id)
        .order_by(Chunk.ordinal)
        .offset(offset)
        .limit(limit)
    )
    return ChunkPage(
        document_id=document.id,
        total=total or 0,
        offset=offset,
        limit=limit,
        items=[ChunkOut.model_validate(chunk) for chunk in chunks],
    )


@router.get(
    "/{document_id}/file",
    response_class=FileResponse,
    responses={404: {"model": ErrorResponse}},
)
def download_file(session: SessionDep, storage: StorageDep, document_id: uuid.UUID) -> FileResponse:
    """The original upload, always as a download (never rendered inline)."""
    document = _get_document(session, document_id)
    path = storage.path_for(document.stored_name)
    if not path.is_file():
        raise NotFoundError("The original file is missing from storage.")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES[document.file_type],
        filename=document.display_name,
        content_disposition_type="attachment",
    )


@router.delete("/{document_id}", status_code=204, responses={404: {"model": ErrorResponse}})
def delete_document(session: SessionDep, storage: StorageDep, document_id: uuid.UUID) -> Response:
    """Delete the document, its chunks and search-index entries, and the stored file."""
    document = _get_document(session, document_id)
    stored_name = document.stored_name
    session.delete(document)
    session.commit()  # chunks and index rows go with it (foreign-key cascade + triggers)
    # The row is removed first, so a file that cannot be deleted now becomes an orphan for the
    # start-up sweep, never a document pointing at a missing file.
    storage.delete(stored_name)
    logger.info("Deleted document %s", document_id)
    return Response(status_code=204)
