from __future__ import annotations

import asyncio

import torch

from first_model.train import train


class ModelService:
    """Owns a lazily initialized in-memory model for local predictions."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._model: torch.nn.Module | None = None

    def is_ready(self) -> bool:
        return self._model is not None

    async def load(self) -> None:
        if self._model is not None:
            return

        async with self._lock:
            if self._model is None:
                self._model = await asyncio.to_thread(train, epochs=200, learning_rate=0.1)
                self._model.eval()

    async def predict(self, value: float) -> float:
        await self.load()
        assert self._model is not None
        return await asyncio.to_thread(self._predict_sync, value)

    def _predict_sync(self, value: float) -> float:
        with torch.no_grad():
            sample = torch.tensor([[value]], dtype=torch.float32)
            prediction = self._model(sample)

        return float(prediction.item())


model_service = ModelService()
