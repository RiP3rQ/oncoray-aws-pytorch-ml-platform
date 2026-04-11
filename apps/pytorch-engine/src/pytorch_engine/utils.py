"""General-purpose utilities for the pytorch_engine package."""

import logging

import torch

logger = logging.getLogger(__name__)


def get_current_device() -> torch.device:
    """Return the best available device (CUDA if available, else CPU).

    Shorthand for :func:`resolve_device` with ``"auto"``.

    Returns:
        A :class:`torch.device` pointing to CUDA when available, otherwise CPU.

    Example::

        device = get_current_device()  # → cuda or cpu
    """
    return resolve_device("auto")


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


def accuracy_fn(y_true: torch.Tensor, y_pred: torch.Tensor) -> float:
    """Compute classification accuracy as a fraction in [0, 1].

    Args:
        y_true: Ground-truth class indices.
        y_pred: Predicted class indices (same shape as *y_true*).

    Returns:
        Accuracy value between 0 and 1.

    Example::

        acc = accuracy_fn(y_true=torch.tensor([0, 1, 2]),
                          y_pred=torch.tensor([0, 2, 2]))
        # acc ≈ 0.6667
    """
    correct = torch.eq(y_true, y_pred).sum().item()
    return correct / len(y_pred)


def print_train_time(
    start: float, end: float, device: str | torch.device | None = None
) -> float:
    """Print and return the elapsed time between *start* and *end*.

    Args:
        start: Start timestamp (e.g. from :func:`time.time`).
        end: End timestamp.
        device: Device label to include in the output. Defaults to ``None``.

    Returns:
        Elapsed time in seconds.

    Example::

        start = time.time()
        # … training …
        elapsed = print_train_time(start, time.time(), device="cuda")
    """
    total_time = end - start
    device_str = f" on {device}" if device else ""
    logger.info("Train time%s: %.3f seconds", device_str, total_time)
    return total_time


def set_seeds(seed: int = 42) -> None:
    """Set random seeds for reproducible PyTorch operations.

    Seeds both CPU and CUDA random number generators.

    Args:
        seed: Random seed to set. Defaults to 42.

    Example::

        set_seeds(42)  # deterministic results
    """
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
