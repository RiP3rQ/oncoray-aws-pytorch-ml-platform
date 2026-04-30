"""
Tests for ModelCatalog reads.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.errors import EntityNotFound
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead
from src.services.model_catalog import ModelCatalog


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def fake_model():
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
def model_catalog(mock_session):
    return ModelCatalog(session=mock_session)


class TestListModels:
    @pytest.mark.asyncio
    async def test_list_models_returns_model_reads(self, model_catalog, mock_session, fake_model):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fake_model]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await model_catalog.list_models()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], ModelRead)
        assert result[0].name == "EffNetB0"
        assert result[0].slug == "effnetb0"

    @pytest.mark.asyncio
    async def test_list_models_returns_empty_list(self, model_catalog, mock_session):
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await model_catalog.list_models()

        assert result == []


class TestGetModel:
    @pytest.mark.asyncio
    async def test_get_model_returns_model_read(self, model_catalog, mock_session, fake_model):
        mock_session.get.return_value = fake_model

        result = await model_catalog.get_model(fake_model.id)

        assert isinstance(result, ModelRead)
        assert result.id == fake_model.id
        assert result.name == "EffNetB0"
        assert result.slug == "effnetb0"

    @pytest.mark.asyncio
    async def test_get_model_raises_entity_not_found(self, model_catalog, mock_session):
        mock_session.get.return_value = None

        with pytest.raises(EntityNotFound):
            await model_catalog.get_model(uuid4())
