from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse


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


# =============================== EXCEPTION HANDLER ===============================
def _get_handler(status: int, detail: str):
    # Define
    def handler(request: Request, exception: Exception) -> Response:
        # DEBUG PRINT STATEMENT 👇
        from rich import panel, print
        print(
            panel.Panel(
                exception.__class__.__name__,
                title="Handled Exception",
                border_style="red",
            ),
        )
        # DEBUG PRINT STATEMENT 👆
        
        # Raise HTTPException with given status and detail
        # can return JSONResponse as well
        raise HTTPException(
            status_code=status,
            detail=detail,
        )
    # Return ExceptionHandler required with given
    # status and detail for HTTPExcetion above
    return handler


def add_exception_handlers(app: FastAPI):
    # Get all subclass of 👇, our custom exceptions
    exception_classes = FastApiCoreError.__subclasses__()

    for exception_class in exception_classes:
        # Add exception handler
        app.add_exception_handler(
            # Custom exception class
            exception_class,
            # Get handler function
            _get_handler(
                status=exception_class.status,
                detail=exception_class.__doc__,
            ),
        )

    @app.exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR)
    def internal_server_error_handler(request: Request, exception: Exception) -> Response:
        return JSONResponse(
            content={"detail": "Something went wrong..."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={
                "X-Error": f"{exception}",
            }
        )