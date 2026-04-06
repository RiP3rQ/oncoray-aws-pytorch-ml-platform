import asyncio
from uuid import UUID
from src.services.base import BaseService
from src.core.errors import EntityNotFound

model_list = [
    {
        "id": 1,
        "name": "Model 1",
        "description": "Model 1 description",
        "version": "1.0.0",
    },
    {
        "id": 2,
        "name": "Model 2",
        "description": "Model 2 description",
        "version": "1.0.0",
    },
]


class ModelService(BaseService):
    """
    Service for managing models
    """
    def __init__(
        self,
    ):
        super().__init__()

    # Get a model by id
    async def get(self, id: UUID) -> dict[str, str | int] | None:
        """Get a model by id"""
        # Simulate 0.5 second delay
        await asyncio.sleep(0.5)
        # Check for model with given id
        fetched_model = next((model for model in model_list if model["id"] == id), None)
        if not fetched_model:
            raise EntityNotFound()
        return fetched_model