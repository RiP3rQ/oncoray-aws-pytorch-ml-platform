from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import secrets

import bcrypt

from core_api.config import get_settings


class TokenValidationError(ValueError):
    """Raised when an access token cannot be trusted."""


@dataclass(frozen=True, slots=True)
class AccessTokenBundle:
    token: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    subject: int
    jti: str
    expires_at: datetime
    issued_at: datetime
    not_before: datetime


def _hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_password, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(_verify_password, password, password_hash)


def generate_session_identifier() -> str:
    return secrets.token_urlsafe(32)


def hash_session_identifier(identifier: str) -> str:
    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, *, issued_at: datetime | None = None) -> AccessTokenBundle:
    settings = get_settings()
    now = issued_at or datetime.now(UTC)
    jti = generate_session_identifier()
    expires_at = now + timedelta(minutes=settings.jwt_access_token_ttl_minutes)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "jti": jti,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = _encode_jwt(payload)
    return AccessTokenBundle(token=token, jti=jti, expires_at=expires_at)


def decode_access_token(token: str, *, now: datetime | None = None) -> AccessTokenClaims:
    settings = get_settings()
    payload = _decode_jwt(token)
    required_claims = {"sub", "type", "jti", "iss", "aud", "iat", "nbf", "exp"}
    if not required_claims.issubset(payload):
        raise TokenValidationError("Access token is missing required claims.")

    if payload["type"] != "access":
        raise TokenValidationError("Unsupported token type.")
    if payload["iss"] != settings.jwt_issuer:
        raise TokenValidationError("Unexpected token issuer.")

    audience = payload["aud"]
    if isinstance(audience, list):
        if settings.jwt_audience not in audience:
            raise TokenValidationError("Unexpected token audience.")
    elif audience != settings.jwt_audience:
        raise TokenValidationError("Unexpected token audience.")

    issued_at = _timestamp_to_datetime(payload["iat"], "iat")
    not_before = _timestamp_to_datetime(payload["nbf"], "nbf")
    expires_at = _timestamp_to_datetime(payload["exp"], "exp")
    current_time = now or datetime.now(UTC)
    skew = timedelta(seconds=settings.jwt_clock_skew_seconds)

    if current_time + skew < not_before:
        raise TokenValidationError("Token cannot be used yet.")
    if current_time - skew > expires_at:
        raise TokenValidationError("Token has expired.")
    if issued_at - skew > current_time:
        raise TokenValidationError("Token was issued in the future.")

    try:
        subject = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise TokenValidationError("Token subject must be an integer user id.") from exc

    jti = payload["jti"]
    if not isinstance(jti, str) or not jti:
        raise TokenValidationError("Token jti must be a non-empty string.")

    return AccessTokenClaims(
        subject=subject,
        jti=jti,
        expires_at=expires_at,
        issued_at=issued_at,
        not_before=not_before,
    )


def _encode_jwt(payload: dict[str, object]) -> str:
    settings = get_settings()
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        settings.jwt_secret.get_secret_value().encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    encoded_signature = _base64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def _decode_jwt(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise TokenValidationError("Malformed JWT.") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        settings.jwt_secret.get_secret_value().encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    signature = _base64url_decode(encoded_signature)
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenValidationError("JWT signature verification failed.")

    header = json.loads(_base64url_decode(encoded_header))
    if header.get("alg") != settings.jwt_algorithm or header.get("typ") != "JWT":
        raise TokenValidationError("Unsupported JWT header.")

    payload = json.loads(_base64url_decode(encoded_payload))
    if not isinstance(payload, dict):
        raise TokenValidationError("JWT payload must be an object.")

    return payload


def _timestamp_to_datetime(value: object, claim_name: str) -> datetime:
    if not isinstance(value, int):
        raise TokenValidationError(f"JWT claim '{claim_name}' must be an integer timestamp.")
    return datetime.fromtimestamp(value, tz=UTC)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise TokenValidationError("Invalid base64url encoding in JWT.") from exc
