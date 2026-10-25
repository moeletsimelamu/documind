"""Application errors and the uniform JSON error envelope.

Every error response has the shape ``{"error": {"code", "message", "request_id", "details"?}}``.
"""

from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """An expected error with a stable code and a message that is safe to show to the user."""

    status_code: int = HTTPStatus.BAD_REQUEST
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"


def request_id_of(request: Request) -> str:
    return str(request.scope.get("state", {}).get("request_id", "-"))


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id_of(request),
    }
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": body})


_STATUS_CODES = {
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE: "file_too_large",  # only uploads have bodies this big
}


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(AppError, exc)
    return error_response(request, error.status_code, error.code, error.message, error.details)


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    error = cast(StarletteHTTPException, exc)
    status = HTTPStatus(error.status_code)
    code = _STATUS_CODES.get(status, status.phrase.lower().replace(" ", "_"))
    message = error.detail if isinstance(error.detail, str) else status.phrase
    response = error_response(request, error.status_code, code, message)
    if error.headers:
        response.headers.update(error.headers)
    return response


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(RequestValidationError, exc)
    # Only location and message are returned: the rejected input itself is not echoed back.
    details = [
        {"location": [str(part) for part in item.get("loc", ())], "message": item.get("msg", "")}
        for item in error.errors()
    ]
    return error_response(
        request,
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "invalid_request",
        "The request is invalid.",
        details,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
