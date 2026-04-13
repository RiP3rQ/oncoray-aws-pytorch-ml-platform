from __future__ import annotations

import unittest

import torch
import torch.nn.functional as F
from pytorch_engine.regularization import MixUpBatchTransform, SoftTargetCrossEntropyLoss
from pytorch_engine.training_loop import train_step
from torch.utils.data import DataLoader, TensorDataset


class SoftTargetCrossEntropyLossTests(unittest.TestCase):
    def test_matches_cross_entropy_on_one_hot_targets(self) -> None:
        logits = torch.tensor([[2.0, 0.5, -1.0], [0.1, 1.3, -0.2]], dtype=torch.float32)
        hard_targets = torch.tensor([0, 1], dtype=torch.long)
        soft_targets = F.one_hot(hard_targets, num_classes=3).to(dtype=torch.float32)

        expected = torch.nn.CrossEntropyLoss()(logits, hard_targets)
        actual = SoftTargetCrossEntropyLoss()(logits, soft_targets)

        self.assertAlmostEqual(actual.item(), expected.item(), places=6)


class MixUpTrainingLoopTests(unittest.TestCase):
    def test_train_step_supports_soft_targets_via_batch_transform(self) -> None:
        features = torch.tensor(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=torch.float32,
        )
        labels = torch.tensor([0, 1, 0, 1], dtype=torch.long)
        dataloader = DataLoader(TensorDataset(features, labels), batch_size=4, shuffle=False)

        model = torch.nn.Linear(2, 2, bias=False)
        with torch.no_grad():
            model.weight.copy_(torch.eye(2))

        optimizer = torch.optim.SGD(model.parameters(), lr=0.0)
        loss_fn = SoftTargetCrossEntropyLoss()
        mixup = MixUpBatchTransform(num_classes=2, alpha=0.2, p=0.0)

        result = train_step(
            epoch=1,
            model=model,
            dataloader=dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            device="cpu",
            train_batch_transform=mixup,
        )

        self.assertAlmostEqual(result["accuracy"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
