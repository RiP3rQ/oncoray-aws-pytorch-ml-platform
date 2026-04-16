from __future__ import annotations

import unittest

from pytorch_engine.transforms import get_simple_train_transform
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


if __name__ == "__main__":
    unittest.main()
