from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.core.config import app_settings, security_settings


def _get_url_safe_serializer() -> URLSafeTimedSerializer:
    """Build a serializer with the current configured secret key."""

    return URLSafeTimedSerializer(security_settings.SECRET_KEY)


def generate_access_token(
    data: dict,
    expiry: timedelta | None = None,
) -> str:
    """
    Generate an access token.
    """
    token_expiry = expiry or timedelta(minutes=app_settings.ACCESS_TOKEN_TTL_MINUTES)

    return jwt.encode(
        payload={
            **data,
            "jti": str(uuid4()),
            "exp": datetime.now(UTC) + token_expiry,
        },
        algorithm=security_settings.ALGORITHM,
        key=security_settings.SECRET_KEY,
    )


def decode_access_token(token: str) -> dict | None:
    """
    Decode an access token.
    """
    try:
        return jwt.decode(
            jwt=token,
            key=security_settings.SECRET_KEY,
            algorithms=[security_settings.ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def generate_url_safe_token(data: dict, salt: str | None = None) -> str:
    """
    Generate a URL safe token.
    """
    return _get_url_safe_serializer().dumps(data, salt=salt)


def decode_url_safe_token(
    token: str,
    salt: str | None = None,
    expiry: timedelta | None = None,
) -> dict | None:
    """
    Decode a URL safe token.
    """
    try:
        return _get_url_safe_serializer().loads(
            token,
            salt=salt,
            max_age=expiry.total_seconds() if expiry else None,
        )
    except (BadSignature, SignatureExpired):
        return None
