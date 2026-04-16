"""
Tests for user-related endpoints (/user/).
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestRegisterUser:
    """Tests for POST /user/signup"""

    def test_register_user(self, client: TestClient):
        """POST /user/signup should create a new user."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
        }
        response = client.post("/user/signup", json=user_data)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data

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


class TestLoginUser:
    """Tests for POST /user/token"""

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


class TestGetUserProfile:
    """Tests for GET /user/me"""

    def test_get_user_profile_unauthenticated(self, client: TestClient):
        """GET /user/me without auth should return 401."""
        response = client.get("/user/me")
        assert response.status_code == 401

    def test_get_user_profile_authenticated(self, authenticated_client: TestClient, mock_user: MagicMock):
        """GET /user/me with auth should return user profile."""
        response = authenticated_client.get("/user/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_user.email


class TestVerifyUserEmail:
    """Tests for GET /user/verify"""

    def test_verify_user_email(self, client: TestClient):
        """GET /user/verify should verify user email."""
        response = client.get("/user/verify?token=fake_token")
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Account verified"


class TestLogoutUser:
    """Tests for GET /user/logout"""

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
