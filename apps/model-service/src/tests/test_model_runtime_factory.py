from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import uuid4

import torch
import torch.nn as nn
import torchvision

from src.config import Settings
from src.model_artifacts import load_state_dict
from src.model_runtime_factory import ModelRuntimeFactory
from src.model_specs import ModelSpec
from src.runtime import ImageTransform, InferenceRuntime
from src.types import ModelSlug


class TinyModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(2, 2)

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, self.linear(batch))


def build_tiny_model(num_classes: int) -> nn.Module:
    assert num_classes == 2
    return TinyModel()


def build_tiny_transform() -> ImageTransform:
    return cast(ImageTransform, torchvision.transforms.Compose([torchvision.transforms.ToTensor()]))


def test_load_state_dict_accepts_nested_checkpoint() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"checkpoint-{uuid4()}.pth"
    expected = {"layer.weight": torch.ones(2, 2)}
    torch.save({"model_state_dict": expected}, artifact_path)
    resolved = load_state_dict(artifact_path, map_location=torch.device("cpu"))
    assert torch.equal(resolved["layer.weight"], expected["layer.weight"])


def test_model_runtime_factory_builds_inference_runtime_from_settings() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"tiny-{uuid4()}.pth"
    model = TinyModel()
    torch.save(model.state_dict(), artifact_path)

    settings = Settings(
        MODEL_SLUG=ModelSlug.EFFNETB0,
        MODEL_ARTIFACT_PATH=artifact_path,
        MODEL_DEVICE="cpu",
        MODEL_CLASS_NAMES="NORMAL,PNEUMONIA",
        MODEL_STRICT_LOAD=True,
    )
    factory = ModelRuntimeFactory(
        settings=settings,
        model_specs={
            ModelSlug.EFFNETB0: ModelSpec(
                slug=ModelSlug.EFFNETB0,
                build_model=build_tiny_model,
                build_transform=build_tiny_transform,
            )
        },
    )

    runtime = factory.build()

    assert isinstance(runtime, InferenceRuntime)
    assert runtime.slug == ModelSlug.EFFNETB0
    assert runtime.class_names == ("NORMAL", "PNEUMONIA")
    assert runtime.device == torch.device("cpu")
