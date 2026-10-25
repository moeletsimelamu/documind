import hashlib
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from documind.db import create_db_engine, create_session_factory, init_schema, session_scope
from documind.models import Chunk, Document, DocumentStatus
from documind.retrieval import (
    EmptyQueryError,
    make_excerpt,
    parse_query,
    search,
    split_highlights,
)

# --- Query parsing ---------------------------------------------------------------------------


def test_common_words_are_dropped_and_terms_lowercased() -> None:
    query = parse_query("What is the Budget for Project Falcon?")

    assert query.terms == ["budget", "project", "falcon"]
    assert query.match_expression() == '"budget" OR "project" OR "falcon"'


def test_a_query_of_only_common_words_is_kept() -> None:
    assert parse_query("to be or not to be").terms == ["to", "be", "or", "not"]


def test_quoted_text_is_searched_as_a_phrase() -> None:
    query = parse_query('"notice period" contract')

    assert query.phrases == [["notice", "period"]]
    assert query.terms == ["contract"]
    assert query.match_expression() == '"notice period" OR "contract"'
    assert query.searched_for == ["notice period", "contract"]


def test_repeated_terms_are_searched_once() -> None:
    assert parse_query("audit Audit AUDIT report").terms == ["audit", "report"]


@pytest.mark.parametrize(
    "raw",
    [
        "NEAR(budget audit, 2)",
        "budget*",
        "-audit",
        "^budget",
        "text:budget",
        "budget AND audit NOT risk",
        '"unbalanced quote',
        "'); DROP TABLE documents; --",
        "{budget audit}",
        "budget + audit",
    ],
)
def test_fts_syntax_in_queries_is_neutralised(raw: str) -> None:
    expression = parse_query(raw).match_expression()

    # Only quoted runs of letters/digits joined by OR: nothing FTS5 would interpret as syntax.
    for part in expression.split(" OR "):
        assert part.startswith('"') and part.endswith('"')
        assert all(ch.isalnum() or ch == " " for ch in part.strip('"'))


@pytest.mark.parametrize("raw", ["", "   ", "?!.,;", '""', "___"])
def test_queries_without_words_are_rejected(raw: str) -> None:
    with pytest.raises(EmptyQueryError):
        parse_query(raw)


def test_number_of_terms_is_capped() -> None:
    query = parse_query(" ".join(f"word{n}" for n in range(100)))

    assert len(query.terms) == 32


# --- Highlights and excerpts -----------------------------------------------------------------


def test_split_highlights_returns_plain_text_and_offsets() -> None:
    plain, spans = split_highlights("The \x01budget\x02 was \x01approved in March\x02.")

    assert plain == "The budget was approved in March."
    assert spans == [(4, 10), (15, 32)]
    assert [plain[s:e] for s, e in spans] == ["budget", "approved in March"]


def test_short_text_is_its_own_excerpt() -> None:
    excerpt = make_excerpt("Short text.", [(0, 5)], width=320)

    assert excerpt.text == "Short text."
    assert excerpt.highlights == [(0, 5)]
    assert not excerpt.starts_mid_text and not excerpt.ends_mid_text


def test_excerpt_window_follows_the_matches_and_keeps_offsets_valid() -> None:
    words = [f"filler{n}" for n in range(200)]
    words[150] = "budget"
    words[155] = "audit"
    text = " ".join(words)
    start_budget = text.index("budget")
    start_audit = text.index("audit")
    highlights = [(start_budget, start_budget + 6), (start_audit, start_audit + 5)]

    excerpt = make_excerpt(text, highlights, width=120)

    assert excerpt.starts_mid_text and excerpt.ends_mid_text
    assert [excerpt.text[s:e] for s, e in excerpt.highlights] == ["budget", "audit"]
    assert not excerpt.text.startswith(" ") and not excerpt.text.endswith(" ")
    assert excerpt.text in text


def test_excerpt_without_highlights_starts_at_the_beginning() -> None:
    excerpt = make_excerpt("word " * 200, [], width=100)

    assert not excerpt.starts_mid_text
    assert excerpt.ends_mid_text


# --- Search against a real index -------------------------------------------------------------


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_db_engine(tmp_path / "search.db")
    init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def add_document(
    factory: sessionmaker[Session],
    name: str,
    chunks: list[tuple[int | None, str]],
    status: DocumentStatus = DocumentStatus.READY,
) -> str:
    document_id = str(uuid.uuid4())
    with session_scope(factory) as session:
        document = Document(
            id=document_id,
            display_name=name,
            stored_name=f"{document_id}.pdf",
            file_type="pdf",
            size_bytes=100,
            sha256=hashlib.sha256(document_id.encode()).hexdigest(),
            status=status,
        )
        document.chunks = [
            Chunk(ordinal=i, page=page, text=text) for i, (page, text) in enumerate(chunks)
        ]
        session.add(document)
    return document_id


def test_results_are_ranked_and_identify_their_source(factory: sessionmaker[Session]) -> None:
    report = add_document(
        factory,
        "q3-report.pdf",
        [
            (1, "Revenue grew in the third quarter."),
            (2, "Supplier delays affected deliveries. The supplier audit found delivery risks."),
        ],
    )
    add_document(factory, "minutes.pdf", [(1, "The board discussed a new supplier.")])

    with factory() as session:
        result = search(session, "supplier delivery delays", limit=10)

    assert result.total_passages == 2
    assert result.total_documents == 2
    best = result.passages[0]
    assert (best.document_id, best.document_name, best.page) == (report, "q3-report.pdf", 2)
    matched = [best.text[s:e] for s, e in best.highlights]
    assert "delays" in matched and "deliveries" in matched and "Supplier" in matched


def test_word_forms_and_accents_match(factory: sessionmaker[Session]) -> None:
    add_document(factory, "notes.pdf", [(1, "Deliveries to the Café resumed.")])

    with factory() as session:
        assert search(session, "delivery", limit=5).total_passages == 1
        assert search(session, "cafe", limit=5).total_passages == 1
        assert search(session, "resuming", limit=5).total_passages == 1


def test_phrase_requires_adjacent_words(factory: sessionmaker[Session]) -> None:
    add_document(factory, "a.pdf", [(1, "The notice period is thirty days.")])
    add_document(factory, "b.pdf", [(1, "Period of notice: see clause four.")])

    with factory() as session:
        result = search(session, '"notice period"', limit=5)

    assert [p.document_name for p in result.passages] == ["a.pdf"]


def test_only_ready_documents_are_searched(factory: sessionmaker[Session]) -> None:
    add_document(factory, "ready.pdf", [(1, "audit findings")])
    add_document(factory, "processing.pdf", [(1, "audit findings")], DocumentStatus.PROCESSING)
    add_document(factory, "failed.pdf", [(1, "audit findings")], DocumentStatus.FAILED)

    with factory() as session:
        result = search(session, "audit", limit=10)

    assert [p.document_name for p in result.passages] == ["ready.pdf"]


def test_search_can_be_limited_to_selected_documents(factory: sessionmaker[Session]) -> None:
    first = add_document(factory, "first.pdf", [(1, "budget review")])
    second = add_document(factory, "second.pdf", [(1, "budget approval")])
    add_document(factory, "third.pdf", [(1, "budget cuts")])

    with factory() as session:
        result = search(session, "budget", limit=10, document_ids=[first, second])

    assert {p.document_id for p in result.passages} == {first, second}
    assert result.total_documents == 2


def test_limit_caps_passages_but_not_totals(factory: sessionmaker[Session]) -> None:
    add_document(factory, "log.pdf", [(n, f"Entry {n}: shipment logged.") for n in range(1, 31)])

    with factory() as session:
        result = search(session, "shipment", limit=5)

    assert len(result.passages) == 5
    assert result.total_passages == 30
    assert result.total_documents == 1


def test_no_matches(factory: sessionmaker[Session]) -> None:
    add_document(factory, "a.pdf", [(1, "nothing relevant here")])

    with factory() as session:
        result = search(session, "zebra", limit=5)

    assert result.passages == []
    assert result.total_passages == 0


def test_hostile_queries_run_safely(factory: sessionmaker[Session]) -> None:
    add_document(factory, "a.pdf", [(1, "near the budget, text and audit")])

    with factory() as session:
        for raw in ["NEAR(budget audit)", "text:budget", '"budget', "budget*", "-audit"]:
            result = search(session, raw, limit=5)
            assert result.total_passages == 1
