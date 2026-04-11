"""Image prediction and visualization utilities for PyTorch models."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TypedDict

import torch
import torchvision
from matplotlib.figure import Figure
from PIL import Image

from pytorch_engine.transforms import _DEFAULT_IMAGE_SIZE, get_default_transform
from pytorch_engine.utils import resolve_device

logger = logging.getLogger(__name__)


class PredictionResult(TypedDict):
    """Return type for :func:`predict_image`.

    Attributes:
        class_name: Predicted class label.
        confidence: Prediction probability for the top class (0–1).
        probabilities: Full probability distribution over all classes.
    """

    class_name: str
    confidence: float
    probabilities: torch.Tensor


def predict_image(
    model: torch.nn.Module,
    image_path: str | Path,
    class_names: list[str],
    image_size: tuple[int, int] = _DEFAULT_IMAGE_SIZE,
    transform: torchvision.transforms.Compose | None = None,
    device: str | torch.device = "auto",
) -> PredictionResult:
    """Run inference on a single image.

    Puts *model* into eval mode with :func:`torch.inference_mode` and
    returns predicted class, confidence, and full probability tensor.

    Args:
        model: A PyTorch model to predict with.
        image_path: Filepath to the image to predict on.
        class_names: Mapping from class index to label.
        image_size: ``(H, W)`` to resize to when *transform* is ``None``.
        transform: Custom transform pipeline. When ``None``, an ImageNet
            normalised resize pipeline is constructed from *image_size*.
        device: Target device. ``"auto"`` picks CUDA if available.

    Returns:
        A :class:`PredictionResult` dict with ``"class_name"``,
        ``"confidence"``, and ``"probabilities"`` keys.

    Example::

        result = predict_image(model, "photo.jpg", class_names=["cat", "dog"])
        print(result["class_name"], result["confidence"])
    """
    computed_device = resolve_device(device)
    logger.info("Predicting on %s for image %s", computed_device, image_path)

    img = Image.open(image_path)
    logger.info("Opened image: %s (size=%s)", image_path, img.size)

    image_transform = (
        transform if transform is not None else get_default_transform(image_size)
    )

    model.to(computed_device).eval()
    with torch.inference_mode():
        transformed = image_transform(img)
        assert isinstance(transformed, torch.Tensor), "Transform must produce a Tensor"
        img_tensor = transformed.unsqueeze(dim=0).to(computed_device)
        logger.info("Input tensor shape: %s", img_tensor.shape)
        logits = model(img_tensor)

    probabilities = torch.softmax(logits, dim=1)
    confidence: float = probabilities.max().item()
    pred_index: int = int(probabilities.argmax(dim=1).item())
    logger.info(
        "Prediction: class=%s confidence=%.4f index=%d",
        class_names[pred_index],
        confidence,
        pred_index,
    )

    return PredictionResult(
        class_name=class_names[pred_index],
        confidence=confidence,
        probabilities=probabilities.squeeze(0),
    )


def plot_prediction(
    image_path: str | Path,
    class_name: str,
    confidence: float,
) -> Figure:
    """Display an image annotated with predicted class and confidence.

    Args:
        image_path: Filepath to the source image.
        class_name: Predicted label to display.
        confidence: Probability of the predicted label.

    Returns:
        The :class:`matplotlib.figure.Figure` for further customisation
        or saving.
    """
    import matplotlib.pyplot as plt

    logger.info(
        "Plotting prediction for %s: %s (%.3f)", image_path, class_name, confidence
    )
    img = Image.open(image_path)
    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.set_title(f"Pred: {class_name} | Prob: {confidence:.3f}")
    ax.axis("off")
    return fig
