"""Keyword search over indexed passages, and single-passage lookup for citations."""

import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Query

from documind import retrieval
from documind.api.deps import SessionDep, SettingsDep
from documind.errors import AppError, NotFoundError
from documind.models import Chunk
from documind.schemas import ChunkDetail, ErrorResponse, SearchHit, SearchResponse

router = APIRouter(tags=["search"])


def hit_from(passage: retrieval.Passage) -> SearchHit:
    excerpt = passage.excerpt()
    return SearchHit(
        chunk_id=passage.chunk_id,
        document_id=passage.document_id,
        document_name=passage.document_name,
        file_type=passage.file_type,
        ordinal=passage.ordinal,
        page=passage.page,
        line_start=passage.line_start,
        line_end=passage.line_end,
        excerpt=excerpt.text,
        highlights=excerpt.highlights,
        excerpt_starts_mid_text=excerpt.starts_mid_text,
        excerpt_ends_mid_text=excerpt.ends_mid_text,
    )


@router.get("/search", response_model=SearchResponse, responses={422: {"model": ErrorResponse}})
def search_passages(
    session: SessionDep,
    settings: SettingsDep,
    q: Annotated[str, Query(description="Words to search for; use quotes for a phrase")],
    document_id: Annotated[
        list[uuid.UUID] | None, Query(max_length=50, description="Limit to these documents")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResponse:
    if len(q) > settings.max_query_chars:
        raise AppError(
            f"Search queries can be at most {settings.max_query_chars} characters.",
            code="query_too_long",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    try:
        result = retrieval.search(
            session,
            q,
            limit=limit,
            document_ids=[str(i) for i in document_id] if document_id else None,
        )
    except retrieval.EmptyQueryError as exc:
        raise AppError(
            str(exc), code="empty_query", status_code=HTTPStatus.UNPROCESSABLE_ENTITY
        ) from exc
    return SearchResponse(
        query=q,
        searched_for=result.query.searched_for,
        total_passages=result.total_passages,
        total_documents=result.total_documents,
        results=[hit_from(p) for p in result.passages],
    )


@router.get(
    "/chunks/{chunk_id}", response_model=ChunkDetail, responses={404: {"model": ErrorResponse}}
)
def get_chunk(session: SessionDep, chunk_id: int) -> ChunkDetail:
    """One indexed passage with its source location; used to open a search result or citation."""
    chunk = session.get(Chunk, chunk_id)
    if chunk is None:
        raise NotFoundError("This passage no longer exists. Its document may have been deleted.")
    return ChunkDetail(
        id=chunk.id,
        document_id=chunk.document_id,
        document_name=chunk.document.display_name,
        ordinal=chunk.ordinal,
        page=chunk.page,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        text=chunk.text,
    )
