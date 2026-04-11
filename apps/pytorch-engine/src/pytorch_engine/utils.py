"""General-purpose utilities for the pytorch_engine package."""

import logging

import torch

logger = logging.getLogger(__name__)


def resolve_device(device: str | torch.device) -> torch.device:
    """Resolve ``"auto"`` to CUDA when available, else CPU.

    Args:
        device: ``"auto"`` selects CUDA if available, otherwise CPU.
            Also accepts an explicit device string or :class:`torch.device`.

    Returns:
        A resolved :class:`torch.device`.

    Example::

        device = resolve_device("auto")   # → cuda or cpu
        device = resolve_device("cuda:0") # → cuda:0
    """
    if isinstance(device, str) and device == "auto":
        chosen = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Auto-detected device: %s", chosen)
        return torch.device(chosen)
    resolved = torch.device(device)
    logger.info("Using explicit device: %s", resolved)
    return resolved


def get_current_device() -> torch.device:
    """Get the current device."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
