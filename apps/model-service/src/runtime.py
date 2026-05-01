from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import torch
import torch.nn as nn
import torchvision
from PIL import Image, UnidentifiedImageError

from src.schemas import ModelRuntimePrediction
from src.types import ModelSlug


@dataclass
class InferenceRuntime:
    """Loaded in-memory model runtime for one deployment."""

    slug: ModelSlug
    model: nn.Module
    transform: torchvision.transforms.Compose
    class_names: tuple[str, ...]
    device: torch.device

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
            probabilities = torch.softmax(logits, dim=1)

        predicted_index = int(probabilities.argmax(dim=1).item())
        confidence = float(probabilities[0, predicted_index].item())
        return ModelRuntimePrediction(
            prediction=self.class_names[predicted_index],
            confidence=confidence,
        )
