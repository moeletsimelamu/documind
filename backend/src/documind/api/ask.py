"""Ask a question about the documents."""

from http import HTTPStatus

from fastapi import APIRouter

from documind import retrieval
from documind.answering.service import answer_question
from documind.api.deps import SessionDep, SettingsDep
from documind.api.search import hit_from
from documind.errors import AppError
from documind.schemas import AskRequest, AskResponse, ErrorResponse

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse, responses={422: {"model": ErrorResponse}})
def ask(request: AskRequest, session: SessionDep, settings: SettingsDep) -> AskResponse:
    question = request.question.strip()
    if len(question) > settings.max_question_chars:
        raise AppError(
            f"Questions can be at most {settings.max_question_chars} characters.",
            code="question_too_long",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    try:
        answer = answer_question(
            session,
            question,
            document_ids=[str(i) for i in request.document_ids] if request.document_ids else None,
        )
    except retrieval.EmptyQueryError as exc:
        raise AppError(
            "Type a question with at least one word.",
            code="empty_query",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        ) from exc
    return AskResponse(
        mode=answer.mode.value,
        question=question,
        searched_for=answer.query.searched_for,
        passages=[hit_from(p) for p in answer.passages],
    )
