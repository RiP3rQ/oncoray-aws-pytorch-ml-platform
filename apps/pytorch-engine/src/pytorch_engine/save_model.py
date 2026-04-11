"""PyTorch model persistence utilities."""

import logging
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
