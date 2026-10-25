"""Database engine, sessions and schema initialisation.

The schema is created with ``create_all`` plus raw DDL for the FTS5 index and the triggers that
keep it in sync with ``chunks``. Alembic is not used because it cannot manage FTS5 virtual tables
or triggers; ``schema_meta.schema_version`` marks the schema so later changes can be migrated.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event, insert, select, text
from sqlalchemy.orm import Session, sessionmaker

from documind.models import Base, schema_meta

SCHEMA_VERSION = 1

_FTS_DDL = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
        text,
        content='chunks',
        content_rowid='id',
        tokenize='porter unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON chunks BEGIN
        INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE OF text ON chunks BEGIN
        INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
        INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
    END
    """,
)


class SchemaVersionError(RuntimeError):
    pass


def create_db_engine(database_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite:///{database_path}",
        # Sessions are used from FastAPI's thread pool and from background processing threads;
        # each session still holds its own connection.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _configure_connection(dbapi_connection: SQLiteConnection, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_schema(engine: Engine) -> None:
    """Create tables, the FTS index and triggers. Safe to call on every start-up."""
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for statement in _FTS_DDL:
            connection.execute(text(statement))
        stored = connection.execute(
            select(schema_meta.c.value).where(schema_meta.c.key == "schema_version")
        ).scalar_one_or_none()
        if stored is None:
            connection.execute(
                insert(schema_meta).values(key="schema_version", value=str(SCHEMA_VERSION))
            )
        elif int(stored) > SCHEMA_VERSION:
            raise SchemaVersionError(
                f"Database schema version {stored} is newer than this application "
                f"supports ({SCHEMA_VERSION})."
            )


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """A session that commits on success and rolls back on any exception."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
