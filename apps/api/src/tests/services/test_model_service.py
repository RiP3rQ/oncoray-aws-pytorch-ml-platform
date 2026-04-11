"""
Tests for ModelService - getting models and predictions.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.errors import EntityNotFound
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead, PredictionResponse
from src.services.model_service import ModelService
from src.services.s3_service import S3Service

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for unit tests."""
    session = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_s3_service():
    """Create a mock S3Service."""
    s3 = MagicMock(spec=S3Service)
    s3.upload_image = AsyncMock(return_value="predictions/test-uuid.jpg")
    return s3


@pytest.fixture
def fake_model():
    """Create a fake LLMModel instance."""
    model = MagicMock(spec=LLMModel)
    model.id = uuid4()
    model.name = "TestModel"
    model.description = "A test model"
    model.version = "v1"
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


@pytest.fixture
def model_service(mock_session, mock_s3_service):
    """Create a ModelService instance with mocked dependencies."""
    return ModelService(
        model=LLMModel, session=mock_session, s3_service=mock_s3_service
    )


# =============================================================================
# Tests for get_all
# =============================================================================


class TestGetAllModels:
    """Tests for ModelService.get_all."""

    @pytest.mark.asyncio
    async def test_get_all_returns_model_reads(
            self, model_service, mock_session, fake_model
    ):
        """get_all should return a list of ModelRead schemas."""
        # Mock the query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fake_model]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await model_service.get_all()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ModelRead)
        assert result[0].name == "TestModel"

    @pytest.mark.asyncio
    async def test_get_all_empty_list(self, model_service, mock_session):
        """get_all should return empty list when no models exist."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await model_service.get_all()

        assert isinstance(result, list)
        assert len(result) == 0


# =============================================================================
# Tests for get
# =============================================================================


class TestGetModelById:
    """Tests for ModelService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_model_read(
            self, model_service, mock_session, fake_model
    ):
        """get should return ModelRead when model is found."""
        mock_session.get.return_value = fake_model

        result = await model_service.get(fake_model.id)

        assert isinstance(result, ModelRead)
        assert result.id == fake_model.id
        assert result.name == "TestModel"

    @pytest.mark.asyncio
    async def test_get_raises_entity_not_found(self, model_service, mock_session):
        """get should raise EntityNotFound when model is not found."""
        mock_session.get.return_value = None

        with pytest.raises(EntityNotFound):
            await model_service.get(uuid4())


# =============================================================================
# Tests for predict_with_image
# =============================================================================


class TestPredictWithImage:
    """Tests for ModelService.predict_with_image."""

    @pytest.mark.asyncio
    async def test_predict_with_image_success(
            self, model_service, mock_session, mock_s3_service, fake_model
    ):
        """predict_with_image should return PredictionResponse for valid model."""
        mock_session.get.return_value = fake_model

        result = await model_service.predict_with_image(
            model_id=fake_model.id,
            image_data=b"fake_image_data",
            filename="test.jpg",
        )

        assert isinstance(result, PredictionResponse)
        assert result.prediction == "cat"
        assert result.confidence == 0.95
        assert result.model_id == fake_model.id
        mock_s3_service.upload_image.assert_called_once_with(
            b"fake_image_data", "test.jpg"
        )

    @pytest.mark.asyncio
    async def test_predict_with_image_model_not_found(
            self, model_service, mock_session
    ):
        """predict_with_image should raise EntityNotFound for nonexistent model."""
        mock_session.get.return_value = None
        model_id = uuid4()

        with pytest.raises(EntityNotFound):
            await model_service.predict_with_image(
                model_id=model_id,
                image_data=b"fake_image_data",
                filename="test.jpg",
            )

    @pytest.mark.asyncio
    async def test_predict_with_image_no_extension(
            self, model_service, mock_session, mock_s3_service, fake_model
    ):
        """predict_with_image should handle filenames without extensions."""
        mock_session.get.return_value = fake_model
        mock_s3_service.upload_image.return_value = "predictions/test-uuid"

        result = await model_service.predict_with_image(
            model_id=fake_model.id,
            image_data=b"fake_image_data",
            filename="no_extension",
        )

        assert isinstance(result, PredictionResponse)
