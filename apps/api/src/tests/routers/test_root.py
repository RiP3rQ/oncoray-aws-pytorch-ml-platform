"""
Tests for root (/) and Scalar docs (/scalar) endpoints.
"""

from fastapi.testclient import TestClient


class TestRootEndpoint:
    """Tests for GET /"""

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


class TestScalarDocsEndpoint:
    """Tests for GET /scalar"""

    def test_get_scalar_returns_html(self, client: TestClient):
        """GET /scalar should return HTML for Scalar API reference."""
        response = client.get("/scalar")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_get_scalar_contains_title(self, client: TestClient):
        """GET /scalar should include the API title."""
        response = client.get("/scalar")
        assert "Core API" in response.text
