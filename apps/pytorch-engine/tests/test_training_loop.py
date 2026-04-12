from __future__ import annotations

import unittest
from typing import cast

import torch
from pytorch_engine.training_loop import train_model
from torch.utils.data import DataLoader, TensorDataset


class TrainModelMetricTests(unittest.TestCase):
    def test_train_accuracy_uses_eval_mode_final_epoch_model(self) -> None:
        features = torch.tensor(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ]
        )
        labels = torch.tensor([0, 1, 0, 1])
        dataloader = DataLoader(TensorDataset(features, labels), batch_size=2, shuffle=False)

        model = torch.nn.Sequential(
            torch.nn.Dropout(p=1.0),
            torch.nn.Linear(2, 2, bias=False),
        )
        linear = cast(torch.nn.Linear, model[1])
        with torch.no_grad():
            linear.weight.copy_(torch.eye(2))

        optimizer = torch.optim.SGD(model.parameters(), lr=0.0)
        loss_fn = torch.nn.CrossEntropyLoss()

        results = train_model(
            model=model,
            train_dataloader=dataloader,
            test_dataloader=dataloader,
            optimizer=optimizer,
            loss_fn=loss_fn,
            epochs=1,
            device="cpu",
        )

        self.assertAlmostEqual(results["train_acc"][0], 1.0, places=6)
        self.assertAlmostEqual(results["test_acc"][0], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
