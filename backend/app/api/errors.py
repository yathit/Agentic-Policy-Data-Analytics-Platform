"""
Error handling and Problem JSON responses (RFC7807).
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from typing import List, Optional


class APIException(HTTPException):
    """Base API exception with Problem JSON support."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: str,
        error_type: str = "about:blank",
        errors: Optional[List[dict]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.title = title
        self.error_type = error_type
        self.errors = errors


class NotFoundError(APIException):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            status_code=404,
            title="Not Found",
            detail=f"{resource} with ID '{resource_id}' not found",
            error_type="about:blank",
        )


class ValidationException(APIException):
    """Validation error."""

    def __init__(self, detail: str, errors: Optional[List[dict]] = None):
        super().__init__(
            status_code=422,
            title="Validation Error",
            detail=detail,
            error_type="about:blank",
            errors=errors,
        )


class ConflictError(APIException):
    """Conflict error (e.g., invalid state transition)."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=409,
            title="Conflict",
            detail=detail,
            error_type="about:blank",
        )


def problem_response(
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    error_type: str = "about:blank",
    errors: Optional[List[dict]] = None,
) -> JSONResponse:
    """Create a Problem JSON response."""
    content = {
        "type": error_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        content["instance"] = instance
    if errors:
        content["errors"] = errors

    return JSONResponse(status_code=status_code, content=content)


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle APIException and return Problem JSON."""
    return problem_response(
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        instance=str(request.url.path),
        error_type=exc.error_type,
        errors=exc.errors,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle generic HTTPException and return Problem JSON."""
    return problem_response(
        status_code=exc.status_code,
        title="Error",
        detail=str(exc.detail),
        instance=str(request.url.path),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation errors and return Problem JSON."""
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        })

    return problem_response(
        status_code=422,
        title="Validation Error",
        detail="Request validation failed",
        instance=str(request.url.path),
        errors=errors,
    )
