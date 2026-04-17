from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import torch
import torch.nn as nn
import torchvision
from PIL import Image
from torchvision.transforms import InterpolationMode

from src.config import Settings
from src.schemas import PredictionResponse
from src.types import ModelSlug

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class ModelSpec:
    """Architecture and transform factory for one deployable model."""

    slug: ModelSlug
    build_model: Callable[[int], nn.Module]
    build_transform: Callable[[], torchvision.transforms.Compose]


def build_effnetb0_model(num_classes: int) -> nn.Module:
    model = torchvision.models.efficientnet_b0(weights=None)
    classifier_head = model.classifier[-1]
    if not isinstance(classifier_head, nn.Linear):
        raise TypeError(f"Expected nn.Linear classifier head, got {type(classifier_head)}")

    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features=classifier_head.in_features, out_features=num_classes),
    )
    return model


def build_vitb16_model(num_classes: int) -> nn.Module:
    model = torchvision.models.vit_b_16(weights=None)
    original_classifier = next(
        (module for module in reversed(list(model.heads.modules())) if isinstance(module, nn.Linear)),
        None,
    )
    if original_classifier is None:
        raise TypeError(f"Expected nn.Linear inside model.heads, got {type(model.heads)}")

    model.heads = nn.Sequential(
        nn.Linear(in_features=original_classifier.in_features, out_features=num_classes),
    )
    return model


def build_effnetb0_transform() -> torchvision.transforms.Compose:
    return torchvision.transforms.Compose(
        [
            torchvision.transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
            torchvision.transforms.CenterCrop(224),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )


def build_vitb16_transform() -> torchvision.transforms.Compose:
    return torchvision.transforms.Compose(
        [
            torchvision.transforms.Resize((224, 224), interpolation=InterpolationMode.BICUBIC),
            torchvision.transforms.ToTensor(),
            torchvision.transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )


MODEL_SPECS: dict[ModelSlug, ModelSpec] = {
    ModelSlug.EFFNETB0: ModelSpec(
        slug=ModelSlug.EFFNETB0,
        build_model=build_effnetb0_model,
        build_transform=build_effnetb0_transform,
    ),
    ModelSlug.VITB16: ModelSpec(
        slug=ModelSlug.VITB16,
        build_model=build_vitb16_model,
        build_transform=build_vitb16_transform,
    ),
}


@dataclass
class InferenceRuntime:
    """Loaded in-memory model runtime for one deployment."""

    slug: ModelSlug
    model: nn.Module
    transform: torchvision.transforms.Compose
    class_names: tuple[str, ...]
    device: torch.device

    @classmethod
    def from_settings(cls, settings: Settings) -> "InferenceRuntime":
        configure_torch_threads(settings.MODEL_NUM_THREADS)

        artifact_path = settings.MODEL_ARTIFACT_PATH
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

        spec = MODEL_SPECS[settings.MODEL_SLUG]
        device = resolve_device(settings.MODEL_DEVICE)
        model = spec.build_model(num_classes=len(settings.class_names))
        state_dict = load_state_dict(artifact_path, map_location=device)
        model.load_state_dict(state_dict, strict=settings.MODEL_STRICT_LOAD)
        model.to(device)
        model.eval()

        logger.info(
            "Loaded model runtime slug=%s artifact=%s device=%s classes=%s",
            settings.MODEL_SLUG,
            artifact_path,
            device,
            ",".join(settings.class_names),
        )
        return cls(
            slug=settings.MODEL_SLUG,
            model=model,
            transform=spec.build_transform(),
            class_names=settings.class_names,
            device=device,
        )

    def predict(self, image_data: bytes) -> PredictionResponse:
        if len(image_data) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Image size {len(image_data)} bytes exceeds the maximum allowed size of {MAX_IMAGE_SIZE_BYTES} bytes."
            )

        with Image.open(BytesIO(image_data)) as image:
            rgb_image = image.convert("RGB")
            transformed = self.transform(rgb_image)

        if not isinstance(transformed, torch.Tensor):
            raise TypeError("Transform must produce a torch.Tensor.")

        batch = transformed.unsqueeze(0).to(self.device)
        with torch.inference_mode():
            logits = self.model(batch)
            probabilities = torch.softmax(logits, dim=1)

        predicted_index = int(probabilities.argmax(dim=1).item())
        confidence = float(probabilities[0, predicted_index].item())
        return PredictionResponse(
            prediction=self.class_names[predicted_index],
            confidence=confidence,
        )


def configure_torch_threads(num_threads: int) -> None:
    resolved_threads = max(1, num_threads)
    torch.set_num_threads(resolved_threads)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        logger.debug("Torch interop thread count already initialised; leaving as-is.")


def resolve_device(requested_device: str) -> torch.device:
    normalized = requested_device.strip().lower()
    if normalized == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(normalized)


def load_state_dict(artifact_path: Path, map_location: torch.device) -> dict[str, Any]:
    payload = torch.load(artifact_path, map_location=map_location)
    if isinstance(payload, dict):
        if any(isinstance(value, torch.Tensor) for value in payload.values()):
            return payload

        for key in ("state_dict", "model_state_dict", "model"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested

    raise TypeError(f"Unsupported model artifact payload at {artifact_path}")

