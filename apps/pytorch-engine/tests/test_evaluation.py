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
