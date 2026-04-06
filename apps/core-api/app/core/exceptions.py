from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from rich import print, panel

class CoreApiError(Exception):
    """Base exception for all exceptions in core api"""
    # status_code to be returned for this exception
    # when it is handled
    status: int = status.HTTP_400_BAD_REQUEST

class EntityNotFound(CoreApiError):
    """Entity not found in database"""

    status = status.HTTP_404_NOT_FOUND


class BadPassword(CoreApiError):
    """Password is not strong enough or invalid"""

    status = status.HTTP_400_BAD_REQUEST


class ClientNotAuthorized(CoreApiError):
    """Client is not authorized to perform the action"""

    status = status.HTTP_401_UNAUTHORIZED


class ClientNotVerified(CoreApiError):
    """Client is not verified"""

    status = status.HTTP_401_UNAUTHORIZED


class BadCredentials(CoreApiError):
    """User email or password is incorrect"""

    status = status.HTTP_401_UNAUTHORIZED


class InvalidToken(CoreApiError):
    """Access token is invalid or expired"""

    status = status.HTTP_401_UNAUTHORIZED

def _get_handler(status: int, detail: str):
    # Define
    def handler(request: Request, exception: Exception) -> Response:
        # DEBUG PRINT STATEMENT 👇
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
    exception_classes = CoreApiError.__subclasses__()

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
    def internal_server_error_handler(request, exception):
        return JSONResponse(
            content={"detail": "Something went wrong..."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={
                "X-Error": f"{exception}",
            }
        )
    