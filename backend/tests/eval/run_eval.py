"""Measure retrieval quality on the evaluation set.

Run from ``backend/``:  python -m tests.eval.run_eval

Documents go through the real extraction, normalisation and chunking code (in-process) and the
real search function. A question is a hit at rank k if one of the top k passages comes from the
expected document and contains the anchor phrase.
"""

import hashlib
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from documind.db import create_db_engine, create_session_factory, init_schema, session_scope
from documind.ingestion.extraction import extract_bytes
from documind.ingestion.pipeline import build_chunks
from documind.models import Chunk, Document, DocumentStatus
from documind.retrieval import search
from tests.eval.dataset import DOCUMENTS, QUESTIONS, EvalQuestion
from tests.pdf_factory import make_pdf

TOP_K = 5


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass(frozen=True)
class QuestionResult:
    question: EvalQuestion
    rank: int | None  # 1-based rank of the first correct passage within TOP_K, or None


@dataclass(frozen=True)
class EvalReport:
    results: list[QuestionResult]

    def hit_rate(self, k: int, kind: str | None = None) -> float:
        selected = [r for r in self.results if kind is None or r.question.kind == kind]
        hits = sum(1 for r in selected if r.rank is not None and r.rank <= k)
        return hits / len(selected)

    def mrr(self, kind: str | None = None) -> float:
        selected = [r for r in self.results if kind is None or r.question.kind == kind]
        return sum(1 / r.rank for r in selected if r.rank) / len(selected)

    def table(self) -> str:
        lines = ["| Questions | n | hit@1 | hit@3 | hit@5 | MRR@5 |", "|---|---|---|---|---|---|"]
        for label, kind in (("All", None), ("Keyword", "keyword"), ("Paraphrase", "paraphrase")):
            n = sum(1 for r in self.results if kind is None or r.question.kind == kind)
            lines.append(
                f"| {label} | {n} | {self.hit_rate(1, kind):.0%} | {self.hit_rate(3, kind):.0%} "
                f"| {self.hit_rate(5, kind):.0%} | {self.mrr(kind):.2f} |"
            )
        return "\n".join(lines)


def evaluate() -> EvalReport:
    with tempfile.TemporaryDirectory() as directory:
        engine = create_db_engine(Path(directory) / "eval.db")
        try:
            init_schema(engine)
            factory = create_session_factory(engine)
            names: dict[str, str] = {}
            for doc in DOCUMENTS:
                if doc.pages is not None:
                    data, file_type = make_pdf(doc.pages), "pdf"
                else:
                    assert doc.text is not None
                    data, file_type = doc.text.encode(), "txt"
                extracted = extract_bytes(data, file_type, max_pages=500, max_chars=2_000_000)
                document_id = str(uuid.uuid4())
                names[document_id] = doc.name
                with session_scope(factory) as session:
                    document = Document(
                        id=document_id,
                        display_name=doc.name,
                        stored_name=f"{document_id}.{file_type}",
                        file_type=file_type,
                        size_bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest(),
                        status=DocumentStatus.READY,
                    )
                    document.chunks = [
                        Chunk(
                            ordinal=i,
                            page=d.page,
                            line_start=d.line_start,
                            line_end=d.line_end,
                            text=d.text,
                        )
                        for i, d in enumerate(build_chunks(extracted))
                    ]
                    session.add(document)

            results = []
            with factory() as session:
                for question in QUESTIONS:
                    passages = search(session, question.question, limit=TOP_K).passages
                    rank = next(
                        (
                            position
                            for position, p in enumerate(passages, start=1)
                            if names[p.document_id] == question.document
                            and _squash(question.anchor) in _squash(p.text)
                        ),
                        None,
                    )
                    results.append(QuestionResult(question, rank))
            return EvalReport(results)
        finally:
            engine.dispose()


def main() -> None:
    report = evaluate()
    print(report.table())
    print()
    for result in report.results:
        rank = str(result.rank) if result.rank else "miss"
        print(f"{rank:>4}  [{result.question.kind:10}] {result.question.question}")


if __name__ == "__main__":
    main()
