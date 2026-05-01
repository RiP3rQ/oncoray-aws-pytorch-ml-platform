from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import Settings
from src.model_artifacts import load_state_dict
from src.model_specs import MODEL_SPECS, ModelSpec
from src.runtime import InferenceRuntime
from src.torch_environment import configure_torch_threads, resolve_device
from src.types import ModelSlug

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelRuntimeFactory:
    settings: Settings
    model_specs: dict[ModelSlug, ModelSpec]

    @classmethod
    def from_settings(cls, settings: Settings) -> ModelRuntimeFactory:
        return cls(settings=settings, model_specs=MODEL_SPECS)

    def build(self) -> InferenceRuntime:
        configure_torch_threads(self.settings.MODEL_NUM_THREADS)

        artifact_path = self.settings.MODEL_ARTIFACT_PATH
        if not artifact_path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

        spec = self.model_specs[self.settings.MODEL_SLUG]
        device = resolve_device(self.settings.MODEL_DEVICE)
        model = spec.build_model(len(self.settings.class_names))
        state_dict = load_state_dict(artifact_path, map_location=device)
        model.load_state_dict(state_dict, strict=self.settings.MODEL_STRICT_LOAD)
        model.to(device)
        model.eval()

        logger.info(
            "Loaded model runtime slug=%s artifact=%s device=%s classes=%s",
            self.settings.MODEL_SLUG,
            artifact_path,
            device,
            ",".join(self.settings.class_names),
        )
        return InferenceRuntime(
            slug=self.settings.MODEL_SLUG,
            model=model,
            transform=spec.build_transform(),
            class_names=self.settings.class_names,
            device=device,
        )
