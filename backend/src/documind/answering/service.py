"""Question answering over retrieved passages.

1. Retrieve passages. None → ``insufficient_evidence``; the model is never asked.
2. No model configured → ``retrieval_only``: the passages are the response.
3. Otherwise ask the model to answer from the passages only, then check its reply: citations must
   name passages that were actually retrieved, and an answer without a valid citation, or one the
   model marks as insufficient, becomes ``insufficient_evidence``. Source details shown to the user
   always come from the retrieved passages, never from the model's text.
4. Provider failure → ``retrieval_only`` with the error, so the user still gets the passages.

A search result is never presented as a generated answer, and generated text is never shown
without sources.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from documind import retrieval
from documind.answering.prompt import SYSTEM_PROMPT, ModelReply, build_user_message, parse_reply
from documind.answering.prompt import source_id as make_source_id
from documind.answering.provider import LanguageModel, ProviderError

logger = logging.getLogger(__name__)

ASK_TOP_K = 6
ASK_MAX_CONTEXT_CHARS = 12_000

# One or more ids in brackets: [S1] or [S1, S3].
_CITATION = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([.,;:!?])")


class AnswerMode(StrEnum):
    GENERATED = "generated"
    RETRIEVAL_ONLY = "retrieval_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class GenerationError:
    code: str
    message: str


@dataclass(frozen=True)
class Answer:
    mode: AnswerMode
    query: retrieval.ParsedQuery
    passages: list[retrieval.Passage]
    text: str | None = None
    # Ids ("S1", ...) of passages the generated answer cites, in order of first use.
    cited: list[str] = field(default_factory=list)
    generation_error: GenerationError | None = None
    model: str | None = None


def ground_reply(reply: ModelReply, passage_count: int) -> tuple[str, list[str]]:
    """Remove citations to passages that were not retrieved; return the text and valid ids."""
    valid = {make_source_id(i) for i in range(passage_count)}
    found: list[str] = []

    def keep_valid(match: re.Match[str]) -> str:
        ids = [i.strip() for i in re.split(r"[,;]", match.group(1))]
        kept = [i for i in ids if i in valid]
        found.extend(kept)
        return "".join(f"[{i}]" for i in kept)

    text = _CITATION.sub(keep_valid, reply.answer)
    text = _SPACE_BEFORE_PUNCTUATION.sub(r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()
    listed = [i.strip() for i in reply.cited if i.strip() in valid]
    cited = list(dict.fromkeys(found + listed))
    return text, cited


def _within_context_budget(passages: list[retrieval.Passage]) -> list[retrieval.Passage]:
    kept: list[retrieval.Passage] = []
    total = 0
    for passage in passages:
        if kept and total + len(passage.text) > ASK_MAX_CONTEXT_CHARS:
            break
        kept.append(passage)
        total += len(passage.text)
    return kept


def answer_question(
    session: Session,
    question: str,
    *,
    document_ids: list[str] | None = None,
    model: LanguageModel | None = None,
) -> Answer:
    result = retrieval.search(session, question, limit=ASK_TOP_K, document_ids=document_ids)
    passages = _within_context_budget(result.passages)
    if not passages:
        return Answer(AnswerMode.INSUFFICIENT_EVIDENCE, result.query, [])
    if model is None:
        return Answer(AnswerMode.RETRIEVAL_ONLY, result.query, passages)

    try:
        reply = parse_reply(model.complete(SYSTEM_PROMPT, build_user_message(question, passages)))
    except ProviderError as exc:
        logger.warning("Answer generation failed: %s", exc.code)
        return Answer(
            AnswerMode.RETRIEVAL_ONLY,
            result.query,
            passages,
            generation_error=GenerationError(exc.code, exc.message),
            model=model.model,
        )

    text, cited = ground_reply(reply, len(passages))
    if not reply.sufficient or not cited or not text:
        if reply.sufficient:
            logger.info("Generated answer discarded: no valid citations")
        return Answer(AnswerMode.INSUFFICIENT_EVIDENCE, result.query, passages, model=model.model)
    return Answer(
        AnswerMode.GENERATED, result.query, passages, text=text, cited=cited, model=model.model
    )
