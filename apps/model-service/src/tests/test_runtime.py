from __future__ import annotations

from io import BytesIO

import torch
import torch.nn as nn
import torchvision
from PIL import Image

from src.runtime import InferenceRuntime
from src.types import ModelSlug


class ConstantLogitsModel(nn.Module):
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        assert batch.shape[0] == 1
        return torch.tensor([[0.1, 0.9]], dtype=torch.float32)


def make_runtime() -> InferenceRuntime:
    transform = torchvision.transforms.Compose(
        [
            torchvision.transforms.Resize((32, 32)),
            torchvision.transforms.ToTensor(),
        ]
    )
    return InferenceRuntime(
        slug=ModelSlug.EFFNETB0,
        model=ConstantLogitsModel(),
        transform=transform,
        class_names=("NORMAL", "PNEUMONIA"),
        device=torch.device("cpu"),
    )


def make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(120, 120, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_runtime_predict_returns_top_class_and_confidence():
    result = make_runtime().predict(make_png_bytes())

    assert result.prediction == "PNEUMONIA"
    assert 0.68 < result.confidence < 0.70
