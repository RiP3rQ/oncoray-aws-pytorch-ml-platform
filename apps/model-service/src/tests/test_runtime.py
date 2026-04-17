from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

import torch
import torch.nn as nn
import torchvision
from PIL import Image

from src.runtime import InferenceRuntime, load_state_dict
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


def test_load_state_dict_accepts_nested_checkpoint():
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"checkpoint-{uuid4()}.pth"
    expected = {"layer.weight": torch.ones(2, 2)}
    torch.save({"model_state_dict": expected}, artifact_path)
    resolved = load_state_dict(artifact_path, map_location=torch.device("cpu"))
    assert torch.equal(resolved["layer.weight"], expected["layer.weight"])
