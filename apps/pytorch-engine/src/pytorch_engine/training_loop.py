"""Training loop utilities for PyTorch image classification models.

Provides epoch-level :func:`train_step` and :func:`test_step` helpers, plus
a :func:`train_model` orchestrator that runs a full training run and returns
per-epoch metrics.
"""

import logging
from collections.abc import Callable
from typing import TypedDict

import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

from pytorch_engine.utils import accuracy_fn, resolve_device

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class StepResult(TypedDict):
    """Return type for :func:`train_step` and :func:`test_step`.

    Attributes:
        loss: Average loss over all batches in the epoch.
        accuracy: Average accuracy (0–1) over all batches in the epoch.
    """

    loss: float
    accuracy: float


class TrainResult(TypedDict):
    """Return type for :func:`train_model`.

    Each value is a list of per-epoch measurements whose length equals
    the number of training epochs.

    Attributes:
        train_loss: Training loss per epoch.
        train_acc: Training accuracy per epoch.
        test_loss: Test loss per epoch.
        test_acc: Test accuracy per epoch.
    """

    train_loss: list[float]
    train_acc: list[float]
    test_loss: list[float]
    test_acc: list[float]


# ---------------------------------------------------------------------------
# Single-epoch steps
# ---------------------------------------------------------------------------


def train_step(
    model: torch.nn.Module,
    dataloader: DataLoader,
    loss_fn: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    device: str | torch.device = "auto",
) -> StepResult:
    """Run a single training epoch.

    Sets *model* to training mode, iterates every batch in *dataloader*
    (forward → loss → backward → optimizer step), and returns the average
    loss and accuracy across all batches.

    Args:
        model: Model to train.
        dataloader: Training data loader.
        loss_fn: Loss function to minimise.
        optimizer: Optimizer for parameter updates.
        device: ``"auto"`` resolves to CUDA when available.

    Returns:
        A :class:`StepResult` with average ``loss`` and ``accuracy``.
    """
    computed_device = resolve_device(device)
    # Put model in train mode
    model.to(computed_device).train()

    # Setup train loss and train accuracy values
    running_loss: float = 0.0
    running_acc: float = 0.0
    num_batches = len(dataloader)

    logger.info("Train step started on %s (%d batches)", computed_device, num_batches)

    # Loop through data loader data batches
    for _batch_idx, (X, y) in enumerate(dataloader):
        # Send data to target device
        X, y = X.to(computed_device), y.to(computed_device)

        # 1. Forward pass
        y_pred = model(X)

        # 2. Calculate  and accumulate loss
        loss = loss_fn(y_pred, y)
        running_loss += loss.item()

        # 3. Optimizer zero grad
        optimizer.zero_grad()

        # 4. Loss backward
        loss.backward()

        # 5. Optimizer step
        optimizer.step()

        # Calculate and accumulate accuracy metric across all batches
        y_pred_class = torch.argmax(torch.softmax(y_pred, dim=1), dim=1)
        running_acc += accuracy_fn(y_true=y, y_pred=y_pred_class)

    # Adjust metrics to get average loss and accuracy per batch
    avg_loss = running_loss / num_batches
    avg_acc = running_acc / num_batches

    logger.info("Train step complete — loss=%.4f accuracy=%.4f", avg_loss, avg_acc)
    return StepResult(loss=avg_loss, accuracy=avg_acc)


def test_step(
    model: torch.nn.Module,
    dataloader: DataLoader,
    loss_fn: torch.nn.Module,
    device: str | torch.device = "auto",
) -> StepResult:
    """Run a single evaluation epoch.

    Sets *model* to eval mode with :func:`torch.inference_mode` and
    computes average loss and accuracy over *dataloader*.

    Args:
        model: Model to evaluate.
        dataloader: Test/validation data loader.
        loss_fn: Loss function used for evaluation.
        device: ``"auto"`` resolves to CUDA when available.

    Returns:
        A :class:`StepResult` with average ``loss`` and ``accuracy``.
    """
    computed_device = resolve_device(device)
    # Put model in eval mode
    model.to(computed_device).eval()

    # Setup test loss and test accuracy values
    running_loss: float = 0.0
    running_acc: float = 0.0
    num_batches = len(dataloader)

    logger.info("Test step started on %s (%d batches)", computed_device, num_batches)

    # Turn on inference context manager
    with torch.inference_mode():
        # Loop through DataLoader batches
        for _batch_idx, (X, y) in enumerate(dataloader):
            # Send data to target device
            X, y = X.to(computed_device), y.to(computed_device)

            # 1. Forward pass
            test_pred_logits = model(X)

            # 2. Calculate and accumulate loss
            loss = loss_fn(test_pred_logits, y)
            running_loss += loss.item()

            # Calculate and accumulate accuracy (argmax over logits, no softmax needed)
            test_pred_labels = test_pred_logits.argmax(dim=1)
            running_acc += accuracy_fn(y_true=y, y_pred=test_pred_labels)

    # Adjust metrics to get average loss and accuracy per batch
    avg_loss = running_loss / num_batches
    avg_acc = running_acc / num_batches

    logger.info("Test step complete — loss=%.4f accuracy=%.4f", avg_loss, avg_acc)
    return StepResult(loss=avg_loss, accuracy=avg_acc)


# ---------------------------------------------------------------------------
# Full training run
# ---------------------------------------------------------------------------


def train_model(
    model: torch.nn.Module,
    train_dataloader: DataLoader,
    test_dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn: torch.nn.Module,
    epochs: int,
    device: str | torch.device = "auto",
    epoch_end_callback: Callable[[int, torch.nn.Module, StepResult, StepResult], None] | None = None,
) -> TrainResult:
    """Train and evaluate a model for multiple epochs.

    Runs :func:`train_step` followed by :func:`test_step` for each epoch,
    logging per-epoch metrics and returning the full history.

    Args:
        model: Model to train and evaluate.
        train_dataloader: DataLoader for training data.
        test_dataloader: DataLoader for test/validation data.
        optimizer: Optimizer for parameter updates.
        loss_fn: Loss function to minimise.
        epochs: Number of training epochs.
        device: ``"auto"`` resolves to CUDA when available.
        epoch_end_callback: Optional callback called after each epoch with
            ``(epoch_number_1_based, model, train_result, test_result)``.
            Callback failures are logged and training continues.

    Returns:
        A :class:`TrainResult` dict with per-epoch metric lists.

    Example::

        result = train_model(
            model=model,
            train_dataloader=train_dl,
            test_dataloader=test_dl,
            optimizer=optimizer,
            loss_fn=loss_fn,
            epochs=5,
            device="auto",
        )
        # result["train_loss"] → [2.06, 1.05, ...]
    """
    computed_device = resolve_device(device)
    # Make sure model on target device
    model.to(computed_device)

    logger.info(
        "Training started — model=%s epochs=%d device=%s",
        model.__class__.__name__,
        epochs,
        computed_device,
    )

    results: TrainResult = {
        "train_loss": [],
        "train_acc": [],
        "test_loss": [],
        "test_acc": [],
    }

    # Loop through training and testing steps for a number of epochs
    for epoch in tqdm(range(epochs), desc="Epochs"):
        train_result = train_step(
            model=model,
            dataloader=train_dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            device=computed_device,
        )
        test_result = test_step(
            model=model,
            dataloader=test_dataloader,
            loss_fn=loss_fn,
            device=computed_device,
        )

        logger.info(
            "Epoch %d/%d — train_loss=%.4f train_acc=%.4f test_loss=%.4f test_acc=%.4f",
            epoch + 1,
            epochs,
            train_result["loss"],
            train_result["accuracy"],
            test_result["loss"],
            test_result["accuracy"],
        )

        # Update results dictionary
        results["train_loss"].append(train_result["loss"])
        results["train_acc"].append(train_result["accuracy"])
        results["test_loss"].append(test_result["loss"])
        results["test_acc"].append(test_result["accuracy"])

        if epoch_end_callback is not None:
            try:
                epoch_end_callback(epoch + 1, model, train_result, test_result)
            except Exception as error:  # pragma: no cover - callback runtime dependent
                logger.warning("Epoch-end callback failed at epoch %d: %s", epoch + 1, error)

    logger.info("Training complete — %d epochs finished", epochs)
    return results
