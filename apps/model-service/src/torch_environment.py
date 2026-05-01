from __future__ import annotations

import logging

import torch

logger = logging.getLogger(__name__)


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
