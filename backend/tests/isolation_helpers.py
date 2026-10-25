"""Functions run in child processes by test_isolation.py (they must be importable by name)."""

import os
import time

from documind.ingestion.extraction import ExtractionError


def double(value: int) -> int:
    return value * 2


def fail_with_extraction_error(_: object) -> None:
    raise ExtractionError("encrypted", "Locked.")


def sleep_forever(_: object) -> None:
    time.sleep(600)


def exit_abruptly(_: object) -> None:
    os._exit(3)


class CrashesWhenUnpickled:
    """Pickles fine here, but kills the child process while it is still starting up."""

    def __reduce__(self) -> tuple[object, tuple[int]]:
        return (os._exit, (7,))
