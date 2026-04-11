"""Visualization utilities for PyTorch model inspection and result plotting."""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import torch
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


def plot_decision_boundary(
    model: torch.nn.Module,
    x_arg: torch.Tensor,
    y_arg: torch.Tensor,
) -> Figure:
    """Plot decision boundaries of *model* overlaid on the data.

    Moves model and data to CPU for NumPy/Matplotlib compatibility.
    Supports both binary and multi-class classification.

    Based on `Made With ML <https://madewithml.com/courses/foundations/neural-networks/>`_.

    Args:
        model: Trained classification model.
        X: Input feature tensor of shape ``(N, 2)``.
        y: Target label tensor of shape ``(N,)``.

    Returns:
        The :class:`matplotlib.figure.Figure` for further customisation
        or saving.
    """
    model.to("cpu")
    x, y = x_arg.to("cpu"), y_arg.to("cpu")

    x_min, x_max = x[:, 0].min() - 0.1, x[:, 0].max() + 0.1
    y_min, y_max = x[:, 1].min() - 0.1, x[:, 1].max() + 0.1
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, 101), np.linspace(y_min, y_max, 101))

    x_to_pred = torch.from_numpy(np.column_stack((xx.ravel(), yy.ravel()))).float()

    model.eval()
    with torch.inference_mode():
        logits = model(x_to_pred)

    if len(torch.unique(y)) > 2:
        preds = torch.softmax(logits, dim=1).argmax(dim=1)
    else:
        preds = torch.round(torch.sigmoid(logits))

    preds = preds.reshape(xx.shape).detach().numpy()

    fig, ax = plt.subplots()
    ax.contourf(xx, yy, preds, cmap=plt.cm.RdYlBu, alpha=0.7)
    ax.scatter(x[:, 0], x[:, 1], c=y, s=40, cmap=plt.cm.RdYlBu)
    ax.set_xlim(xx.min(), xx.max())
    ax.set_ylim(yy.min(), yy.max())
    return fig


def plot_predictions(
    train_data: np.ndarray,
    train_labels: np.ndarray,
    test_data: np.ndarray,
    test_labels: np.ndarray,
    predictions: np.ndarray | None = None,
) -> Figure:
    """Plot linear training data, test data, and optional predictions.

    Args:
        train_data: Training feature values.
        train_labels: Training target values.
        test_data: Test feature values.
        test_labels: Test target values.
        predictions: Optional model predictions on *test_data*.

    Returns:
        The :class:`matplotlib.figure.Figure`.
    """
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(train_data, train_labels, c="b", s=4, label="Training data")
    ax.scatter(test_data, test_labels, c="g", s=4, label="Testing data")
    if predictions is not None:
        ax.scatter(test_data, predictions, c="r", s=4, label="Predictions")
    ax.legend(prop={"size": 14})
    return fig


def plot_loss_curves(results: dict[str, list[float]]) -> Figure:
    """Plot training and test loss/accuracy curves from a results dict.

    Expects keys ``"train_loss"``, ``"test_loss"``, ``"train_acc"``,
    ``"test_acc"`` — the same shape returned by :func:`train_model
    <pytorch_engine.training_loop.train_model>`.

    Args:
        results: Dictionary of per-epoch metric lists.

    Returns:
        The :class:`matplotlib.figure.Figure`.
    """
    epochs = range(len(results["train_loss"]))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))

    ax1.plot(epochs, results["train_loss"], label="train_loss")
    ax1.plot(epochs, results["test_loss"], label="test_loss")
    ax1.set_title("Loss")
    ax1.set_xlabel("Epochs")
    ax1.legend()

    ax2.plot(epochs, results["train_acc"], label="train_accuracy")
    ax2.plot(epochs, results["test_acc"], label="test_accuracy")
    ax2.set_title("Accuracy")
    ax2.set_xlabel("Epochs")
    ax2.legend()

    return fig
