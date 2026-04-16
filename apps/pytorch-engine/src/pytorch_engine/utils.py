"""General-purpose utilities for the pytorch_engine package."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np
import torch
from tqdm.auto import tqdm

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


def print_train_time(start: float, end: float, device: str | torch.device | None = None) -> float:
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


@dataclass
class ImageStats:
    """Per-channel image statistics in RGB order.

    Attributes:
        mean: Mean pixel value per channel (R, G, B), normalized to [0, 1].
        std: Standard deviation per channel (R, G, B), normalized to [0, 1].
    """

    mean: list[float]
    std: list[float]


def compute_img_mean_std(
    image_paths: Sequence[str],
    resize: tuple[int, int] = (224, 224),
) -> ImageStats:
    """Compute per-channel mean and standard deviation over a set of images.

    Reads each image from disk, converts BGR→RGB, resizes to ``resize``,
    normalizes pixel values from ``[0, 255]`` to ``[0, 1]``, then computes
    the channel-wise mean and standard deviation across the entire dataset.

    Args:
        image_paths: Sequence of file-system paths to image files.
            All images must be readable — ``None`` reads from
            :func:`cv2.imread` trigger :class:`FileNotFoundError`.
        resize: Target ``(height, width)`` to resize every image to before
            computing statistics. Defaults to ``(224, 224)`` (ImageNet size).

    Returns:
        :class:`ImageStats` with ``mean`` and ``std`` as three-element lists
        in **RGB** channel order.

    Raises:
        FileNotFoundError: If any path in *image_paths* cannot be read by
            OpenCV (missing file, unreadable format, etc.).

    Example::

        stats = compute_img_mean_std(["img1.jpg", "img2.jpg"])
        normalize = transforms.Normalize(mean=stats.mean, std=stats.std)
    """

    img_h, img_w = resize
    imgs: list[np.ndarray] = []

    for path in tqdm(image_paths, desc="Loading images", unit="img"):
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (img_w, img_h))
        imgs.append(img)

    # Stack into (N, H, W, C) float32 array, then normalize to [0, 1].
    # Using float32 avoids overflow in variance computation while keeping
    # memory usage reasonable (float64 would double memory for no practical
    # gain in accuracy at typical dataset sizes).
    imgs_arr = np.stack(imgs, axis=0).astype(np.float32) / 255.0
    logger.debug("Loaded image tensor shape: %s", imgs_arr.shape)

    # Reshape to (N, H*W, C) and compute per-channel statistics.
    # This avoids explicit Python loops and the BGR→RGB reorder hack.
    n, h, w, c = imgs_arr.shape
    pixels = imgs_arr.reshape(n, h * w, c)
    mean = pixels.mean(axis=(0, 1)).tolist()  # shape: (C,)
    std = pixels.std(axis=(0, 1)).tolist()  # shape: (C,)

    logger.debug("Image mean (RGB): %s", mean)
    logger.debug("Image std  (RGB): %s", std)

    return ImageStats(mean=mean, std=std)
