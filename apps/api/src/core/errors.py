from fastapi import status


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
