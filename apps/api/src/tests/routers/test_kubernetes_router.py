"""
Tests for Kubernetes health probe endpoints (livez, readyz, startupz, health, healthz).
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestLivezProbe:
    """Tests for GET /livez"""

    def test_get_livez_returns_ok(self, client: TestClient):
        """GET /livez should return ok status without dependency checks."""
        response = client.get("/livez")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"

    def test_livez_no_checks_key(self, client: TestClient):
        """GET /livez should not include 'checks' key (no dependency probe)."""
        response = client.get("/livez")
        data = response.json()
        assert "checks" not in data


class TestReadyzProbe:
    """Tests for GET /readyz"""

    def test_get_readyz_returns_ok_with_mocked_deps(self, client: TestClient):
        """GET /readyz should return ok when dependencies are mocked."""
        response = client.get("/readyz")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"
        assert "checks" in data
        assert data["checks"]["database"] is True

    def test_readyz_degraded_when_db_fails(self, app):
        """GET /readyz should return degraded status when database is unreachable."""
        with patch(
            "src.routers.kubernetes_router.ping_database",
            new=AsyncMock(return_value=False),
        ):
            from fastapi.testclient import TestClient

            client = TestClient(app)
            response = client.get("/readyz")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["database"] is False


class TestStartupzProbe:
    """Tests for GET /startupz"""

    def test_get_startupz_returns_ok(self, client: TestClient):
        """GET /startupz should return ok status."""
        response = client.get("/startupz")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"
        assert "checks" in data


class TestHealthProbe:
    """Tests for GET /health"""

    def test_get_health_returns_ok(self, client: TestClient):
        """GET /health should return ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"


class TestHealthzProbe:
    """Tests for GET /healthz"""

    def test_get_healthz_returns_ok(self, client: TestClient):
        """GET /healthz should return ok status."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "core-api"
        assert data["status"] == "ok"
