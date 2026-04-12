"""PyTorch model persistence utilities."""

import logging
from collections.abc import Callable
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

_DEFAULT_SAVE_DIR = "packages/pytorch-saved-models"

_VALID_EXTENSIONS = (".pt", ".pth")


def save_model(
    model: torch.nn.Module,
    model_name: str,
    target_dir: str = _DEFAULT_SAVE_DIR,
) -> Path:
    """Save a model's ``state_dict`` to disk.

    Creates *target_dir* (including parents) if it does not already exist.

    Args:
        model: A PyTorch model to persist.
        model_name: Filename for the saved checkpoint. Must end with
            ``".pt"`` or ``".pth"``.
        target_dir: Directory to write the checkpoint into.
            Defaults to ``"packages/pytorch-saved-models"``.

    Returns:
        The :class:`~pathlib.Path` where the checkpoint was written.

    Raises:
        ValueError: If *model_name* does not end with a recognised
            checkpoint extension.

    Example::

        saved_path = save_model(
            model=model_0,
            model_name="tingvgg_model.pth",
        )
    """
    if not model_name.endswith(_VALID_EXTENSIONS):
        msg = f"model_name must end with one of {_VALID_EXTENSIONS}, got {model_name!r}"
        raise ValueError(msg)

    save_path = Path(target_dir) / model_name
    save_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Saving model to %s", save_path)
    torch.save(model.state_dict(), save_path)

    return save_path


def upload_model_file_to_huggingface(
    local_file_path: str | Path,
    repo_id: str,
    token: str | None = None,
    repo_path: str | None = None,
    commit_message: str | None = None,
) -> str | None:
    """Upload a local model file to a Hugging Face model repository.

    Returns the Hub URL when upload succeeds, otherwise ``None``.
    """
    local_file = Path(local_file_path)
    if not local_file.is_file():
        raise FileNotFoundError(f"Checkpoint file not found: {local_file}")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        logger.warning(
            "huggingface_hub not installed; skipping upload for '%s'.",
            local_file,
        )
        return None

    try:
        api = HfApi(token=token)
        api.create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)
        destination = repo_path or local_file.name
        logger.info(
            "Uploading checkpoint '%s' to Hugging Face repo '%s' as '%s'.",
            local_file,
            repo_id,
            destination,
        )
        api.upload_file(
            path_or_fileobj=str(local_file),
            path_in_repo=destination,
            repo_id=repo_id,
            repo_type="model",
            commit_message=commit_message or f"Upload checkpoint {local_file.name}",
        )
        return f"https://huggingface.co/{repo_id}/blob/main/{destination}"
    except Exception as error:  # pragma: no cover - network/auth runtime dependent
        logger.warning("Hugging Face upload failed: %s", error)
        return None


def create_milestone_checkpoint_callback(
    model_name_prefix: str,
    total_epochs: int,
    every_n_epochs: int = 10,
    target_dir: str = _DEFAULT_SAVE_DIR,
    hf_repo_id: str | None = None,
    hf_token: str | None = None,
    hf_repo_subdir: str = "",
    upload_best_checkpoint: bool = False,
) -> Callable[[int, torch.nn.Module, dict, dict], None]:
    """Create epoch-end callback that saves milestone checkpoints.

    Saves checkpoints every *every_n_epochs* and on final epoch. Optionally
    saves best-by-test-accuracy checkpoints when metric improves. If
    *hf_repo_id* is provided, each saved checkpoint is also uploaded to
    Hugging Face.
    """
    normalized_subdir = hf_repo_subdir.strip("/").strip()
    best_test_accuracy: float | None = None

    def callback(
        epoch: int,
        model: torch.nn.Module,
        _train_result: dict,
        test_result: dict,
    ) -> None:
        nonlocal best_test_accuracy
        is_milestone = epoch % every_n_epochs == 0
        is_final = epoch == total_epochs
        test_accuracy = float(test_result.get("accuracy", 0.0))
        is_best = upload_best_checkpoint and (best_test_accuracy is None or test_accuracy > best_test_accuracy)
        if is_best:
            best_test_accuracy = test_accuracy

        checkpoints: list[tuple[str, str]] = []
        if is_milestone or is_final:
            base_name = f"{model_name_prefix}_epoch_{epoch:03d}.pth"
            checkpoints.append((base_name, f"Upload checkpoint at epoch {epoch}"))
        if is_best:
            best_name = f"{model_name_prefix}_best_epoch_{epoch:03d}_acc_{test_accuracy:.4f}.pth"
            checkpoints.append((best_name, f"Upload best checkpoint at epoch {epoch} acc={test_accuracy:.4f}"))

        for checkpoint_name, commit_message in checkpoints:
            saved_path = save_model(
                model=model,
                model_name=checkpoint_name,
                target_dir=target_dir,
            )
            if not hf_repo_id:
                continue
            path_in_repo = f"{normalized_subdir}/{checkpoint_name}" if normalized_subdir else checkpoint_name
            upload_model_file_to_huggingface(
                local_file_path=saved_path,
                repo_id=hf_repo_id,
                token=hf_token,
                repo_path=path_in_repo,
                commit_message=commit_message,
            )

    return callback
