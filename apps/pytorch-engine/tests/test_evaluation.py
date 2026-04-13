from __future__ import annotations

import unittest

import matplotlib.pyplot as plt
import torch
from pytorch_engine.evaluation import evaluate_classification_model
from pytorch_engine.visualization import plot_confusion_matrix
from torch.utils.data import DataLoader, TensorDataset


class EvaluateClassificationModelTests(unittest.TestCase):
    def test_returns_expected_balanced_metrics(self) -> None:
        features = torch.tensor(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0],
            ]
        )
        labels = torch.tensor([0, 1, 2, 1])
        dataloader = DataLoader(TensorDataset(features, labels), batch_size=2, shuffle=False)

        model = torch.nn.Linear(3, 3, bias=False)
        with torch.no_grad():
            model.weight.copy_(torch.eye(3))

        metrics = evaluate_classification_model(
            model=model,
            dataloader=dataloader,
            class_names=["akiec", "bcc", "mel"],
            device="cpu",
        )

        self.assertAlmostEqual(metrics["accuracy"], 0.75, places=6)
        self.assertAlmostEqual(metrics["balanced_accuracy"], 5 / 6, places=6)
        self.assertAlmostEqual(metrics["macro_f1"], 7 / 9, places=6)
        self.assertAlmostEqual(metrics["macro_precision"], 5 / 6, places=6)
        self.assertAlmostEqual(metrics["macro_recall"], 5 / 6, places=6)
        self.assertAlmostEqual(metrics["weighted_f1"], 0.75, places=6)
        self.assertEqual(metrics["confusion_matrix"], [[1, 0, 0], [1, 1, 0], [0, 0, 1]])
        self.assertEqual(metrics["per_class_support"], {"akiec": 1, "bcc": 2, "mel": 1})
        self.assertAlmostEqual(metrics["per_class_recall"]["bcc"], 0.5, places=6)
        self.assertEqual(metrics["y_true"], [0, 1, 2, 1])
        self.assertEqual(metrics["y_pred"], [0, 1, 2, 0])

    def test_tta_runs_multiple_forward_passes_per_batch(self) -> None:
        features = torch.tensor(
            [
                [[[1.0, 0.0], [0.0, 0.0]]],
                [[[0.0, 1.0], [0.0, 0.0]]],
            ]
        )
        labels = torch.tensor([0, 1])
        dataloader = DataLoader(TensorDataset(features, labels), batch_size=2, shuffle=False)

        class CountingModel(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.forward_calls = 0

            def forward(self, X: torch.Tensor) -> torch.Tensor:
                self.forward_calls += 1
                left_score = X[..., 0].sum(dim=(-2, -1))
                right_score = X[..., 1].sum(dim=(-2, -1))
                return torch.stack([left_score, right_score], dim=1)

        model = CountingModel()

        metrics = evaluate_classification_model(
            model=model,
            dataloader=dataloader,
            class_names=["left", "right"],
            device="cpu",
            tta_transforms=("identity", "hflip"),
        )

        self.assertEqual(model.forward_calls, 2)
        self.assertEqual(metrics["y_true"], [0, 1])
        self.assertEqual(len(metrics["y_pred"]), 2)


class PlotConfusionMatrixTests(unittest.TestCase):
    def test_returns_figure(self) -> None:
        figure = plot_confusion_matrix(
            confusion_matrix_values=[[0.9, 0.1], [0.2, 0.8]],
            class_names=["neg", "pos"],
            normalize=True,
        )

        self.assertEqual(figure.axes[0].get_title(), "Normalized Confusion Matrix")
        plt.close(figure)


if __name__ == "__main__":
    unittest.main()
