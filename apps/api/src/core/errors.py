from fastapi import status


class FastApiCoreError(Exception):
    """Base exception for all exceptions in fastapi core"""
    # status_code to be returned for this exception
    # when it is handled
    status = status.HTTP_400_BAD_REQUEST


class EntityNotFound(FastApiCoreError):
    """Entity not found in database"""

    status = status.HTTP_404_NOT_FOUND
