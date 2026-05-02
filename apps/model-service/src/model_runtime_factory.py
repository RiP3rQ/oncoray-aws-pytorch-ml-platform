from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import Settings
from src.model_artifacts import (
    load_model_artifact_payload,
    load_state_dict,
    read_model_artifact_manifest,
    resolve_model_artifact,
    validate_model_artifact_manifest,
)
from src.model_specs import MODEL_SPECS, ModelSpec
from src.runtime import InferenceRuntime
from src.runtime_definition import ModelRuntimeDefinition
from src.torch_environment import configure_torch_threads, resolve_device
from src.types import ModelSlug

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelRuntimeFactory:
    definition: ModelRuntimeDefinition

    @classmethod
    def from_settings(cls, settings: Settings) -> ModelRuntimeFactory:
        return cls.from_settings_and_specs(settings=settings, model_specs=MODEL_SPECS)

    @classmethod
    def from_settings_and_specs(
        cls,
        settings: Settings,
        model_specs: dict[ModelSlug, ModelSpec],
    ) -> ModelRuntimeFactory:
        return cls(definition=ModelRuntimeDefinition.from_settings(settings, model_specs))

    @classmethod
    def from_settings_for_slug(
        cls,
        settings: Settings,
        slug: ModelSlug,
        model_specs: dict[ModelSlug, ModelSpec] | None = None,
    ) -> ModelRuntimeFactory:
        return cls(definition=ModelRuntimeDefinition.from_settings_for_slug(settings, slug, model_specs or MODEL_SPECS))

    def build(self) -> InferenceRuntime:
        definition = self.definition
        configure_torch_threads(definition.num_threads)

        artifact_path = resolve_model_artifact(
            definition.artifact_path,
            definition.artifact_source,
            expected_sha256=definition.artifact_sha256,
        )
        device = resolve_device(definition.device_name)
        model = definition.spec.build_model(len(definition.class_names))
        payload = load_model_artifact_payload(artifact_path, map_location=device)
        validate_model_artifact_manifest(
            read_model_artifact_manifest(payload),
            expected_slug=definition.slug,
            expected_class_names=definition.class_names,
        )
        state_dict = load_state_dict(artifact_path, map_location=device, payload=payload)
        model.load_state_dict(state_dict, strict=definition.strict_load)
        model.to(device)
        model.eval()

        logger.info(
            "Loaded model runtime slug=%s artifact=%s device=%s classes=%s",
            definition.slug,
            artifact_path,
            device,
            ",".join(definition.class_names),
        )
        runtime = InferenceRuntime(
            slug=definition.slug,
            model=model,
            transform=definition.spec.build_transform(),
            class_names=definition.class_names,
            device=device,
        )
        if definition.startup_smoke_test:
            runtime.validate_model_contract(definition.spec.input_shape)
            logger.info("Validated model runtime startup contract slug=%s", definition.slug)

        return runtime
