"""
Tests for core error handling and exception classes.
"""

import sys
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.errors import (
    BadCredentials,
    BadPassword,
    ClientNotAuthorized,
    ClientNotVerified,
    EntityNotFound,
    FastApiCoreError,
    InvalidToken,
    ServiceUnavailable,
    UpstreamServiceError,
    add_exception_handlers,
)

# =============================================================================
# Tests for exception classes
# =============================================================================


class TestFastApiCoreError:
    """Tests for FastApiCoreError base exception."""

    def test_default_status_code(self):
        """FastApiCoreError should default to 400."""
        assert FastApiCoreError.status == status.HTTP_400_BAD_REQUEST

    def test_default_detail(self):
        """FastApiCoreError should have default detail message."""
        assert FastApiCoreError.detail == "Request could not be processed."

    def test_custom_detail(self):
        """FastApiCoreError should accept custom detail."""
        error = FastApiCoreError("Custom error message")
        assert error.detail == "Custom error message"

    def test_inherits_from_exception(self):
        """FastApiCoreError should inherit from Exception."""
        assert issubclass(FastApiCoreError, Exception)


class TestEntityNotFound:
    """Tests for EntityNotFound exception."""

    def test_status_code(self):
        """EntityNotFound should have 404 status."""
        assert EntityNotFound.status == status.HTTP_404_NOT_FOUND

    def test_default_detail(self):
        """EntityNotFound should have appropriate detail."""
        assert EntityNotFound.detail == "Entity not found."


class TestClientNotAuthorized:
    """Tests for ClientNotAuthorized exception."""

    def test_status_code(self):
        """ClientNotAuthorized should have 401 status."""
        assert ClientNotAuthorized.status == status.HTTP_401_UNAUTHORIZED

    def test_default_detail(self):
        """ClientNotAuthorized should have appropriate detail."""
        assert ClientNotAuthorized.detail == "Client is not authorized to perform the action."


class TestInvalidToken:
    """Tests for InvalidToken exception."""

    def test_status_code(self):
        """InvalidToken should have 401 status."""
        assert InvalidToken.status == status.HTTP_401_UNAUTHORIZED

    def test_default_detail(self):
        """InvalidToken should have appropriate detail."""
        assert InvalidToken.detail == "Access token is invalid or expired."


class TestBadCredentials:
    """Tests for BadCredentials exception."""

    def test_status_code(self):
        """BadCredentials should have 401 status."""
        assert BadCredentials.status == status.HTTP_401_UNAUTHORIZED

    def test_default_detail(self):
        """BadCredentials should have appropriate detail."""
        assert BadCredentials.detail == "Email or password is incorrect."


class TestBadPassword:
    """Tests for BadPassword exception."""

    def test_status_code(self):
        """BadPassword should have 400 status."""
        assert BadPassword.status == status.HTTP_400_BAD_REQUEST

    def test_default_detail(self):
        """BadPassword should have appropriate detail."""
        assert BadPassword.detail == "Password does not meet requirements or could not be processed."


class TestClientNotVerified:
    """Tests for ClientNotVerified exception."""

    def test_status_code(self):
        """ClientNotVerified should have 403 status."""
        assert ClientNotVerified.status == status.HTTP_403_FORBIDDEN

    def test_default_detail(self):
        """ClientNotVerified should have appropriate detail."""
        assert ClientNotVerified.detail == "Email address has not been verified."


class TestServiceUnavailable:
    """Tests for ServiceUnavailable exception."""

    def test_status_code(self):
        assert ServiceUnavailable.status == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_default_detail(self):
        assert ServiceUnavailable.detail == "Dependent service is unavailable."


class TestUpstreamServiceError:
    """Tests for UpstreamServiceError exception."""

    def test_status_code(self):
        assert UpstreamServiceError.status == status.HTTP_502_BAD_GATEWAY

    def test_default_detail(self):
        assert UpstreamServiceError.detail == "Dependent service returned an invalid response."


# =============================================================================
# Tests for exception handler registration
# =============================================================================


class TestAddExceptionHandlers:
    """Tests for add_exception_handlers function."""

    def test_add_exception_handlers_registers_handlers(self):
        """add_exception_handlers should register exception handlers."""
        app = FastAPI()
        add_exception_handlers(app)

        # Check that exception handlers are registered
        assert len(app.exception_handlers) > 0

    def test_entity_not_found_handler_returns_404(self):
        """EntityNotFound handler should raise HTTPException with 404."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-not-found")
        async def test_not_found():
            raise EntityNotFound()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-not-found")
        assert response.status_code == 404

    def test_bad_credentials_handler_returns_401(self):
        """BadCredentials handler should raise HTTPException with 401."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-bad-credentials")
        async def test_bad_credentials():
            raise BadCredentials()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-bad-credentials")
        assert response.status_code == 401

    def test_client_not_verified_handler_returns_403(self):
        """ClientNotVerified handler should raise HTTPException with 403."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-not-verified")
        async def test_not_verified():
            raise ClientNotVerified()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-not-verified")
        assert response.status_code == 403

    def test_internal_server_error_handler(self):
        """Internal server error handler should return 500 with error detail."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-internal-error")
        async def test_internal_error():
            raise RuntimeError("Something broke")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-internal-error")
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_bad_password_handler_returns_400(self):
        """BadPassword handler should raise HTTPException with 400."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-bad-password")
        async def test_bad_password():
            raise BadPassword()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-bad-password")
        assert response.status_code == 400

    def test_invalid_token_handler_returns_401(self):
        """InvalidToken handler should raise HTTPException with 401."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-invalid-token")
        async def test_invalid_token():
            raise InvalidToken()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-invalid-token")
        assert response.status_code == 401

    def test_client_not_authorized_handler_returns_401(self):
        """ClientNotAuthorized handler should raise HTTPException with 401."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-not-authorized")
        async def test_not_authorized():
            raise ClientNotAuthorized()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-not-authorized")
        assert response.status_code == 401

    def test_handler_uses_custom_exception_detail(self):
        """Custom detail passed to exception instance should reach the response."""
        app = FastAPI()
        add_exception_handlers(app)

        @app.get("/test-service-unavailable")
        async def test_service_unavailable():
            raise ServiceUnavailable("Model-service URL is not configured.")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-service-unavailable")
        assert response.status_code == 503
        assert response.json()["detail"] == "Model-service URL is not configured."
