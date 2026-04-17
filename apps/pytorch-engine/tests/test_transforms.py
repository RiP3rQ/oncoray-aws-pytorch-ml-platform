from __future__ import annotations

import unittest

from pytorch_engine.transforms import (
    get_chest_xray_eval_transform,
    get_chest_xray_train_transform,
    get_simple_train_transform,
)
from torchvision import transforms


class SimpleTrainTransformTests(unittest.TestCase):
    def test_builds_lightweight_train_pipeline(self) -> None:
        transform = get_simple_train_transform(
            image_size=(256, 256),
            normalize_mean=[0.1, 0.2, 0.3],
            normalize_std=[0.4, 0.5, 0.6],
            interpolation=transforms.InterpolationMode.BILINEAR,
            rotation_degrees=5,
            horizontal_flip_probability=0.25,
        )

        self.assertIsInstance(transform, transforms.Compose)
        self.assertEqual(
            [type(step).__name__ for step in transform.transforms],
            [
                "RandomResizedCrop",
                "RandomHorizontalFlip",
                "RandomRotation",
                "ToTensor",
                "Normalize",
            ],
        )

        resize = transform.transforms[0]
        flip = transform.transforms[1]
        rotation = transform.transforms[2]
        normalize = transform.transforms[-1]

        self.assertEqual(resize.size, (256, 256))
        self.assertEqual(flip.p, 0.25)
        self.assertEqual(rotation.degrees, [-5.0, 5.0])
        self.assertEqual(normalize.mean, [0.1, 0.2, 0.3])
        self.assertEqual(normalize.std, [0.4, 0.5, 0.6])


class ChestXrayTrainTransformTests(unittest.TestCase):
    def test_builds_chest_xray_specific_train_pipeline(self) -> None:
        transform = get_chest_xray_train_transform(
            image_size=(224, 224),
            resize_size=(256, 256),
            normalize_mean=[0.1, 0.2, 0.3],
            normalize_std=[0.4, 0.5, 0.6],
            interpolation=transforms.InterpolationMode.BILINEAR,
            rotation_degrees=6,
            translate=(0.01, 0.02),
            scale=(0.97, 1.03),
            brightness=0.05,
            contrast=0.07,
            affine_probability=0.7,
            jitter_probability=0.3,
        )

        self.assertIsInstance(transform, transforms.Compose)
        self.assertEqual(
            [type(step).__name__ for step in transform.transforms],
            [
                "Resize",
                "RandomCrop",
                "RandomApply",
                "RandomApply",
                "ToTensor",
                "Normalize",
            ],
        )

        resize = transform.transforms[0]
        crop = transform.transforms[1]
        affine_apply = transform.transforms[2]
        jitter_apply = transform.transforms[3]
        normalize = transform.transforms[-1]

        self.assertEqual(resize.size, (256, 256))
        self.assertEqual(crop.size, (224, 224))
        self.assertEqual(affine_apply.p, 0.7)
        self.assertEqual(jitter_apply.p, 0.3)
        self.assertEqual(normalize.mean, [0.1, 0.2, 0.3])
        self.assertEqual(normalize.std, [0.4, 0.5, 0.6])

    def test_builds_deterministic_eval_pipeline(self) -> None:
        transform = get_chest_xray_eval_transform(
            image_size=(224, 224),
            resize_size=(256, 256),
            normalize_mean=[0.1, 0.2, 0.3],
            normalize_std=[0.4, 0.5, 0.6],
            interpolation=transforms.InterpolationMode.BILINEAR,
        )

        self.assertIsInstance(transform, transforms.Compose)
        self.assertEqual(
            [type(step).__name__ for step in transform.transforms],
            [
                "Resize",
                "CenterCrop",
                "ToTensor",
                "Normalize",
            ],
        )

        resize = transform.transforms[0]
        crop = transform.transforms[1]
        normalize = transform.transforms[-1]

        self.assertEqual(resize.size, (256, 256))
        self.assertEqual(crop.size, (224, 224))
        self.assertEqual(normalize.mean, [0.1, 0.2, 0.3])
        self.assertEqual(normalize.std, [0.4, 0.5, 0.6])


if __name__ == "__main__":
    unittest.main()
