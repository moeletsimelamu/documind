"""Question answering over retrieved passages.

Without a configured language model the answer is the retrieved evidence itself
(``retrieval_only``); when nothing relevant is found the response says so
(``insufficient_evidence``). A search result is never presented as a generated answer.
"""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from documind import retrieval

ASK_TOP_K = 6


class AnswerMode(StrEnum):
    GENERATED = "generated"
    RETRIEVAL_ONLY = "retrieval_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class Answer:
    mode: AnswerMode
    query: retrieval.ParsedQuery
    passages: list[retrieval.Passage]


def answer_question(
    session: Session, question: str, *, document_ids: list[str] | None = None
) -> Answer:
    result = retrieval.search(session, question, limit=ASK_TOP_K, document_ids=document_ids)
    if not result.passages:
        return Answer(AnswerMode.INSUFFICIENT_EVIDENCE, result.query, [])
    return Answer(AnswerMode.RETRIEVAL_ONLY, result.query, result.passages)
