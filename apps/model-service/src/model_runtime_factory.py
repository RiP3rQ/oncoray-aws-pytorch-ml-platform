from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import Settings
from src.model_artifacts import HuggingFaceArtifactSource, load_state_dict, resolve_model_artifact
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

        artifact_path = resolve_model_artifact(
            self.settings.MODEL_ARTIFACT_PATH,
            self._hugging_face_source(),
            expected_sha256=self.settings.MODEL_ARTIFACT_SHA256,
        )
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

    def _hugging_face_source(self) -> HuggingFaceArtifactSource | None:
        if self.settings.HF_MODEL_REPOSITORY is None:
            return None
        return HuggingFaceArtifactSource(
            repo_id=self.settings.HF_MODEL_REPOSITORY,
            revision=self.settings.HF_MODEL_REVISION,
            filename=self.settings.HF_MODEL_FILENAME or self.settings.MODEL_ARTIFACT_PATH.name,
            token=self.settings.HF_TOKEN,
        )
