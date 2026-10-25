from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Engine, delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from documind.db import (
    SCHEMA_VERSION,
    SchemaVersionError,
    create_db_engine,
    create_session_factory,
    init_schema,
    session_scope,
)
from documind.models import Chunk, Document, DocumentStatus, schema_meta


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_db_engine(tmp_path / "test.db")
    init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


def make_document(sha: str = "a" * 64, **overrides: object) -> Document:
    values: dict[str, object] = {
        "display_name": "report.pdf",
        "stored_name": f"{sha[:8]}.pdf",
        "file_type": "pdf",
        "size_bytes": 1024,
        "sha256": sha,
        "status": DocumentStatus.READY,
    }
    values.update(overrides)
    return Document(**values)


def fts_match_count(session: Session, term: str) -> int:
    count: int = session.execute(
        text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH :term"), {"term": term}
    ).scalar_one()
    return count


def test_connection_pragmas(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"


def test_schema_creates_tables_index_and_triggers(engine: Engine) -> None:
    with engine.connect() as connection:
        names = set(
            connection.execute(
                text("SELECT name FROM sqlite_master WHERE type IN ('table', 'trigger')")
            ).scalars()
        )
        version = connection.execute(
            select(schema_meta.c.value).where(schema_meta.c.key == "schema_version")
        ).scalar_one()

    assert {"documents", "chunks", "chunks_fts", "schema_meta"} <= names
    assert {"chunks_fts_insert", "chunks_fts_delete", "chunks_fts_update"} <= names
    assert version == str(SCHEMA_VERSION)


def test_init_schema_is_idempotent(engine: Engine) -> None:
    init_schema(engine)
    init_schema(engine)

    with engine.connect() as connection:
        rows = connection.execute(select(func.count()).select_from(schema_meta)).scalar_one()
    assert rows == 1


def test_newer_schema_version_is_refused(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(update(schema_meta).values(value=str(SCHEMA_VERSION + 1)))

    with pytest.raises(SchemaVersionError):
        init_schema(engine)


def test_inserted_chunks_are_searchable(factory: sessionmaker[Session]) -> None:
    with session_scope(factory) as session:
        document = make_document()
        document.chunks = [
            Chunk(ordinal=0, page=1, text="The invoice was paid in March."),
            Chunk(ordinal=1, page=2, text="Deliveries resume after the audit."),
        ]
        session.add(document)

    with factory() as session:
        assert fts_match_count(session, "invoice") == 1
        # Porter stemming: "deliveries" is indexed under the same stem as "delivery".
        assert fts_match_count(session, "delivery") == 1


def test_updated_chunk_text_is_reindexed(factory: sessionmaker[Session]) -> None:
    with session_scope(factory) as session:
        document = make_document()
        document.chunks = [Chunk(ordinal=0, page=1, text="original wording")]
        session.add(document)

    with session_scope(factory) as session:
        session.execute(update(Chunk).values(text="replacement wording"))

    with factory() as session:
        assert fts_match_count(session, "original") == 0
        assert fts_match_count(session, "replacement") == 1


def test_deleting_document_removes_chunks_and_index_rows(
    factory: sessionmaker[Session],
) -> None:
    with session_scope(factory) as session:
        kept = make_document("b" * 64)
        kept.chunks = [Chunk(ordinal=0, page=1, text="kept budget figures")]
        removed = make_document("c" * 64)
        removed.chunks = [Chunk(ordinal=0, page=1, text="removed budget figures")]
        session.add_all([kept, removed])
        session.flush()
        removed_id = removed.id

    # A bulk SQL delete: the cascade comes from the database's foreign key, not the ORM.
    with session_scope(factory) as session:
        session.execute(delete(Document).where(Document.id == removed_id))

    with factory() as session:
        remaining = session.execute(select(Chunk.document_id)).scalars().all()
        assert removed_id not in remaining
        assert len(remaining) == 1
        assert fts_match_count(session, "budget") == 1
        assert fts_match_count(session, "removed") == 0


def test_chunk_for_missing_document_is_rejected(factory: sessionmaker[Session]) -> None:
    with pytest.raises(IntegrityError), session_scope(factory) as session:
        session.add(Chunk(document_id="missing", ordinal=0, text="orphan"))


def test_duplicate_content_hash_is_rejected(factory: sessionmaker[Session]) -> None:
    with session_scope(factory) as session:
        session.add(make_document("d" * 64))

    with pytest.raises(IntegrityError), session_scope(factory) as session:
        session.add(make_document("d" * 64, stored_name="other.pdf"))


def test_invalid_status_is_rejected_by_database(factory: sessionmaker[Session]) -> None:
    with session_scope(factory) as session:
        session.add(make_document("e" * 64))

    with pytest.raises(IntegrityError), session_scope(factory) as session:
        session.execute(text("UPDATE documents SET status = 'done'"))


def test_session_scope_rolls_back_on_error(factory: sessionmaker[Session]) -> None:
    with pytest.raises(RuntimeError), session_scope(factory) as session:
        session.add(make_document("f" * 64))
        session.flush()
        raise RuntimeError("boom")

    with factory() as session:
        assert session.execute(select(func.count()).select_from(Document)).scalar_one() == 0


def test_timestamps_round_trip_as_utc(factory: sessionmaker[Session]) -> None:
    created = datetime(2026, 10, 25, 14, 30, tzinfo=timezone(timedelta(hours=2)))
    with session_scope(factory) as session:
        document = make_document("0" * 64, created_at=created)
        session.add(document)
        session.flush()
        document_id = document.id

    with factory() as session:
        loaded = session.get_one(Document, document_id)
        assert loaded.created_at == datetime(2026, 10, 25, 12, 30, tzinfo=UTC)
        assert loaded.created_at.tzinfo is UTC
