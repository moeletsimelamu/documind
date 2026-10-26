"""Queued documents must wait for a processing slot without holding a server worker thread."""

import threading
from pathlib import Path

import anyio
import anyio.to_thread
import pytest

from documind.db import create_db_engine, create_session_factory, init_schema
from documind.ingestion.pipeline import DocumentProcessor
from documind.storage import LocalFileStorage
from tests.conftest import make_settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_waiting_documents_do_not_occupy_the_shared_thread_pool(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data", max_concurrent_processing=1)
    settings.ensure_directories()
    engine = create_db_engine(settings.database_path)
    init_schema(engine)
    processor = DocumentProcessor(
        create_session_factory(engine), LocalFileStorage(settings.uploads_dir), settings
    )
    release = threading.Event()
    started: list[str] = []

    def slow_process(document_id: str) -> None:
        started.append(document_id)
        release.wait(10)

    processor.process = slow_process  # type: ignore[method-assign]
    shared_pool = anyio.to_thread.current_default_thread_limiter()

    async with anyio.create_task_group() as group:
        for n in range(6):
            group.start_soon(processor.process_in_background, f"doc-{n}")
        with anyio.fail_after(5):
            while not started:
                await anyio.sleep(0.01)
        await anyio.sleep(0.2)

        # One document is processing; five are queued, and none of them holds a shared thread.
        assert len(started) == 1
        assert shared_pool.borrowed_tokens == 0
        release.set()

    assert len(started) == 6
    engine.dispose()
