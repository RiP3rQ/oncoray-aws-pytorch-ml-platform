from datetime import datetime, timezone
from uuid import UUID

from src.core.errors import EntityNotFound
from src.schemas.model_schemas import ModelRead
from src.services.base import BaseService

MOCK_MODELS: dict[UUID, ModelRead] = {
    UUID("11111111-1111-1111-1111-111111111111"): ModelRead(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        name="Model 1",
        description="Model 1 description",
        version="1.0.0",
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
    ),
    UUID("22222222-2222-2222-2222-222222222222"): ModelRead(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        name="Model 2",
        description="Model 2 description",
        version="1.0.0",
        created_at=datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc),
    ),
}


class ModelService(BaseService):
    """
    Service for managing models
    """

    def __init__(
        self,
    ):
        super().__init__()

    # Get a model by id
    async def get(self, id: UUID) -> ModelRead:
        """Get a model by id"""
        model = MOCK_MODELS.get(id)
        if model is None:
            raise EntityNotFound(f"Model '{id}' was not found.")
        return model.model_copy(deep=True)
