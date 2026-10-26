"""Document library: upload, list, inspect, download and delete."""

import logging
import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from documind import retrieval
from documind.api.deps import ProcessorDep, SessionDep, SettingsDep, StorageDep
from documind.errors import AppError, NotFoundError
from documind.ingestion.pipeline import accept_upload
from documind.models import Chunk, Document, DocumentStatus
from documind.schemas import (
    ChunkOut,
    ChunkPage,
    DocumentMatchesOut,
    DocumentMatchOut,
    DocumentOut,
    ErrorResponse,
)

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
    background.add_task(processor.process_in_background, document.id)
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
    page: Annotated[
        int | None,
        Query(
            ge=1,
            description="Start at this PDF page instead of at offset (or the next page "
            "with text, if it has none)",
        ),
    ] = None,
) -> ChunkPage:
    """The extracted text of a document, in order, as indexed chunks."""
    document = _get_document(session, document_id)
    total = (
        session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == document.id)
        )
        or 0
    )
    if page is not None:
        # Pages only increase with the ordinal, so the passages before page N are those with a
        # lower page number. Past the last page, the last passage is returned.
        before = (
            session.scalar(
                select(func.count())
                .select_from(Chunk)
                .where(Chunk.document_id == document.id, Chunk.page < page)
            )
            or 0
        )
        offset = min(before, max(total - 1, 0))
    chunks = session.scalars(
        select(Chunk)
        .where(Chunk.document_id == document.id)
        .order_by(Chunk.ordinal)
        .offset(offset)
        .limit(limit)
    )
    return ChunkPage(
        document_id=document.id,
        total=total,
        offset=offset,
        limit=limit,
        items=[ChunkOut.model_validate(chunk) for chunk in chunks],
    )


MAX_DOCUMENT_MATCHES = 500


@router.get(
    "/{document_id}/matches",
    response_model=DocumentMatchesOut,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def find_in_document(
    session: SessionDep,
    settings: SettingsDep,
    document_id: uuid.UUID,
    q: Annotated[str, Query(description="Words to find; use quotes for a phrase")],
) -> DocumentMatchesOut:
    """Every passage of the document containing the words, in reading order, for "find next"."""
    document = _get_document(session, document_id)
    if len(q) > settings.max_query_chars:
        raise AppError(
            f"Search queries can be at most {settings.max_query_chars} characters.",
            code="query_too_long",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    try:
        result = retrieval.find_in_document(session, document.id, q, limit=MAX_DOCUMENT_MATCHES)
    except retrieval.EmptyQueryError as exc:
        raise AppError(
            str(exc), code="empty_query", status_code=HTTPStatus.UNPROCESSABLE_ENTITY
        ) from exc
    return DocumentMatchesOut(
        document_id=document.id,
        query=q,
        searched_for=result.query.searched_for,
        total=result.total,
        truncated=result.total > len(result.matches),
        all_words=result.all_words,
        matches=[
            DocumentMatchOut(
                chunk_id=m.chunk_id,
                ordinal=m.ordinal,
                page=m.page,
                line_start=m.line_start,
                line_end=m.line_end,
                highlights=m.highlights,
            )
            for m in result.matches
        ],
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
