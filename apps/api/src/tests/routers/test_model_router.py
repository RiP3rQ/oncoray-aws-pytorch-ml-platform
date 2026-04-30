"""
Tests for model-related endpoints (/model/).
"""

from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient


class TestGetAllModels:
    """Tests for GET /model/"""

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
            assert "slug" in model
            assert "description" in model
            assert "version" in model
            assert "created_at" in model
            assert "updated_at" in model


class TestGetModelById:
    """Tests for GET /model/{model_id}"""

    def test_get_model_by_id(self, client: TestClient, mock_models: list[MagicMock]):
        """GET /model/{model_id} should return a specific model."""
        model_id = mock_models[0].id
        response = client.get(f"/model/{model_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(model_id)
        assert data["name"] == mock_models[0].name
        assert data["slug"] == mock_models[0].slug

    def test_get_model_by_invalid_id_format(self, client: TestClient):
        """GET /model/{invalid_uuid} should return 422 for invalid UUID."""
        response = client.get("/model/not-a-uuid")
        assert response.status_code == 422

    def test_get_nonexistent_model_returns_404(self, client: TestClient):
        """GET /model/{non_existent_id} should return 404."""
        non_existent_id = uuid4()
        response = client.get(f"/model/{non_existent_id}")
        assert response.status_code == 404


class TestPrediction:
    """Tests for public Prediction endpoints."""

    def test_model_id_prediction_route_is_removed(self, client: TestClient, mock_models: list[MagicMock]):
        """POST /model/{model_id}/predict should not exist."""
        model_id = mock_models[0].id
        files = {"image": ("test.jpg", BytesIO(b"fake_image_data"), "image/jpeg")}

        response = client.post(f"/model/{model_id}/predict", files=files)

        assert response.status_code == 404

    def test_public_predict_single_model(self, client: TestClient):
        """POST /predict should return unified single-model envelope."""
        files = {"image": ("test.jpg", BytesIO(b"fake_image_data"), "image/jpeg")}

        response = client.post("/predict?model=effnetb0", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "effnetb0"
        assert data["upload"]["status"] == "ok"
        assert "effnetb0" in data["results"]
        assert data["results"]["effnetb0"]["status"] == "ok"

    def test_public_predict_both_models(self, client: TestClient):
        """POST /predict?model=both should return both model results."""
        files = {"image": ("test.jpg", BytesIO(b"fake_image_data"), "image/jpeg")}

        response = client.post("/predict?model=both", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "both"
        assert "effnetb0" in data["results"]
        assert "vitb16" in data["results"]

    def test_public_predict_unsupported_image_type(self, client: TestClient):
        """POST /predict with unsupported type should return 415."""
        files = {"image": ("notes.txt", BytesIO(b"not-image"), "text/plain")}

        response = client.post("/predict?model=effnetb0", files=files)

        assert response.status_code == 415
