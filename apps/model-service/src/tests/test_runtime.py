from __future__ import annotations

from io import BytesIO
from typing import cast

import torch
import torch.nn as nn
import torchvision
from PIL import Image

from src.runtime import ImageTransform, InferenceRuntime
from src.types import ModelSlug


class ConstantLogitsModel(nn.Module):
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        assert batch.shape[0] == 1
        return torch.tensor([[0.1, 0.9]], dtype=torch.float32)


class ThreeClassLogitsModel(nn.Module):
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        assert batch.shape[0] == 1
        return torch.tensor([[0.1, 0.2, 0.7]], dtype=torch.float32)


class FlatLogitsModel(nn.Module):
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        assert batch.shape[0] == 1
        return torch.tensor([0.1, 0.9], dtype=torch.float32)


class NonTensorModel(nn.Module):
    def forward(self, batch: torch.Tensor) -> list[float]:
        assert batch.shape[0] == 1
        return [0.1, 0.9]


def make_runtime() -> InferenceRuntime:
    transform = cast(
        ImageTransform,
        torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize((32, 32)),
                torchvision.transforms.ToTensor(),
            ]
        ),
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


def test_runtime_predict_returns_top_class_and_confidence() -> None:
    result = make_runtime().predict(make_png_bytes())

    assert result.prediction == "PNEUMONIA"
    assert 0.68 < result.confidence < 0.70


def test_runtime_rejects_logits_that_do_not_match_class_names() -> None:
    runtime = make_runtime()
    runtime.model = ThreeClassLogitsModel()

    try:
        runtime.predict(make_png_bytes())
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected logits/class label mismatch.")

    assert "Model logits/class label mismatch" in message
    assert "logits=3 labels=2" in message


def test_runtime_rejects_unbatched_logits() -> None:
    runtime = make_runtime()
    runtime.model = FlatLogitsModel()

    try:
        runtime.predict(make_png_bytes())
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected invalid logits shape.")

    assert "Model must produce logits with shape [1, classes]" in message


def test_runtime_rejects_non_tensor_model_output() -> None:
    runtime = make_runtime()
    runtime.model = NonTensorModel()

    try:
        runtime.predict(make_png_bytes())
    except TypeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected non-tensor model output failure.")

    assert message == "Model must produce a torch.Tensor."


def test_runtime_requires_at_least_two_class_labels() -> None:
    try:
        InferenceRuntime(
            slug=ModelSlug.EFFNETB0,
            model=ConstantLogitsModel(),
            transform=cast(ImageTransform, torchvision.transforms.ToTensor()),
            class_names=("NORMAL",),
            device=torch.device("cpu"),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected class label validation failure.")

    assert message == "Model Runtime requires at least 2 class labels."
