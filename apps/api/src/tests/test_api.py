"""
Test cases for the FastAPI Core API.

These tests use dependency injection to mock external services like
databases, Redis, and S3.
"""

from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient


# =============================================================================
# Root Endpoint Tests
# =============================================================================


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_get_root_returns_service_info(self, client: TestClient):
        """GET / should return service name and status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"

    def test_get_root_returns_json(self, client: TestClient):
        """GET / should return application/json content type."""
        response = client.get("/")
        assert response.headers["content-type"] == "application/json"


# =============================================================================
# Scalar Docs Endpoint Tests
# =============================================================================


class TestScalarDocsEndpoint:
    """Tests for the Scalar API reference endpoint."""

    def test_get_scalar_returns_html(self, client: TestClient):
        """GET /scalar should return HTML for Scalar API reference."""
        response = client.get("/scalar")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_get_scalar_contains_title(self, client: TestClient):
        """GET /scalar should include the API title."""
        response = client.get("/scalar")
        assert "Core API" in response.text


# =============================================================================
# Health Probe Endpoint Tests
# =============================================================================


class TestHealthProbes:
    """Tests for Kubernetes health probe endpoints."""

    def test_get_livez_returns_ok(self, client: TestClient):
        """GET /livez should return ok status without dependency checks."""
        response = client.get("/livez")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"

    def test_get_readyz_returns_ok_with_mocked_deps(self, client: TestClient):
        """GET /readyz should return ok when dependencies are mocked."""
        response = client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"
        assert "checks" in data
        assert data["checks"]["database"] is True
        assert data["checks"]["redis"] is True

    def test_get_startupz_returns_ok(self, client: TestClient):
        """GET /startupz should return ok status."""
        response = client.get("/startupz")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"

    def test_get_health_returns_ok(self, client: TestClient):
        """GET /health should return ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"

    def test_get_healthz_returns_ok(self, client: TestClient):
        """GET /healthz should return ok status."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"


# =============================================================================
# Model Endpoint Tests
# =============================================================================


class TestModelEndpoints:
    """Tests for /model/* endpoints."""

    def test_get_all_models(self, client: TestClient):
        """GET /model/ should return list of models."""
        response = client.get("/model/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # Default mock has 2 models

    def test_get_all_models_returns_model_structure(self, client: TestClient):
        """GET /model/ should return models with correct fields."""
        response = client.get("/model/")
        assert response.status_code == 200
        models = response.json()
        for model in models:
            assert "id" in model
            assert "name" in model
            assert "description" in model
            assert "version" in model
            assert "created_at" in model
            assert "updated_at" in model

    def test_get_model_by_id(self, client: TestClient, mock_models: list[MagicMock]):
        """GET /model/{model_id} should return a specific model."""
        model_id = mock_models[0].id
        response = client.get(f"/model/{model_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(model_id)
        assert data["name"] == mock_models[0].name

    def test_get_model_by_invalid_id_format(self, client: TestClient):
        """GET /model/{invalid_uuid} should return 422 for invalid UUID."""
        response = client.get("/model/not-a-uuid")
        assert response.status_code == 422

    def test_get_nonexistent_model_returns_404(self, client: TestClient):
        """GET /model/{non_existent_id} should return 404."""
        non_existent_id = uuid4()
        response = client.get(f"/model/{non_existent_id}")
        assert response.status_code == 404

    def test_predict_with_image(self, client: TestClient, mock_models: list[MagicMock]):
        """POST /model/{model_id}/predict should return prediction."""
        model_id = mock_models[0].id
        image_data = b"fake_image_data"
        files = {"image": ("test.jpg", BytesIO(image_data), "image/jpeg")}

        response = client.post(f"/model/{model_id}/predict", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "model_id" in data
        assert "prediction" in data
        assert "confidence" in data
        assert "image_s3_key" in data
        assert data["prediction"] == "cat"
        assert data["confidence"] == 0.95

    def test_predict_with_image_too_large(
            self, client: TestClient, mock_models: list[MagicMock]
    ):
        """POST /model/{model_id}/predict with oversized image should return 413."""
        model_id = mock_models[0].id
        # Create image data larger than 2MB
        large_image = b"x" * (3 * 1024 * 1024)
        files = {"image": ("large.jpg", BytesIO(large_image), "image/jpeg")}

        response = client.post(f"/model/{model_id}/predict", files=files)
        assert response.status_code == 413


# =============================================================================
# User Endpoint Tests
# =============================================================================


class TestUserEndpoints:
    """Tests for /user/* endpoints."""

    def test_register_user(self, client: TestClient):
        """POST /user/signup should create a new user."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
        }
        response = client.post("/user/signup", json=user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"

    def test_register_user_invalid_email(self, client: TestClient):
        """POST /user/signup with invalid email should return 422."""
        user_data = {
            "email": "not-an-email",
            "password": "securepassword123",
        }
        response = client.post("/user/signup", json=user_data)
        assert response.status_code == 422

    def test_register_user_short_password(self, client: TestClient):
        """POST /user/signup with short password should return 422."""
        user_data = {
            "email": "user@example.com",
            "password": "short",
        }
        response = client.post("/user/signup", json=user_data)
        assert response.status_code == 422

    def test_login_valid_credentials(self, client: TestClient):
        """POST /user/token with valid credentials should return token."""
        response = client.post(
            "/user/token",
            data={"username": "valid@example.com", "password": "validpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "jwt"

    def test_login_invalid_credentials(self, client: TestClient):
        """POST /user/token with invalid credentials should return 401."""
        response = client.post(
            "/user/token",
            data={"username": "invalid@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_get_user_profile_unauthenticated(self, client: TestClient):
        """GET /user/me without auth should return 401."""
        response = client.get("/user/me")
        assert response.status_code == 401

    def test_get_user_profile_authenticated(
            self, authenticated_client: TestClient, mock_user: MagicMock
    ):
        """GET /user/me with auth should return user profile."""
        response = authenticated_client.get("/user/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_user.email

    def test_verify_user_email(self, client: TestClient):
        """GET /user/verify should verify user email."""
        response = client.get("/user/verify?token=fake_token")
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Account verified"

    def test_logout_unauthenticated(self, client: TestClient):
        """GET /user/logout without auth should return 401."""
        response = client.get("/user/logout")
        assert response.status_code == 401

    def test_logout_authenticated(self, authenticated_client: TestClient):
        """GET /user/logout with auth should return success message."""
        response = authenticated_client.get("/user/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Successfully logged out"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for exception handling."""

    def test_entity_not_found_returns_404(self, client: TestClient):
        """Non-existent resource should return 404."""
        non_existent_id = uuid4()
        response = client.get(f"/model/{non_existent_id}")
        assert response.status_code == 404

    def test_invalid_token_returns_401(self, client: TestClient, mock_user: MagicMock):
        """Invalid auth token should return 401."""
        # Calling an endpoint that requires auth with no token
        response = client.get("/user/me")
        assert response.status_code == 401


# =============================================================================
# OpenAPI Schema Tests
# =============================================================================


class TestOpenAPISchema:
    """Tests for OpenAPI schema generation."""

    def test_openapi_schema_available(self, client: TestClient):
        """GET /openapi.json should return OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_paths_include_expected_endpoints(self, client: TestClient):
        """OpenAPI schema should include all expected endpoints."""
        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})

        # Root endpoint
        assert "/" in paths

        # Model endpoints
        assert "/model/" in paths
        assert "/model/{model_id}" in paths
        assert "/model/{model_id}/predict" in paths

        # User endpoints
        assert "/user/signup" in paths
        assert "/user/token" in paths
        assert "/user/me" in paths

        # Health endpoints
        assert "/livez" in paths
        assert "/readyz" in paths
        assert "/health" in paths
