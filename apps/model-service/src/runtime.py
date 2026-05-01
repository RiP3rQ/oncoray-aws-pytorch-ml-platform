from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

import torch
import torch.nn as nn
from PIL import Image, UnidentifiedImageError

from src.schemas import ModelRuntimePrediction
from src.types import ModelSlug


class ModelRuntime(Protocol):
    slug: ModelSlug

    def predict(self, image_data: bytes) -> ModelRuntimePrediction: ...


class ImageTransform(Protocol):
    def __call__(self, image: Image.Image) -> torch.Tensor: ...


@dataclass
class InferenceRuntime:
    """Loaded in-memory model runtime for one deployment."""

    slug: ModelSlug
    model: nn.Module
    transform: ImageTransform
    class_names: tuple[str, ...]
    device: torch.device

    def __post_init__(self) -> None:
        if len(self.class_names) < 2:
            raise ValueError("Model Runtime requires at least 2 class labels.")

    def predict(self, image_data: bytes) -> ModelRuntimePrediction:
        try:
            with Image.open(BytesIO(image_data)) as image:
                rgb_image = image.convert("RGB")
                transformed = self.transform(rgb_image)
        except UnidentifiedImageError as exc:
            raise ValueError("Invalid image data.") from exc

        if not isinstance(transformed, torch.Tensor):
            raise TypeError("Transform must produce a torch.Tensor.")

        batch = transformed.unsqueeze(0).to(self.device)
        with torch.inference_mode():
            logits = self.model(batch)
            self._validate_logits(logits)
            probabilities = torch.softmax(logits, dim=1)

        predicted_index = int(probabilities.argmax(dim=1).item())
        confidence = float(probabilities[0, predicted_index].item())
        return ModelRuntimePrediction(
            prediction=self.class_names[predicted_index],
            confidence=confidence,
        )

    def validate_model_contract(self, input_shape: tuple[int, ...]) -> None:
        synthetic_batch = torch.zeros((1, *input_shape), device=self.device)
        with torch.inference_mode():
            logits = self.model(synthetic_batch)
            self._validate_logits(logits)

    def _validate_logits(self, logits: torch.Tensor) -> None:
        if not isinstance(logits, torch.Tensor):
            raise TypeError("Model must produce a torch.Tensor.")
        if logits.ndim != 2 or logits.shape[0] != 1:
            raise RuntimeError(f"Model must produce logits with shape [1, classes], got {tuple(logits.shape)}.")
        if logits.shape[1] != len(self.class_names):
            raise RuntimeError(
                f"Model logits/class label mismatch logits={logits.shape[1]} labels={len(self.class_names)}."
            )
