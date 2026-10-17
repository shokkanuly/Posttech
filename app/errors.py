"""Stable, redacted API errors. Never serialize SQL, passwords, or request bodies."""

import logging
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException

from app.localization import language_for, translate

logger = logging.getLogger("janamen")


def error_response(request: Request, status: int, message: str, fields=None, headers=None):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    language = language_for(request)
    original_message = message
    message = translate(message, language)
    if language != "en" and message == original_message:
        message = translate(
            "Invalid input" if status < 500 else "An unexpected error occurred", language
        )
    localized_fields = [
        {
            **field,
            "message": translate(field["message"], language)
            if translate(field["message"], language) != field["message"] or language == "en"
            else translate("Please check this field", language),
        }
        for field in (fields or [])
    ]
    codes = {
        401: "unauthenticated",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "validation_error",
        429: "rate_limited",
        503: "database_unavailable",
    }
    return JSONResponse(
        status_code=status,
        content={
            "detail": message,
            "error": {
                "code": codes.get(status, "request_error" if status < 500 else "internal_error"),
                "message": message,
                "fields": localized_fields,
            },
            "request_id": request_id,
        },
        headers={
            **(headers or {}),
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "same-origin",
            "Content-Language": language,
            "Vary": "Accept-Language",
        },
    )


def install_error_handlers(app):
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(request, exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return error_response(request, 422, "Invalid input", fields)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, _exc: IntegrityError):
        return error_response(request, 409, "This operation conflicts with existing data")

    @app.exception_handler(OperationalError)
    async def database_error(request: Request, _exc: OperationalError):
        logger.error("Database unavailable request_id=%s", request.state.request_id)
        return error_response(request, 503, "Database temporarily unavailable; retry later")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled %s request_id=%s", type(exc).__name__, request.state.request_id)
        return error_response(request, 500, "An unexpected error occurred")
