from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast
from uuid import uuid4

import torch
import torch.nn as nn
import torchvision

from src.config import Settings
from src.model_artifacts import HuggingFaceArtifactSource, load_state_dict, resolve_model_artifact
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


def test_resolve_model_artifact_reuses_existing_local_file() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"existing-{uuid4()}.pth"
    artifact_path.write_bytes(b"local")

    resolved = resolve_model_artifact(
        artifact_path,
        HuggingFaceArtifactSource(repo_id="owner/repo", revision="main", filename="remote.pth"),
        downloader=lambda source: (_ for _ in ()).throw(AssertionError("Downloader should not run.")),
    )

    assert resolved == artifact_path
    assert artifact_path.read_bytes() == b"local"


def test_resolve_model_artifact_fetches_from_hugging_face_when_missing() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"downloaded-{uuid4()}.pth"
    cached_path = workspace_tmp_dir / f"cached-{uuid4()}.pth"
    cached_path.write_bytes(b"remote")
    calls: list[HuggingFaceArtifactSource] = []

    def fake_downloader(source: HuggingFaceArtifactSource) -> Path:
        calls.append(source)
        return cached_path

    source = HuggingFaceArtifactSource(
        repo_id="RiP3rQ/effnetb0",
        revision="abc123",
        filename="effnetb0/best.pth",
        token="hf_token",
    )
    resolved = resolve_model_artifact(artifact_path, source, downloader=fake_downloader)

    assert resolved == artifact_path
    assert artifact_path.read_bytes() == b"remote"
    assert calls == [source]


def test_resolve_model_artifact_wraps_hugging_face_fetch_failure() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"missing-{uuid4()}.pth"
    source = HuggingFaceArtifactSource(
        repo_id="owner/private",
        revision="missing-revision",
        filename="weights/model.pth",
        token="secret-token",
    )

    def failing_downloader(source: HuggingFaceArtifactSource) -> Path:
        raise RuntimeError(
            "Failed to fetch Model Artifact from Hugging Face "
            f"repo={source.repo_id} revision={source.revision} filename={source.filename}"
        )

    try:
        resolve_model_artifact(artifact_path, source, downloader=failing_downloader)
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected Model Artifact fetch failure.")

    assert "owner/private" in message
    assert "missing-revision" in message
    assert "weights/model.pth" in message
    assert "secret-token" not in message


def test_resolve_model_artifact_validates_expected_sha256() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"checksum-{uuid4()}.pth"
    artifact_path.write_bytes(b"artifact")
    expected_sha256 = hashlib.sha256(b"artifact").hexdigest()

    resolved = resolve_model_artifact(artifact_path, None, expected_sha256=expected_sha256)

    assert resolved == artifact_path


def test_resolve_model_artifact_rejects_checksum_mismatch() -> None:
    workspace_tmp_dir = Path(__file__).resolve().parents[3] / "tmp" / "model-service-tests"
    workspace_tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = workspace_tmp_dir / f"checksum-mismatch-{uuid4()}.pth"
    artifact_path.write_bytes(b"artifact")

    try:
        resolve_model_artifact(artifact_path, None, expected_sha256="0" * 64)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected checksum mismatch.")

    assert "Model Artifact checksum mismatch" in message
    assert str(artifact_path) in message


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
