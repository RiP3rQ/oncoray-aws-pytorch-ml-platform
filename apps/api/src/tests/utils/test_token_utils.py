"""
Tests for token utility functions - JWT and URL-safe token generation/decoding.
"""

import sys
from datetime import timedelta
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.token_utils import (
    _get_url_safe_serializer,
    decode_access_token,
    decode_url_safe_token,
    generate_access_token,
    generate_url_safe_token,
)

# =============================================================================
# Tests for generate_access_token / decode_access_token
# =============================================================================


class TestAccessToken:
    """Tests for JWT access token generation and decoding."""

    def test_generate_access_token_returns_string(self):
        """generate_access_token should return a JWT string."""
        token = generate_access_token(data={"user": {"id": "123"}})
        assert isinstance(token, str)

    def test_decode_valid_access_token(self):
        """decode_access_token should decode a valid token."""
        payload = {"user": {"id": "123"}}
        token = generate_access_token(data=payload)
        decoded = decode_access_token(token)

        assert decoded is not None
        assert decoded["user"]["id"] == "123"
        assert "jti" in decoded
        assert "exp" in decoded

    def test_decode_token_includes_jti(self):
        """generate_access_token should include a jti claim."""
        token = generate_access_token(data={"user": {"id": "456"}})
        decoded = decode_access_token(token)

        assert "jti" in decoded
        assert isinstance(decoded["jti"], str)

    def test_decode_invalid_token_returns_none(self):
        """decode_access_token should return None for invalid tokens."""
        result = decode_access_token("invalid.token.here")
        assert result is None

    def test_decode_empty_token_returns_none(self):
        """decode_access_token should return None for empty string."""
        result = decode_access_token("")
        assert result is None

    def test_generate_token_with_custom_expiry(self):
        """generate_access_token should accept custom expiry timedelta."""
        token = generate_access_token(
            data={"user": {"id": "789"}},
            expiry=timedelta(hours=1),
        )
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["user"]["id"] == "789"

    def test_generate_token_payload_merged(self):
        """generate_access_token should merge custom data with jti and exp."""
        payload = {"user": {"id": "abc"}, "role": "admin"}
        token = generate_access_token(data=payload)
        decoded = decode_access_token(token)

        assert decoded["user"]["id"] == "abc"
        assert decoded["role"] == "admin"
        assert "jti" in decoded
        assert "exp" in decoded


# =============================================================================
# Tests for generate_url_safe_token / decode_url_safe_token
# =============================================================================


class TestUrlSafeToken:
    """Tests for URL-safe token generation and decoding."""

    def test_generate_url_safe_token_returns_string(self):
        """generate_url_safe_token should return a URL-safe string."""
        token = generate_url_safe_token(data={"id": "123"})
        assert isinstance(token, str)

    def test_decode_url_safe_token_roundtrip(self):
        """decode_url_safe_token should decode tokens from generate_url_safe_token."""
        data = {"id": "test-user-123"}
        token = generate_url_safe_token(data)
        decoded = decode_url_safe_token(token)

        assert decoded is not None
        assert decoded["id"] == "test-user-123"

    def test_decode_url_safe_token_with_salt(self):
        """URL-safe tokens should work with salt."""
        data = {"id": "456"}
        token = generate_url_safe_token(data, salt="verification")
        decoded = decode_url_safe_token(token, salt="verification")

        assert decoded is not None
        assert decoded["id"] == "456"

    def test_decode_url_safe_token_wrong_salt_returns_none(self):
        """decode_url_safe_token should return None when salt doesn't match."""
        data = {"id": "789"}
        token = generate_url_safe_token(data, salt="salt_a")
        decoded = decode_url_safe_token(token, salt="salt_b")

        assert decoded is None

    def test_decode_url_safe_token_invalid_returns_none(self):
        """decode_url_safe_token should return None for invalid tokens."""
        result = decode_url_safe_token("invalid_token_string")
        assert result is None

    def test_decode_url_safe_token_with_expiry(self):
        """decode_url_safe_token should work with expiry."""
        data = {"id": "expired"}
        token = generate_url_safe_token(data)
        # Should decode successfully with a generous expiry
        decoded = decode_url_safe_token(token, expiry=timedelta(hours=1))
        assert decoded is not None
        assert decoded["id"] == "expired"


# =============================================================================
# Tests for _get_url_safe_serializer
# =============================================================================


class TestGetUrlSafeSerializer:
    """Tests for _get_url_safe_serializer function."""

    def test_get_serializer_returns_instance(self):
        """_get_url_safe_serializer should return a URLSafeTimedSerializer."""
        from itsdangerous import URLSafeTimedSerializer

        serializer = _get_url_safe_serializer()
        assert isinstance(serializer, URLSafeTimedSerializer)
