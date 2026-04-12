from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import patch

import torch
from pytorch_engine.training_loop import _resolve_compile_mode, train_model
from torch.utils.data import DataLoader, TensorDataset


class TrainModelMetricTests(unittest.TestCase):
    def test_train_accuracy_comes_from_online_training_pass(self) -> None:
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

        self.assertAlmostEqual(results["train_acc"][0], 0.5, places=6)
        self.assertAlmostEqual(results["test_acc"][0], 1.0, places=6)

    @patch("pytorch_engine.training_loop.test_step")
    @patch("pytorch_engine.training_loop.train_step")
    def test_early_stopping_restores_best_epoch_weights(
        self,
        mock_train_step: Any,
        mock_test_step: Any,
    ) -> None:
        features = torch.zeros((1, 1))
        labels = torch.zeros((1,), dtype=torch.long)
        dataloader = DataLoader(TensorDataset(features, labels), batch_size=1, shuffle=False)

        model = torch.nn.Linear(1, 1, bias=False)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
        loss_fn = torch.nn.CrossEntropyLoss()

        train_losses = [1.0, 0.9, 0.8, 0.7]
        test_losses = [0.5, 0.4, 0.41, 0.42]

        def fake_train_step(*args: object, **kwargs: object) -> dict[str, float]:
            epoch = cast(int, kwargs["epoch"])
            patched_model = cast(torch.nn.Linear, kwargs["model"])
            with torch.no_grad():
                patched_model.weight.fill_(float(epoch))
            return {"loss": train_losses[epoch - 1], "accuracy": 0.0}

        def fake_test_step(*args: object, **kwargs: object) -> dict[str, float]:
            epoch = cast(int, kwargs["epoch"])
            return {"loss": test_losses[epoch - 1], "accuracy": 0.0}

        mock_train_step.side_effect = fake_train_step
        mock_test_step.side_effect = fake_test_step

        results = train_model(
            model=model,
            train_dataloader=dataloader,
            test_dataloader=dataloader,
            optimizer=optimizer,
            loss_fn=loss_fn,
            epochs=10,
            device="cpu",
            early_stopping_patience=2,
        )

        self.assertEqual(len(results["test_loss"]), 4)
        self.assertEqual(results["test_loss"], test_losses)
        self.assertAlmostEqual(model.weight.item(), 2.0, places=6)


class TrainModelCudaTuningTests(unittest.TestCase):
    def test_short_cuda_run_downgrades_max_autotune(self) -> None:
        dataloader = DataLoader(TensorDataset(torch.zeros((32, 1))), batch_size=8, shuffle=False)

        compile_mode = _resolve_compile_mode(
            device=torch.device("cuda"),
            compile_mode="max-autotune",
            train_dataloader=dataloader,
            epochs=30,
        )

        self.assertEqual(compile_mode, "reduce-overhead")

    def test_long_cuda_run_keeps_max_autotune(self) -> None:
        dataloader = DataLoader(TensorDataset(torch.zeros((4096, 1))), batch_size=4, shuffle=False)

        compile_mode = _resolve_compile_mode(
            device=torch.device("cuda"),
            compile_mode="max-autotune",
            train_dataloader=dataloader,
            epochs=2,
        )

        self.assertEqual(compile_mode, "max-autotune")


if __name__ == "__main__":
    unittest.main()
