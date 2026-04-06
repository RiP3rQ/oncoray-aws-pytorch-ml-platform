from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.core.config import security_settings

_serializer = URLSafeTimedSerializer(security_settings.JWT_SECRET)

def generate_access_token(
    data: dict,
    expiry: timedelta = timedelta(days=7),
) -> str:
    """
    Generate an access token.
    """
    return jwt.encode(
        payload={
            **data,
            "jti": str(uuid4()),
            "exp": datetime.now(timezone.utc) + expiry,
        },
        algorithm=security_settings.JWT_ALGORITHM,
        key=security_settings.JWT_SECRET,
    )


def decode_access_token(token: str) -> dict | None:
    """
    Decode an access token.
    """
    try:
        return jwt.decode(
            jwt=token,
            key=security_settings.JWT_SECRET,
            algorithms=[security_settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def generate_url_safe_token(data: dict, salt: str | None = None) -> str:
    """
    Generate a URL safe token.
    """
    return _serializer.dumps(data, salt=salt)


def decode_url_safe_token(
    token: str,
    salt: str | None = None,
    expiry: timedelta | None = None,
) -> dict | None:
    """
    Decode a URL safe token.
    """
    try:
        return _serializer.loads(
            token,
            salt=salt,
            max_age=expiry.total_seconds() if expiry else None,
        )
    except (BadSignature, SignatureExpired):
        return None