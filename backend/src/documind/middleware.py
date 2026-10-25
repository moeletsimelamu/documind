"""Per-request plumbing: request IDs, the access log, security headers and unhandled errors."""

import logging
import re
import time
import uuid
from http import HTTPStatus

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from documind.errors import error_response
from documind.logging_setup import request_id_var

access_logger = logging.getLogger("documind.access")
error_logger = logging.getLogger("documind.errors")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# JSON API responses never need to load anything.
_API_CSP = "default-src 'none'; frame-ancestors 'none'"
# FastAPI's Swagger UI page loads its assets from jsDelivr and uses an inline bootstrap script.
_DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
)
# The single-page app. Angular adds component styles at runtime, hence 'unsafe-inline' for styles.
_APP_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)

_COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _headers_for(path: str) -> dict[str, str]:
    headers = dict(_COMMON_HEADERS)
    if path.startswith("/api/docs"):
        headers["Content-Security-Policy"] = _DOCS_CSP
    elif path.startswith("/api/"):
        headers["Content-Security-Policy"] = _API_CSP
        headers["Cache-Control"] = "no-store"
    else:
        headers["Content-Security-Policy"] = _APP_CSP
    return headers


class RequestContextMiddleware:
    """Pure ASGI middleware, outermost in the application's own stack."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        path: str = scope["path"]
        method: str = scope["method"]
        extra_headers = _headers_for(path)
        extra_headers["X-Request-ID"] = request_id
        response_state = {"status": 0, "started": False}

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_state["started"] = True
                response_state["status"] = message["status"]
                headers = MutableHeaders(scope=message)
                for name, value in extra_headers.items():
                    headers.setdefault(name, value)
            await send(message)

        started_at = time.perf_counter()
        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            error_logger.exception("Unhandled error during %s %s", method, path)
            if response_state["started"]:
                raise
            response = error_response(
                Request(scope),
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "Something went wrong on the server. Quote the request ID if you report it.",
            )
            await response(scope, receive, send_with_headers)
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            # Path only: query strings can contain search terms and are deliberately not logged.
            access_logger.info(
                "%s %s -> %s (%.1f ms)", method, path, response_state["status"], elapsed_ms
            )
            request_id_var.reset(token)
