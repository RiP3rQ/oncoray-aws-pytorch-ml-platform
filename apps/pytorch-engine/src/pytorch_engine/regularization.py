"""Batch-level regularization helpers for image classification."""

from __future__ import annotations

from collections.abc import Callable

import torch
import torch.nn.functional as F


def soft_target_cross_entropy(
    logits: torch.Tensor,
    targets: torch.Tensor,
    weight: torch.Tensor | None = None,
    reduction: str = "mean",
) -> torch.Tensor:
    """Cross-entropy for probability targets such as MixUp labels."""
    if logits.ndim != 2:
        raise ValueError("logits must have shape [batch_size, num_classes]")

    if targets.ndim == 1:
        if targets.size(0) != logits.size(0):
            raise ValueError("hard targets batch size must match logits batch size")
        targets = F.one_hot(targets.long(), num_classes=logits.size(1)).to(device=logits.device, dtype=logits.dtype)
    elif targets.shape != logits.shape:
        raise ValueError("targets must match logits shape for soft-target cross-entropy")

    log_probs = F.log_softmax(logits, dim=1)
    if weight is not None:
        weight = weight.to(device=logits.device, dtype=logits.dtype)
        loss = -(targets.to(dtype=logits.dtype) * log_probs * weight.unsqueeze(0)).sum(dim=1)
    else:
        loss = -(targets.to(dtype=logits.dtype) * log_probs).sum(dim=1)

    if reduction == "none":
        return loss
    if reduction == "sum":
        return loss.sum()
    if reduction == "mean":
        return loss.mean()
    raise ValueError("reduction must be one of: none, mean, sum")


class SoftTargetCrossEntropyLoss(torch.nn.Module):
    """Module wrapper around :func:`soft_target_cross_entropy`."""

    def __init__(
        self,
        weight: torch.Tensor | None = None,
        reduction: str = "mean",
    ) -> None:
        super().__init__()
        self.weight = weight
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return soft_target_cross_entropy(
            logits=logits,
            targets=targets,
            weight=self.weight,
            reduction=self.reduction,
        )


class MixUpBatchTransform:
    """Apply MixUp to a training batch and expose weighted accuracy tracking."""

    def __init__(
        self,
        num_classes: int,
        alpha: float = 0.2,
        p: float = 1.0,
    ) -> None:
        if num_classes < 2:
            raise ValueError("num_classes must be >= 2")
        if alpha <= 0:
            raise ValueError("alpha must be > 0")
        if not 0.0 <= p <= 1.0:
            raise ValueError("p must be in [0, 1]")
        self.num_classes = num_classes
        self.alpha = alpha
        self.p = p

    def __call__(
        self,
        X: torch.Tensor,
        y: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, Callable[[torch.Tensor], float]]:
        if y.ndim != 1:
            raise ValueError("MixUp expects hard class-index labels")

        hard_labels = y.long()
        one_hot_labels = F.one_hot(hard_labels, num_classes=self.num_classes).to(dtype=torch.float32, device=X.device)

        def hard_accuracy_fn(logits: torch.Tensor) -> float:
            predictions = logits.argmax(dim=1)
            return float(torch.eq(predictions, hard_labels).sum().item())

        if hard_labels.size(0) < 2:
            return X, one_hot_labels, hard_accuracy_fn

        apply_mixup = self.p >= 1.0 or float(torch.rand((), device=X.device).item()) < self.p
        if not apply_mixup:
            return X, one_hot_labels, hard_accuracy_fn

        beta_dist = torch.distributions.Beta(self.alpha, self.alpha)
        mix_lam = float(beta_dist.sample(()).item())
        permutation = torch.randperm(hard_labels.size(0), device=X.device)

        mixed_inputs = (mix_lam * X) + ((1.0 - mix_lam) * X[permutation])
        mixed_targets = (mix_lam * one_hot_labels) + ((1.0 - mix_lam) * one_hot_labels[permutation])
        paired_labels = hard_labels[permutation]

        def mixup_accuracy_fn(logits: torch.Tensor) -> float:
            predictions = logits.argmax(dim=1)
            correct_primary = torch.eq(predictions, hard_labels).sum().item()
            correct_paired = torch.eq(predictions, paired_labels).sum().item()
            return float((mix_lam * correct_primary) + ((1.0 - mix_lam) * correct_paired))

        return mixed_inputs, mixed_targets, mixup_accuracy_fn
