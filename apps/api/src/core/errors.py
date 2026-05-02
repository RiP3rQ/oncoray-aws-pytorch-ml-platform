from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from src.core.observability import record_exception


class FastApiCoreError(Exception):
    """Base exception for all exceptions in fastapi core"""

    # status_code to be returned for this exception
    # when it is handled
    status = status.HTTP_400_BAD_REQUEST
    detail = "Request could not be processed."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class EntityNotFound(FastApiCoreError):
    """Entity not found in database"""

    status = status.HTTP_404_NOT_FOUND
    detail = "Entity not found."


class ClientNotAuthorized(FastApiCoreError):
    """Client is not authorized to perform the action"""

    status = status.HTTP_401_UNAUTHORIZED
    detail = "Client is not authorized to perform the action."


class InvalidToken(FastApiCoreError):
    """Access token is invalid or expired"""

    status = status.HTTP_401_UNAUTHORIZED
    detail = "Access token is invalid or expired."


class BadCredentials(FastApiCoreError):
    """Email or password is incorrect."""

    status = status.HTTP_401_UNAUTHORIZED
    detail = "Email or password is incorrect."


class BadPassword(FastApiCoreError):
    """Password does not meet requirements or could not be processed."""

    status = status.HTTP_400_BAD_REQUEST
    detail = "Password does not meet requirements or could not be processed."


class ClientNotVerified(FastApiCoreError):
    """Email address has not been verified."""

    status = status.HTTP_403_FORBIDDEN
    detail = "Email address has not been verified."


class ServiceUnavailable(FastApiCoreError):
    """Dependent service is unavailable."""

    status = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Dependent service is unavailable."


class UpstreamServiceError(FastApiCoreError):
    """Dependent service returned an invalid response."""

    status = status.HTTP_502_BAD_GATEWAY
    detail = "Dependent service returned an invalid response."

    def __init__(self, detail: str | None = None, upstream_status_code: int | None = None):
        self.upstream_status_code = upstream_status_code
        super().__init__(detail)


def _get_handler(status: int, detail: str) -> Callable[[Request, Exception], Response]:
    """Create FastAPI exception handler for a custom core error type."""

    def handler(request: Request, exception: Exception) -> Response:
        resolved_detail = detail
        if isinstance(exception, FastApiCoreError):
            resolved_detail = exception.detail

        raise HTTPException(
            status_code=status,
            detail=resolved_detail,
        )

    return handler


def add_exception_handlers(app: FastAPI) -> None:
    # Get all subclass of our custom exceptions
    exception_classes = FastApiCoreError.__subclasses__()

    for exception_class in exception_classes:
        app.add_exception_handler(
            exception_class,
            _get_handler(
                status=exception_class.status,
                detail=exception_class.detail,
            ),
        )

    @app.exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR)
    def internal_server_error_handler(
        request: Request,
        exception: Exception,
    ) -> Response:
        record_exception(exception)
        return JSONResponse(
            content={"detail": "Something went wrong..."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
