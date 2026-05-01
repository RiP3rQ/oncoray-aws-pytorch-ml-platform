from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import torch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HuggingFaceArtifactSource:
    repo_id: str
    revision: str
    filename: str
    token: str | None = None


class ArtifactDownloader(Protocol):
    def __call__(self, source: HuggingFaceArtifactSource) -> Path: ...


def download_hugging_face_artifact(source: HuggingFaceArtifactSource) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("huggingface-hub is required to fetch Model Artifacts from Hugging Face.") from exc

    try:
        return Path(
            hf_hub_download(
                repo_id=source.repo_id,
                filename=source.filename,
                revision=source.revision,
                token=source.token,
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to fetch Model Artifact from Hugging Face "
            f"repo={source.repo_id} revision={source.revision} filename={source.filename}"
        ) from exc


def resolve_model_artifact(
    artifact_path: Path,
    source: HuggingFaceArtifactSource | None,
    *,
    expected_sha256: str | None = None,
    downloader: ArtifactDownloader = download_hugging_face_artifact,
) -> Path:
    if artifact_path.is_file():
        verify_model_artifact_checksum(artifact_path, expected_sha256)
        return artifact_path

    if source is None:
        raise FileNotFoundError(f"Model artifact not found: {artifact_path}")

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Fetching model artifact repo=%s revision=%s filename=%s target=%s",
        source.repo_id,
        source.revision,
        source.filename,
        artifact_path,
    )
    downloaded_path = downloader(source)
    if not downloaded_path.is_file():
        raise FileNotFoundError(f"Downloaded Model Artifact not found: {downloaded_path}")
    if downloaded_path.resolve() != artifact_path.resolve():
        shutil.copy2(downloaded_path, artifact_path)
    verify_model_artifact_checksum(artifact_path, expected_sha256)
    return artifact_path


def verify_model_artifact_checksum(artifact_path: Path, expected_sha256: str | None) -> None:
    if expected_sha256 is None:
        return

    actual_sha256 = file_sha256(artifact_path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            "Model Artifact checksum mismatch "
            f"path={artifact_path} expected_sha256={expected_sha256} actual_sha256={actual_sha256}"
        )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
