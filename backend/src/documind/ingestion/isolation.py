"""Run a function in a separate process with a hard time limit.

Parsing untrusted PDFs can take pathologically long (pypdf has had infinite-loop and
decompression-bomb bugs). A thread cannot be stopped, but a process can: on timeout it is
terminated and the document is marked as failed.
"""

import logging
import multiprocessing
from collections.abc import Callable
from multiprocessing.connection import Connection, wait
from typing import Any

logger = logging.getLogger(__name__)


class IsolationTimeoutError(Exception):
    pass


class IsolationCrashError(Exception):
    pass


def _child_main(connection: Connection, func: Callable[[Any], Any], arg: Any) -> None:
    # Parser warnings are noise here and can be numerous for damaged files.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        connection.send(("ok", func(arg)))
    except Exception as exc:
        try:
            connection.send(("error", exc))
        except Exception:  # the exception itself could not be pickled
            connection.send(("error", RuntimeError(type(exc).__name__)))
    finally:
        connection.close()


def run_isolated[T, R](func: Callable[[T], R], arg: T, timeout: float) -> R:
    """Call ``func(arg)`` in a fresh process. Exceptions raised by ``func`` are re-raised here.

    Raises IsolationTimeoutError if no result arrives within ``timeout`` seconds, and
    IsolationCrashError if the process exits without sending one.

    ``arg`` should be small: it is sent while the process starts, and that send can block if the
    process dies before reading it. Pass a file path rather than file contents.
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child_main, args=(sender, func, arg), daemon=True)
    process.start()
    sender.close()
    try:
        # Wait for a result or for the process to exit. Watching only the pipe is not enough: a
        # process that dies during start-up may never close its end, so no EOF would arrive.
        ready = wait([receiver, process.sentinel], timeout)
        if not ready:
            raise IsolationTimeoutError(f"No result within {timeout:g} seconds")
        if receiver not in ready and not receiver.poll():
            raise IsolationCrashError(f"Worker process exited with code {process.exitcode}")
        try:
            status, payload = receiver.recv()
        except EOFError as exc:
            raise IsolationCrashError("Worker process exited without a result") from exc
    finally:
        receiver.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join()
        process.close()

    if status == "ok":
        result: R = payload
        return result
    raise payload
