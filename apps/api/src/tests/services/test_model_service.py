"""
Tests for ModelService - getting models and orchestrating predictions.
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

from src.core.errors import EntityNotFound, ServiceUnavailable
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead, PredictionResponse, UnifiedPredictionResponse
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_service import ModelService
from src.services.s3_service import S3Service
from src.types.enums import ModelSlug, PredictionMode


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
def mock_runtime_client():
    """Create a mock runtime client."""
    runtime = MagicMock(spec=ModelRuntimeClient)
    runtime.predict = AsyncMock(return_value=MagicMock(prediction="cat", confidence=0.95))
    return runtime


@pytest.fixture
def mock_runtime_clients(mock_runtime_client):
    vit_client = MagicMock(spec=ModelRuntimeClient)
    vit_client.predict = AsyncMock(return_value=MagicMock(prediction="pneumonia", confidence=0.87))
    return {
        ModelSlug.EFFNETB0: mock_runtime_client,
        ModelSlug.VITB16: vit_client,
    }


@pytest.fixture
def fake_model():
    """Create a fake LLMModel instance."""
    model = MagicMock(spec=LLMModel)
    model.id = uuid4()
    model.name = "EffNetB0"
    model.slug = "effnetb0"
    model.description = "A test model"
    model.version = "v1"
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


@pytest.fixture
def model_service(mock_session, mock_s3_service, mock_runtime_clients):
    """Create a ModelService instance with mocked dependencies."""
    return ModelService(
        model=LLMModel,
        session=mock_session,
        s3_service=mock_s3_service,
        model_runtime_clients=mock_runtime_clients,
    )


class TestGetAllModels:
    """Tests for ModelService.get_all."""

    @pytest.mark.asyncio
    async def test_get_all_returns_model_reads(self, model_service, mock_session, fake_model):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fake_model]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await model_service.get_all()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ModelRead)
        assert result[0].name == "EffNetB0"
        assert result[0].slug == "effnetb0"

    @pytest.mark.asyncio
    async def test_get_all_empty_list(self, model_service, mock_session):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await model_service.get_all()

        assert isinstance(result, list)
        assert len(result) == 0


class TestGetModelById:
    """Tests for ModelService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_model_read(self, model_service, mock_session, fake_model):
        mock_session.get.return_value = fake_model

        result = await model_service.get(fake_model.id)

        assert isinstance(result, ModelRead)
        assert result.id == fake_model.id
        assert result.name == "EffNetB0"
        assert result.slug == "effnetb0"

    @pytest.mark.asyncio
    async def test_get_raises_entity_not_found(self, model_service, mock_session):
        mock_session.get.return_value = None

        with pytest.raises(EntityNotFound):
            await model_service.get(uuid4())


class TestPredictWithImage:
    """Tests for ModelService.predict_with_image."""

    @pytest.mark.asyncio
    async def test_predict_with_image_success(
        self,
        model_service,
        mock_session,
        mock_s3_service,
        mock_runtime_clients,
        fake_model,
    ):
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
        mock_runtime_clients[ModelSlug.EFFNETB0].predict.assert_called_once_with(
            image_data=b"fake_image_data",
            filename="test.jpg",
        )
        mock_s3_service.upload_image.assert_called_once_with(
            b"fake_image_data",
            "test.jpg",
        )

    @pytest.mark.asyncio
    async def test_predict_with_image_model_not_found(self, model_service, mock_session):
        mock_session.get.return_value = None
        model_id = uuid4()

        with pytest.raises(EntityNotFound):
            await model_service.predict_with_image(
                model_id=model_id,
                image_data=b"fake_image_data",
                filename="test.jpg",
            )

    @pytest.mark.asyncio
    async def test_predict_with_image_requires_runtime_client(self, mock_session, mock_s3_service, fake_model):
        service = ModelService(
            model=LLMModel,
            session=mock_session,
            s3_service=mock_s3_service,
            model_runtime_clients={},
        )
        mock_session.get.return_value = fake_model

        with pytest.raises(ServiceUnavailable):
            await service.predict_with_image(
                model_id=fake_model.id,
                image_data=b"fake_image_data",
                filename="test.jpg",
            )

    @pytest.mark.asyncio
    async def test_predict_public_single_model(self, model_service, mock_s3_service):
        result = await model_service.predict(
            mode=PredictionMode.EFFNETB0,
            image_data=b"fake_image_data",
            filename="test.jpg",
        )

        assert isinstance(result, UnifiedPredictionResponse)
        assert result.mode == PredictionMode.EFFNETB0
        assert result.upload.status == "ok"
        assert result.results[ModelSlug.EFFNETB0].status == "ok"
        assert result.results[ModelSlug.EFFNETB0].prediction == "cat"
        mock_s3_service.upload_image.assert_called_once_with(b"fake_image_data", "test.jpg")

    @pytest.mark.asyncio
    async def test_predict_public_both_models_parallel_result_map(self, model_service):
        result = await model_service.predict(
            mode=PredictionMode.BOTH,
            image_data=b"fake_image_data",
            filename="test.jpg",
        )

        assert result.mode == PredictionMode.BOTH
        assert result.results[ModelSlug.EFFNETB0].status == "ok"
        assert result.results[ModelSlug.VITB16].status == "ok"

    @pytest.mark.asyncio
    async def test_predict_public_partial_success_when_one_model_fails(
        self,
        mock_session,
        mock_s3_service,
        mock_runtime_clients,
    ):
        mock_runtime_clients[ModelSlug.VITB16].predict.side_effect = ServiceUnavailable("timeout")
        service = ModelService(
            model=LLMModel,
            session=mock_session,
            s3_service=mock_s3_service,
            model_runtime_clients=mock_runtime_clients,
        )

        result = await service.predict(
            mode=PredictionMode.BOTH,
            image_data=b"fake_image_data",
            filename="test.jpg",
        )

        assert result.results[ModelSlug.EFFNETB0].status == "ok"
        assert result.results[ModelSlug.VITB16].status == "error"
        assert result.results[ModelSlug.VITB16].error == "timeout"

    @pytest.mark.asyncio
    async def test_predict_with_image_s3_failure_is_best_effort(
        self,
        model_service,
        mock_session,
        mock_s3_service,
        fake_model,
    ):
        mock_session.get.return_value = fake_model
        mock_s3_service.upload_image.side_effect = RuntimeError("s3 down")

        result = await model_service.predict_with_image(
            model_id=fake_model.id,
            image_data=b"fake_image_data",
            filename="test.jpg",
        )

        assert result.image_s3_key is None
