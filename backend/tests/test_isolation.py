import sys
import time
from pathlib import Path

import pytest

from documind.config import Settings
from documind.ingestion.extraction import ExtractionError, ExtractionRequest, extract_file
from documind.ingestion.isolation import (
    IsolationCrashError,
    IsolationTimeoutError,
    memory_limit_supported,
    run_isolated,
)
from tests import isolation_helpers
from tests.pdf_factory import make_pdf, paragraph


def test_result_is_returned_from_child_process() -> None:
    assert run_isolated(isolation_helpers.double, 21, timeout=60) == 42


def test_exceptions_from_the_child_are_re_raised_with_their_details() -> None:
    with pytest.raises(ExtractionError) as caught:
        run_isolated(isolation_helpers.fail_with_extraction_error, None, timeout=60)

    assert caught.value.code == "encrypted"
    assert caught.value.message == "Locked."


def test_hung_work_is_stopped_at_the_time_limit() -> None:
    started = time.perf_counter()

    with pytest.raises(IsolationTimeoutError):
        # The limit includes process start-up, which takes about a second on Windows.
        run_isolated(isolation_helpers.sleep_forever, None, timeout=5)

    assert time.perf_counter() - started < 20


def test_child_that_dies_without_a_result_is_reported() -> None:
    with pytest.raises(IsolationCrashError):
        run_isolated(isolation_helpers.exit_abruptly, None, timeout=60)


def test_child_that_dies_during_start_up_is_reported_promptly() -> None:
    started = time.perf_counter()

    with pytest.raises(IsolationCrashError):
        run_isolated(isolation_helpers.exit_abruptly, isolation_helpers.CrashesWhenUnpickled(), 120)

    assert time.perf_counter() - started < 30


posix_only = pytest.mark.skipif(
    not memory_limit_supported(), reason="per-process memory limits need POSIX (resource module)"
)


@posix_only
def test_memory_limit_stops_runaway_allocation() -> None:
    with pytest.raises(MemoryError):
        run_isolated(
            isolation_helpers.allocate_megabytes, 1024, 60, memory_limit_bytes=512 * 1024 * 1024
        )


@posix_only
def test_memory_limit_leaves_room_for_normal_work() -> None:
    result = run_isolated(
        isolation_helpers.allocate_megabytes, 100, 60, memory_limit_bytes=1024 * 1024 * 1024
    )

    assert result == 100 * 1024 * 1024


@posix_only
def test_a_large_pdf_extracts_within_the_default_memory_limit(tmp_path: Path) -> None:
    path = tmp_path / "large.pdf"
    path.write_bytes(make_pdf([paragraph(f"topic {n}", 40) for n in range(200)]))
    request = ExtractionRequest(str(path), "pdf", max_pages=500, max_chars=2_000_000)

    document = run_isolated(
        extract_file, request, 120, memory_limit_bytes=Settings().extraction_memory_limit_mb * 2**20
    )

    assert document.page_count == 200


def test_memory_limit_support_matches_the_platform() -> None:
    assert memory_limit_supported() is (sys.platform != "win32")
