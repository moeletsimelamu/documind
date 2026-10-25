import time

import pytest

from documind.ingestion.extraction import ExtractionError
from documind.ingestion.isolation import IsolationCrashError, IsolationTimeoutError, run_isolated
from tests import isolation_helpers


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
