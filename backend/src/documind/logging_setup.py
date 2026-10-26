"""Logging configuration.

Log records carry the current request ID. By policy, log messages contain identifiers, sizes,
durations and error codes, never document text, search queries, questions or credentials.
"""

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s [%(request_id)s] %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not any(getattr(h, "_documind", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler.addFilter(RequestIdFilter())
        handler._documind = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    # Uvicorn's access log includes query strings, which can contain search terms. The
    # application writes its own access log line without them.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # The HTTP client logs every request URL at INFO; DocuMind logs provider calls itself.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
