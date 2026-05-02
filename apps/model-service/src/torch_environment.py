# ruff: noqa: E402, I001
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def configure_torch_cache_dir() -> None:
    """Set Torch compiler cache path without asking Windows for current user."""
    if os.environ.get("TORCHINDUCTOR_CACHE_DIR"):
        return

    cache_root = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(cache_root / "pytorch-model" / "torchinductor")


configure_torch_cache_dir()

import torch


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
